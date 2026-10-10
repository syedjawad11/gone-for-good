"""Synthetic run checks for the publication analysis."""

import json

from analysis.analyze import analyze, error_tags, outcome


def test_outcome_precedence_and_tags():
    item = {"api_error": "timeout", "raw_response": "", "format_ok": False,
            "item_correct": True}
    assert outcome(item) == "infra"
    del item["api_error"]
    item["raw_response"] = "reply"
    assert outcome(item) == "format"
    item["format_ok"] = True
    assert outcome(item) == "correct"
    item.update(item_correct=False, gold_permanent=True, pred_permanent=False,
                lost_exact=False, rec_exact=True)
    assert outcome(item) == "wrong"
    assert error_tags(item) == ["false_assurance", "lost_wrong"]


def test_synthetic_reports(tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()
    gold_path = tmp_path / "gold.jsonl"
    models_path = tmp_path / "models.json"
    out = tmp_path / "out"
    gold = []
    for pair, family in (("DB-1", "db"), ("FS-1", "fs")):
        for variant in "AB":
            gold.append({"item_id": pair + variant, "pair_id": pair, "family": family,
                         "hops": 3 if pair == "FS-1" and variant == "B" else 2,
                         "changed_fact": "synthetic change " + pair,
                         "lost": ["R1"], "recoverable": [], "permanent_loss": True,
                         "inventory_labels": {"R1": "sample row"}})
    gold_path.write_text("".join(json.dumps(item) + "\n" for item in gold), encoding="utf-8")
    models_path.write_text(json.dumps({"strong": {"display": "Strong", "open_weight": False},
                                      "weak": {"display": "Weak", "open_weight": True}}),
                           encoding="utf-8")

    def record(item, **changes):
        row = {"item_id": item["item_id"], "pair_id": item["pair_id"],
               "family": item["family"], "hops": item["hops"],
               "item_correct": True, "format_ok": True, "format_error": "",
               "raw_response": "{}", "gold_permanent": True, "pred_permanent": True,
               "lost_exact": True, "rec_exact": True, "missed_losses": [],
               "phantom_losses": [], "false_alarm": [], "false_assurance": []}
        row.update(changes)
        return "GFG_ITEM " + json.dumps(row) + "\n"

    strong = [record(gold[0], item_correct=False), record(gold[0])]
    strong += [record(item) for item in gold[1:]]
    weak = [record(gold[0]), record(gold[1], item_correct=False, pred_permanent=False),
            record(gold[2], api_error="rate limit", format_ok=False, item_correct=True),
            record(gold[3], item_correct=False, format_ok=False, format_error="no_json")]
    (logs / "strong.log").write_text("irrelevant line\n" + "".join(strong), encoding="utf-8")
    (logs / "weak.log").write_text("".join(weak), encoding="utf-8")

    summaries = analyze(logs, gold_path, out, models_path)
    assert [s["model"] for s in summaries] == ["strong", "weak"]
    assert summaries[0]["pair_accuracy"] == 1
    assert summaries[1]["pair_accuracy"] == 0
    assert summaries[1]["clean_pair_accuracy"] == 0
    assert summaries[1]["clean_pair_n"] == 1
    assert summaries[1]["clean_item_accuracy"] == 1 / 3
    assert summaries[1]["infra_fails"] == 1
    assert summaries[1]["format_fails"] == 1
    assert summaries[1]["error_tags"]["false_assurance"] == 1
    assert summaries[0]["by_hops"]["3"]["n_pairs"] == 1
    assert "3 (1 pairs)" in (out / "by_hops.md").read_text(encoding="utf-8")
    assert "FS-1A" not in (out / "failures.jsonl").read_text(encoding="utf-8")
    failures = [json.loads(line) for line in (out / "failures.jsonl").read_text().splitlines()]
    assert len(failures) == 2
    assert failures[0]["tags"] == ["false_assurance"]
    leaderboard = (out / "leaderboard.md").read_text(encoding="utf-8")
    assert leaderboard.index("Strong") < leaderboard.index("Weak")
    assert "Strong | no | 1.00 | 1.00" in leaderboard
    for name in ("leaderboard.md", "by_family.md", "by_hops.md", "items_matrix.md",
                 "error_types.md", "failures.jsonl", "summary.json", "leaderboard.png",
                 "by_family.png", "items_heatmap.png"):
        assert (out / name).is_file()
