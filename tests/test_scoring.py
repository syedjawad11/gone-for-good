import json
import sys
from pathlib import Path

import pytest

from scoring import aggregate, baseline_text, bootstrap, parse_answer, score_item


DATA = Path(__file__).parent / "data"


def read(name):
    return [json.loads(line) for line in (DATA / name).read_text().splitlines()]


GOLD = read("mini_gold.jsonl")
ITEMS = read("mini_items.jsonl")


def answer(gold):
    return json.dumps({"lost": gold["lost"], "recoverable": gold["recoverable"],
                       "permanent_loss": gold["permanent_loss"]})


def test_parse_wrappers_and_normalization():
    ids = ["R1", "R2"]
    for text in ('```json\n{"lost":["r1"],"recoverable":[],"permanent_loss":true}\n```',
                 'Earlier {bad} then {"lost":["r1"],"recoverable":[],"permanent_loss":true} trailing',
                 '{"lost":["R2"],"recoverable":[],"permanent_loss":false} '
                 '{"lost":["r1"],"recoverable":[],"permanent_loss":true}'):
        parsed = parse_answer(text, ids)
        assert parsed.ok and parsed.lost == ("R1",)


@pytest.mark.parametrize("text,error", [
    ("plain", "no_json"), ("{oops}", "bad_json"),
    ('{"lost":[],"recoverable":[]}', "missing_key"),
    ('{"lost":"R1","recoverable":[],"permanent_loss":false}', "bad_type"),
    ('{"lost":["R9"],"recoverable":[],"permanent_loss":true}', "unknown_id"),
    ('{"lost":["R1","r1"],"recoverable":[],"permanent_loss":true}', "duplicate_id"),
    ('{"lost":[],"recoverable":["R1"],"permanent_loss":false}', "not_subset"),
])
def test_parse_errors(text, error):
    assert parse_answer(text, ["R1"]).error == error


def test_perfect_and_one_wrong_variant():
    rows = [score_item(answer(g), g) for g in GOLD]
    perfect = aggregate(rows)
    assert perfect["item_acc"] == perfect["pair_acc"] == perfect["lost_acc"] == perfect["rec_acc"] == 1
    assert perfect["format_failure_rate"] == perfect["perm_flag_inconsistency_rate"] == 0
    rows[1] = score_item(answer(GOLD[0]), GOLD[1])
    summary = aggregate(rows)
    assert summary["item_acc"] == pytest.approx(5 / 6)
    assert summary["pair_acc"] == pytest.approx(2 / 3)
    assert summary["coupling_miss"] == 1
    rows[2] = score_item("garbage", GOLD[2])
    assert aggregate(rows)["format_failure_rate"] == pytest.approx(1 / 6)
    assert not rows[2]["lost_exact"] and not rows[2]["rec_exact"]


def test_permanent_and_error_details():
    row = score_item('{"lost":["R1"],"recoverable":["R1"],"permanent_loss":true}', GOLD[1])
    assert row["false_assurance"] == ["R1"]
    assert not row["pred_permanent"] and not row["perm_flag_consistent"]
    assert row["missed_permanent"]
    bad = score_item("no JSON", GOLD[1])
    assert bad["missed_permanent"] and not bad["item_correct"]


@pytest.mark.parametrize("name,item_acc,pair_acc,lost_acc,rec_acc", [
    ("everything_lost", 0, 0, 0, 3 / 6),
    ("nothing_lost", 1 / 6, 0, 1 / 6, 3 / 6),
    ("naive_reader", 1 / 6, 0, 2 / 6, 4 / 6),
])
def test_frozen_baselines(name, item_acc, pair_acc, lost_acc, rec_acc):
    rows = [score_item(baseline_text(name, g, i), g) for g, i in zip(GOLD, ITEMS)]
    summary = aggregate(rows)
    assert summary["item_acc"] == pytest.approx(item_acc)
    assert summary["pair_acc"] == pytest.approx(pair_acc)
    assert summary["lost_acc"] == pytest.approx(lost_acc)
    assert summary["rec_acc"] == pytest.approx(rec_acc)


def test_bootstrap_paired_and_seeded():
    perfect = [score_item(answer(g), g) for g in GOLD]
    fail_p1 = [score_item("garbage" if g["pair_id"] == "P1" else answer(g), g) for g in GOLD]
    samples = {"perfect": perfect, "partial": fail_p1}
    first = bootstrap(samples, n_boot=100, seed=5)
    assert first == bootstrap(samples, n_boot=100, seed=5)
    assert first["models"]["perfect"]["pair_acc"] == [1, 1]
    assert first["models"]["partial"]["pair_acc"] == first["models"]["partial"]["item_acc"]
    assert first["pairwise_pair_acc_diff"]["perfect - partial"][0] >= 0


def test_missing_variant_counts_wrong_and_duplicate_rejected():
    rows = [score_item(answer(g), g) for g in GOLD]
    summary = aggregate(rows[:-1], expected_items=GOLD)
    assert summary["n_items"] == 6
    assert summary["pair_acc"] == pytest.approx(2 / 3)
    with pytest.raises(ValueError, match="duplicate item_id"):
        aggregate(rows + [rows[0]])
    with pytest.raises(ValueError, match="duplicate item_id"):
        bootstrap({"model": rows + [rows[0]]}, n_boot=2)
    with pytest.raises(ValueError, match="same item IDs"):
        bootstrap({"full": rows, "partial": rows[:-1]}, n_boot=2)


def test_cli_writes_bootstrap_for_answer_models(tmp_path, monkeypatch, capsys):
    from scoring import main
    answers = tmp_path / "answers.jsonl"
    answers.write_text("".join(json.dumps({"model": "stub", "item_id": g["item_id"],
                                           "response": answer(g)}) + "\n" for g in GOLD))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["scoring.py", "--gold", str(DATA / "mini_gold.jsonl"),
                                      "--items", str(DATA / "mini_items.jsonl"),
                                      "--answers", str(answers)])
    main()
    output = json.loads((tmp_path / "results/scores.json").read_text())
    assert output["bootstrap"]["models"]["stub"]["pair_acc"] == [1, 1]
    assert "stub pair_acc 95% CI" in capsys.readouterr().out
