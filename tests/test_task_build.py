import json
import py_compile
import sys
import types
from pathlib import Path

import pytest

from tasks.build_task import build_task


DATA = Path(__file__).parent / "data"


class StubLLM:
    def __init__(self, replies):
        self.replies = replies
        self.calls = []

    def prompt(self, prompt, **kwargs):
        self.calls.append(kwargs)
        return self.replies[prompt]


class FakeTask:
    def __init__(self, func):
        self.func = func
        self.result = None

    def __call__(self, *args):
        return self.func(*args)

    def run(self, llm):
        self.result = self.func(llm)
        return types.SimpleNamespace(result=self.result)


def fake_sdk(llm):
    module = types.ModuleType("kaggle_benchmarks")
    module.llm = llm
    module.task = lambda **kwargs: lambda func: FakeTask(func)
    return module


def run_generated(code, output, llm, monkeypatch):
    module = fake_sdk(llm)
    actors = types.ModuleType("kaggle_benchmarks.actors")
    adapters = types.ModuleType("kaggle_benchmarks.actors.llms")
    adapters.OpenAI = OpenAIStub
    adapters.GoogleGenAI = GoogleStub
    monkeypatch.setitem(sys.modules, "kaggle_benchmarks", module)
    monkeypatch.setitem(sys.modules, "kaggle_benchmarks.actors", actors)
    monkeypatch.setitem(sys.modules, "kaggle_benchmarks.actors.llms", adapters)
    ns = {"__name__": "generated_task"}
    exec(compile(code, str(output), "exec"), ns)
    return ns


class OpenAIStub(StubLLM):
    pass


class GoogleStub(StubLLM):
    pass


def test_generated_task_compiles_and_runs(tmp_path, monkeypatch, capsys):
    output = build_task(DATA / "mini_gold.jsonl", DATA / "mini_items.jsonl", tmp_path / "task.py")
    py_compile.compile(str(output), doraise=True)
    code = output.read_text()
    assert code.count("# %%") >= 4
    assert "gone_for_good.run(kbench.llm)" in code
    assert "@kbench.task(name='gone-for-good')" in code
    assert "if __name__ == \"__main__\"" not in code
    gold = {g["item_id"]: g for g in map(json.loads, (DATA / "mini_gold.jsonl").read_text().splitlines())}
    items = list(map(json.loads, (DATA / "mini_items.jsonl").read_text().splitlines()))
    replies = {i["prompt"]: json.dumps({key: gold[i["item_id"]][key]
                                        for key in ("lost", "recoverable", "permanent_loss")}) for i in items}
    for expected, responses in ((1.0, replies), (0.0, {i["prompt"]: "garbage" for i in items})):
        llm = OpenAIStub(responses)
        ns = run_generated(code, output, llm, monkeypatch)
        assert ns["gone_for_good"].result == expected
        assert len(llm.calls) == 6
        assert all(call["temperature"] == 0 and
                   call["extra_api_params"] == {"max_tokens": 16384, "timeout": 600} for call in llm.calls)
        lines = capsys.readouterr().out.splitlines()
        assert len([line for line in lines if line.startswith("GFG_ITEM ")]) == 6
        assert len([line for line in lines if line.startswith("GFG_AGGREGATE ")]) == 1


def test_adapter_dispatch_and_unknown(tmp_path, monkeypatch):
    output = build_task(DATA / "mini_gold.jsonl", DATA / "mini_items.jsonl", tmp_path / "task.py", max_tokens=512)
    code = output.read_text()
    for cls, params in ((type("GoogleChild", (GoogleStub,), {}), {"max_output_tokens": 512}),
                        (StubLLM, {})):
        llm = cls({})
        run_generated(code, output, llm, monkeypatch)
        assert llm.calls[0]["extra_api_params"] == params


def test_api_error_continues_and_cap_retry(tmp_path, monkeypatch, capsys):
    output = build_task(DATA / "mini_gold.jsonl", DATA / "mini_items.jsonl", tmp_path / "task.py")
    code = output.read_text()
    prompts = [json.loads(line)["prompt"] for line in (DATA / "mini_items.jsonl").read_text().splitlines()]
    gold = [json.loads(line) for line in (DATA / "mini_gold.jsonl").read_text().splitlines()]
    replies = {p: json.dumps({k: g[k] for k in ("lost", "recoverable", "permanent_loss")})
               for p, g in zip(prompts, gold)}

    class Failing(OpenAIStub):
        def prompt(self, prompt, **kwargs):
            self.calls.append((prompt, kwargs))
            if prompt == prompts[2]:
                raise RuntimeError("provider down")
            return self.replies[prompt]

    import time
    monkeypatch.setattr(time, "sleep", lambda seconds: None)
    llm = Failing(replies)
    ns = run_generated(code, output, llm, monkeypatch)
    assert len(llm.calls) == 7
    assert llm.calls[-1][0] == prompts[-1]
    assert ns["gone_for_good"].result == pytest.approx(2 / 3)
    lines = capsys.readouterr().out.splitlines()
    rows = [json.loads(line.removeprefix("GFG_ITEM ")) for line in lines if line.startswith("GFG_ITEM ")]
    summary = next(json.loads(line.removeprefix("GFG_AGGREGATE ")) for line in lines if line.startswith("GFG_AGGREGATE "))
    assert rows[2]["format_error"] == "api_error"
    assert rows[2]["api_error"].startswith("RuntimeError: provider down")
    assert summary["n_api_errors"] == 1

    class RejectCap(OpenAIStub):
        def prompt(self, prompt, **kwargs):
            self.calls.append(kwargs)
            if "max_tokens" in kwargs["extra_api_params"]:
                raise ValueError("unsupported parameter max_tokens")
            return self.replies[prompt]

    llm = RejectCap(replies)
    ns = run_generated(code, output, llm, monkeypatch)
    assert ns["gone_for_good"].result == 1
    assert len(llm.calls) == 12
    assert "max_tokens" not in llm.calls[1]["extra_api_params"]


def test_builder_rejects_duplicate_and_single_variant(tmp_path):
    gold = [json.loads(line) for line in (DATA / "mini_gold.jsonl").read_text().splitlines()]
    items = DATA / "mini_items.jsonl"
    path = tmp_path / "gold.jsonl"
    for rows in (gold + [gold[0]], gold[:1]):
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        with pytest.raises(ValueError):
            build_task(path, items, tmp_path / "task.py")


def test_real_sdk_import_and_mock_availability():
    import kaggle_benchmarks as kbench
    from kaggle_benchmarks import tasks
    assert callable(kbench.task)
    assert "store_task" in tasks.task.__code__.co_varnames
    # Installed package has no built-in offline mock LLM with a prompt-only constructor.
