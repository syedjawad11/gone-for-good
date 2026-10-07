"""Execute authored fixtures in disposable roots and freeze observed labels.

The operation guard is deliberately best-effort string validation, not a shell
parser or a security boundary. Run only reviewed, repository-owned fixtures.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from fixtures.base import home_for, FIXED_EPOCH, Artifact, Pair, Variant, env_for
from harness.render import render_prompt


def discover_pairs(include_demo: bool = False, families: set[str] | None = None) -> list[Pair]:
    base = Path(__file__).resolve().parent.parent / "fixtures"
    pairs = []
    seen = set()
    for family_dir in sorted(base.iterdir()):
        if not family_dir.is_dir() or family_dir.name.startswith("_"):
            continue
        if family_dir.name == "demo" and not include_demo:
            continue
        if families is not None and family_dir.name not in families:
            continue
        for path in sorted(family_dir.glob("*.py")):
            if path.name == "__init__.py":
                continue
            module = importlib.import_module(f"fixtures.{family_dir.name}.{path.stem}")
            if not hasattr(module, "PAIR"):
                continue
            pair = module.PAIR
            if pair.family != family_dir.name:
                raise ValueError(f"{pair.pair_id}: family differs from directory {family_dir.name}")
            if pair.pair_id in seen:
                raise ValueError(f"duplicate pair_id: {pair.pair_id}")
            seen.add(pair.pair_id)
            validate_pair(pair)
            pairs.append(pair)
    return pairs


def validate_pair(pair: Pair) -> None:
    ids = [r.id for r in pair.inventory]
    if ids != [f"R{i}" for i in range(1, len(ids) + 1)]:
        raise ValueError(f"{pair.pair_id}: inventory ids must be unique and ordered R1..Rn")
    if not set(pair.literal_targets) <= set(ids):
        raise ValueError(f"{pair.pair_id}: literal_targets outside inventory")
    letters = [v.variant for v in pair.variants]
    if len(letters) != len(set(letters)):
        raise ValueError(f"{pair.pair_id}: duplicate variant letter")
    if not 6 <= len(ids) <= 12:
        message = f"{pair.pair_id}: inventory has {len(ids)} resources; expected 6..12"
        if pair.family == "demo":
            print(f"warning: {message}", file=sys.stderr)
        else:
            raise ValueError(message)


def check_operation(root: Path, tmp: Path, operation: str) -> None:
    temp_base = Path(tempfile.gettempdir()).resolve()
    if not tmp.resolve().is_relative_to(temp_base) or tmp.resolve() == temp_base:
        raise ValueError("sandbox directory is outside the system temporary directory")
    if not root.resolve().is_relative_to(tmp.resolve()) or root.resolve() == tmp.resolve():
        raise ValueError("project root is outside its sandbox directory")
    if ".." in operation or "~" in operation:
        raise ValueError("unsafe operation: '..' or '~' is forbidden")
    # Best effort: recognize literal absolute shell words, including quoted words.
    for match in re.finditer(r"(?<![\w.])/[A-Za-z0-9_./-]+", operation):
        candidate = Path(match.group())
        if str(candidate) == "/dev/null":
            continue
        if not candidate.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"unsafe operation: absolute path outside sandbox: {candidate}")


def set_fixed_mtimes(root: Path) -> None:
    paths = list(root.rglob("*")) + [root]
    for path in sorted(paths, key=lambda p: len(p.parts), reverse=True):
        os.utime(path, (FIXED_EPOCH, FIXED_EPOCH), follow_symlinks=False)
    # `ls -la` shows the parent as `..`; pin it too so no wall-clock date leaks into prompts.
    home_for(root)  # create HOME (beside root) now, so creating it later can't touch the parent
    os.utime(root.parent, (FIXED_EPOCH, FIXED_EPOCH))


def tool_versions() -> dict[str, str]:
    commands = {
        "bash": ["bash", "--version"],
        "coreutils": ["rm", "--version"],
        "git": ["git", "--version"],
        "sqlite": ["sqlite3", "--version"],
        "python": ["python3", "--version"],
        "uname": ["uname", "-sm"],
    }
    found = {}
    for name, command in commands.items():
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=5)
            value = result.stdout.strip() or result.stderr.strip()
            if result.returncode != 0 or not value:
                value = "missing"
            else:
                value = value.splitlines()[0]
                if name == "sqlite":
                    value = value.split(" ")[0]
            found[name] = value
        except (FileNotFoundError, subprocess.TimeoutExpired):
            found[name] = "missing"
    return found


def _run_script(root: Path, script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "--noprofile", "--norc", "-c", script], cwd=root,
        env=env_for(root), capture_output=True, text=True, timeout=30,
    )


def execute_variant(pair: Pair, variant: Variant, versions: dict[str, str]) -> tuple[dict, dict, list[str], int]:
    tmp = Path(tempfile.mkdtemp(prefix="gfg-"))
    root = tmp / "project"
    try:
        root.mkdir()
        check_operation(root, tmp, pair.operation)
        check_operation(root, tmp, pair.restore_script)
        variant.build(root)
        set_fixed_mtimes(root)
        artifacts = variant.artifacts(root)
        # Directory allocation totals vary with filesystem layout and leak size cues.
        artifacts = [Artifact(a.title, "\n".join(line for line in a.body.split("\n")
                                            if not re.fullmatch(r"total \d+", line)))
                     for a in artifacts]
        before = {r.id: r.fingerprint(root) for r in pair.inventory}
        for resource_id, fingerprint in before.items():
            if fingerprint is None:
                raise ValueError(f"{pair.pair_id}{variant.variant}: {resource_id} fingerprint is None before operation")
        op = _run_script(root, pair.operation)
        after = {r.id: r.fingerprint(root) for r in pair.inventory}
        lost = sorted(rid for rid in before if after[rid] != before[rid])
        restore = _run_script(root, pair.restore_script)
        restored = {r.id: r.fingerprint(root) for r in pair.inventory}
        recoverable = sorted(rid for rid in lost if restored[rid] == before[rid])
        item_id = f"{pair.pair_id}{variant.variant}"
        gold = {
            "item_id": item_id, "pair_id": pair.pair_id, "variant": variant.variant,
            "family": pair.family, "hops": variant.hops, "changed_fact": pair.changed_fact,
            "literal_targets": pair.literal_targets,
            "inventory_labels": {r.id: r.label for r in pair.inventory},
            "lost": lost, "recoverable": recoverable,
            "permanent_loss": bool(set(lost) - set(recoverable)),
            "op_exit_code": op.returncode, "op_stderr": op.stderr.replace(str(root), "<root>").replace(str(tmp), "<sandbox>"),
            "restore_exit_code": restore.returncode,
            "restore_stderr": restore.stderr.replace(str(root), "<root>").replace(str(tmp), "<sandbox>"),
            "tool_versions": versions,
        }
        prompt = render_prompt(pair, artifacts, versions)
        if str(tmp) in prompt or str(root) in prompt:
            raise ValueError(f"{item_id}: prompt contains a temporary path")
        item = {
            "item_id": item_id, "pair_id": pair.pair_id, "variant": variant.variant,
            "family": pair.family, "hops": variant.hops, "inventory_ids": [r.id for r in pair.inventory],
            "prompt": prompt,
        }
        total_body_len = sum(len(a.body) for a in artifacts)
        return gold, item, [a.title for a in artifacts], total_body_len
    finally:
        shutil.rmtree(tmp)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in sorted(rows, key=lambda r: r["item_id"]):
            stream.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")


def run_harness(out: Path, only: set[str] | None = None, families: set[str] | None = None,
                include_demo: bool = False) -> tuple[list[dict], list[dict]]:
    pairs = discover_pairs(include_demo=include_demo, families=families)
    if only is not None:
        pairs = [p for p in pairs if p.pair_id in only]
    versions = tool_versions()
    gold_rows, item_rows, tell_lines, mismatch_lines = [], [], [], []
    for pair in pairs:
        titles = None
        lengths = []
        for variant in pair.variants:
            gold, item, current_titles, length = execute_variant(pair, variant, versions)
            if titles is not None and current_titles != titles:
                raise ValueError(f"{pair.pair_id}: variants return different artifact titles or order")
            titles = current_titles
            lengths.append(length)
            gold_rows.append(gold)
            item_rows.append(item)
            expected = pair.expected.get(variant.variant)
            if expected is not None and (gold["lost"] != sorted(expected["lost"]) or
                                         gold["recoverable"] != sorted(expected["recoverable"])):
                mismatch_lines.append(f"{gold['item_id']}: expected {json.dumps(expected, sort_keys=True)}; executed lost={gold['lost']} recoverable={gold['recoverable']}")
        shortest = min(lengths) if lengths else 0
        ratio = max(lengths) / shortest if shortest else (1.0 if not lengths or max(lengths) == 0 else float("inf"))
        tell_lines.append(f"{pair.pair_id}: longest/shortest artifact body chars = {ratio:.3f}\n")
    out.mkdir(parents=True, exist_ok=True)
    _write_jsonl(out / "gold.jsonl", gold_rows)
    _write_jsonl(out / "items.jsonl", item_rows)
    (out / "tell_report.txt").write_text("".join(sorted(tell_lines)), encoding="utf-8")
    (out / "expected_mismatches.txt").write_text("\n".join(sorted(mismatch_lines)) + ("\n" if mismatch_lines else ""), encoding="utf-8")
    if mismatch_lines:
        print(f"{len(mismatch_lines)} expected label mismatch(es); see {out / 'expected_mismatches.txt'}", file=sys.stderr)
    return gold_rows, item_rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="comma-separated pair IDs")
    parser.add_argument("--families", help="comma-separated fixture families")
    parser.add_argument("--out", type=Path, default=Path("data"))
    parser.add_argument("--include-demo", action="store_true")
    args = parser.parse_args()
    run_harness(args.out, set(args.only.split(",")) if args.only else None,
                set(args.families.split(",")) if args.families else None, args.include_demo)


if __name__ == "__main__":
    main()
