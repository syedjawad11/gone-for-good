from dataclasses import replace
from pathlib import Path

import pytest

from fixtures.base import Artifact, Resource, Variant, file_fp
from fixtures.demo.demo1 import PAIR
from harness.run import check_operation, execute_variant, run_harness


def test_demo_labels_and_determinism(tmp_path: Path) -> None:
    out = tmp_path / "data"
    rows, items = run_harness(out, only={"DEMO-1"}, include_demo=True)
    by_variant = {row["variant"]: row for row in rows}
    assert by_variant["A"]["lost"] == ["R1"]
    assert by_variant["A"]["recoverable"] == ["R1"]
    assert by_variant["B"]["lost"] == ["R1", "R3"]
    assert by_variant["B"]["recoverable"] == []
    first = ((out / "gold.jsonl").read_bytes(), (out / "items.jsonl").read_bytes())
    run_harness(out, only={"DEMO-1"}, include_demo=True)
    assert first == ((out / "gold.jsonl").read_bytes(), (out / "items.jsonl").read_bytes())
    for item in items:
        assert "DEMO-1A" not in item["prompt"]
        assert PAIR.changed_fact not in item["prompt"]
        assert str(tmp_path) not in item["prompt"]


def test_safety_rejects_parent_path(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    with pytest.raises(ValueError, match="unsafe operation"):
        check_operation(root, tmp_path, "rm ../outside")


def test_artifact_title_mismatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import harness.run as runner

    other = replace(PAIR.variants[1], artifacts=lambda root: [Artifact("different title", "body")])
    pair = replace(PAIR, variants=[PAIR.variants[0], other])
    monkeypatch.setattr(runner, "discover_pairs", lambda **kwargs: [pair])
    with pytest.raises(ValueError, match="different artifact titles"):
        run_harness(tmp_path / "out", include_demo=True)


def test_missing_before_fingerprint() -> None:
    missing = Resource("R4", "contents of absent.txt", file_fp("absent.txt"))
    pair = replace(PAIR, inventory=PAIR.inventory + [missing])
    with pytest.raises(ValueError, match="DEMO-1A: R4 fingerprint is None before operation"):
        execute_variant(pair, PAIR.variants[0], {"bash": "bash", "coreutils": "rm", "git": "git", "sqlite": "sqlite"})


def test_prompt_shell_context_and_allocation_total_filter() -> None:
    artifacts = lambda root: [Artifact("$ ls -la sample", "total 8\n-rw-r--r-- 1 user group 1 Jan 1 2026 file\n")]
    variant = replace(PAIR.variants[0], artifacts=artifacts)
    _, item, _, _ = execute_variant(PAIR, variant, {"bash": "bash", "coreutils": "coreutils", "git": "git", "sqlite": "3.40"})
    prompt = item["prompt"]
    assert "total 8" not in prompt
    assert "-rw-r--r--" in prompt
    assert "fresh bash process (no startup files, default shell options, a clean environment" in prompt
    assert "The restore script then runs the same way, in a new bash process" in prompt
    assert "=== Restore script (run afterwards in a new bash process) ===" in prompt
