import json
import py_compile
import sys
import types
from pathlib import Path

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
        llm = StubLLM(responses)
        monkeypatch.setitem(sys.modules, "kaggle_benchmarks", fake_sdk(llm))
        ns = {"__name__": "generated_task"}
        exec(compile(code, str(output), "exec"), ns)
        assert ns["gone_for_good"].result == expected
        assert len(llm.calls) == 6
        assert all(call["temperature"] == 0 and
                   call["extra_api_params"] == {"max_tokens": 1024} for call in llm.calls)
        lines = capsys.readouterr().out.splitlines()
        assert len([line for line in lines if line.startswith("GFG_ITEM ")]) == 6
        assert len([line for line in lines if line.startswith("GFG_AGGREGATE ")]) == 1


def test_real_sdk_import_and_mock_availability():
    import kaggle_benchmarks as kbench
    from kaggle_benchmarks import tasks
    assert callable(kbench.task)
    assert "store_task" in tasks.task.__code__.co_varnames
    # Installed package has no built-in offline mock LLM with a prompt-only constructor.
