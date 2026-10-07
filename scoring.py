"""Deterministic scoring for Gone for Good? (Python 3.9+, standard library)."""

import argparse
import json
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ParseResult:
    ok: bool
    error: str = ""
    lost: tuple = ()
    recoverable: tuple = ()
    permanent_loss: bool = False


def _objects(text):
    """Yield balanced outer brace spans, respecting JSON string escapes."""
    depth = 0
    start = None
    quoted = False
    escaped = False
    for index, char in enumerate(text):
        if depth == 0:
            if char == "{":
                start, depth = index, 1
            continue
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                yield text[start:index + 1]


def parse_answer(text, inventory_ids):
    candidates = list(_objects(text if isinstance(text, str) else ""))
    if not candidates:
        return ParseResult(False, "no_json" if "{" not in str(text) else "bad_json")
    obj = None
    for candidate in reversed(candidates):
        try:
            value = json.loads(candidate)
        except (ValueError, TypeError):
            continue
        if isinstance(value, dict):
            obj = value
            break
    if obj is None:
        return ParseResult(False, "bad_json")
    if not all(key in obj for key in ("lost", "recoverable", "permanent_loss")):
        return ParseResult(False, "missing_key")
    if (not isinstance(obj["lost"], list) or not isinstance(obj["recoverable"], list)
            or type(obj["permanent_loss"]) is not bool
            or any(not isinstance(i, str) for key in ("lost", "recoverable") for i in obj[key])):
        return ParseResult(False, "bad_type")
    lost = [i.upper() for i in obj["lost"]]
    rec = [i.upper() for i in obj["recoverable"]]
    allowed = {str(i).upper() for i in inventory_ids}
    if any(i not in allowed for i in lost + rec):
        return ParseResult(False, "unknown_id")
    if len(set(lost)) != len(lost) or len(set(rec)) != len(rec):
        return ParseResult(False, "duplicate_id")
    if not set(rec) <= set(lost):
        return ParseResult(False, "not_subset")
    return ParseResult(True, "", tuple(sorted(lost)), tuple(sorted(rec)), obj["permanent_loss"])


def score_item(text, gold):
    gold_lost = {i.upper() for i in gold["lost"]}
    gold_rec = {i.upper() for i in gold["recoverable"]}
    parsed = parse_answer(text, gold["inventory_labels"])
    pred_lost = set(parsed.lost) if parsed.ok else set()
    pred_rec = set(parsed.recoverable) if parsed.ok else set()
    gold_perm = bool(gold_lost - gold_rec)
    pred_perm = bool(pred_lost - pred_rec)
    return {
        "item_id": gold["item_id"], "pair_id": gold["pair_id"],
        "family": gold["family"], "hops": gold["hops"],
        "format_ok": parsed.ok, "format_error": parsed.error,
        "lost_exact": parsed.ok and pred_lost == gold_lost,
        "rec_exact": parsed.ok and pred_rec == gold_rec,
        "item_correct": parsed.ok and pred_lost == gold_lost and pred_rec == gold_rec,
        "missed_losses": sorted(gold_lost - pred_lost),
        "phantom_losses": sorted(pred_lost - gold_lost),
        "false_assurance": sorted(pred_rec & (gold_lost - gold_rec)),
        "false_alarm": sorted(gold_rec - pred_rec),
        "gold_permanent": gold_perm, "pred_permanent": pred_perm,
        "perm_flag_consistent": parsed.ok and parsed.permanent_loss == pred_perm,
        "missed_permanent": gold_perm and not pred_perm,
    }


def _summary(rows):
    n = len(rows)
    pairs = defaultdict(list)
    for row in rows:
        pairs[row["pair_id"]].append(row)
    pair_values = [all(r["item_correct"] for r in group) for group in pairs.values()]
    permanent = [r for r in rows if r["gold_permanent"]]
    return {
        "n_items": n, "n_pairs": len(pairs),
        "item_acc": sum(r["item_correct"] for r in rows) / n if n else 0.0,
        "pair_acc": sum(pair_values) / len(pairs) if pairs else 0.0,
        "lost_acc": sum(r["lost_exact"] for r in rows) / n if n else 0.0,
        "rec_acc": sum(r["rec_exact"] for r in rows) / n if n else 0.0,
        "format_failure_rate": sum(not r["format_ok"] for r in rows) / n if n else 0.0,
        "perm_flag_inconsistency_rate": sum(not r["perm_flag_consistent"] for r in rows) / n if n else 0.0,
        "false_assurance": {"items_with_any": sum(bool(r["false_assurance"]) for r in rows), "of": n},
        "missed_permanent": {"k": sum(r["missed_permanent"] for r in rows), "of": len(permanent)},
        "coupling_miss": sum(any(r["item_correct"] for r in group) and
                             not all(r["item_correct"] for r in group) for group in pairs.values()),
    }


def aggregate(rows, expected_items=None):
    rows = list(rows)
    seen = set()
    for row in rows:
        if row["item_id"] in seen:
            raise ValueError("duplicate item_id: " + row["item_id"])
        seen.add(row["item_id"])
    if expected_items is not None:
        expected = list(expected_items)
        expected_ids = set()
        for gold in expected:
            item_id = gold["item_id"]
            if item_id in expected_ids:
                raise ValueError("duplicate expected item_id: " + item_id)
            expected_ids.add(item_id)
        if seen - expected_ids:
            raise ValueError("unexpected item IDs: " + repr(sorted(seen - expected_ids)))
        for gold in expected:
            if gold["item_id"] not in seen:
                missing = score_item("", gold)
                missing["format_error"] = "missing"
                rows.append(missing)
    result = _summary(rows)
    for field, output in (("family", "by_family"), ("hops", "by_hops")):
        groups = defaultdict(list)
        for row in rows:
            groups[row[field]].append(row)
        result[output] = {key: {k: _summary(group)[k] for k in
                         ("n_items", "n_pairs", "item_acc", "pair_acc")}
                          for key, group in groups.items()}
    return result


def _percentile(values, fraction):
    values = sorted(values)
    if not values:
        return 0.0
    position = (len(values) - 1) * fraction
    lower = int(position)
    weight = position - lower
    return values[lower] * (1 - weight) + values[min(lower + 1, len(values) - 1)] * weight


def bootstrap(rows_by_model, n_boot=2000, seed=0):
    """Paired, pair-cluster bootstrap. All models must cover identical items."""
    grouped = {}
    item_sets = {}
    for model, rows in rows_by_model.items():
        pairs = defaultdict(list)
        seen = set()
        for row in rows:
            if row["item_id"] in seen:
                raise ValueError("duplicate item_id: " + row["item_id"])
            seen.add(row["item_id"])
            pairs[row["pair_id"]].append(row)
        grouped[model] = pairs
        item_sets[model] = seen
    models = list(grouped)
    ids = sorted(grouped[models[0]]) if models else []
    if any(item_sets[m] != item_sets[models[0]] for m in models):
        raise ValueError("models must contain the same item IDs")
    if any(set(grouped[m]) != set(ids) for m in models):
        raise ValueError("models must contain the same pair IDs")
    draws = {m: {"pair_acc": [], "item_acc": []} for m in models}
    differences = {a + " - " + b: [] for i, a in enumerate(models) for b in models[i + 1:]}
    rng = random.Random(seed)
    for _ in range(n_boot):
        sampled = [rng.choice(ids) for _ in ids]
        scores = {}
        for model in models:
            groups = [grouped[model][pair] for pair in sampled]
            flat = [row for group in groups for row in group]
            scores[model] = (sum(all(r["item_correct"] for r in group) for group in groups) / len(groups)
                             if groups else 0.0)
            draws[model]["pair_acc"].append(scores[model])
            draws[model]["item_acc"].append(sum(r["item_correct"] for r in flat) / len(flat) if flat else 0.0)
        for i, a in enumerate(models):
            for b in models[i + 1:]:
                differences[a + " - " + b].append(scores[a] - scores[b])
    return {"models": {m: {metric: [_percentile(v, .025), _percentile(v, .975)]
                            for metric, v in metrics.items()} for m, metrics in draws.items()},
            "pairwise_pair_acc_diff": {k: [_percentile(v, .025), _percentile(v, .975)]
                                       for k, v in differences.items()}}


def baseline_text(name, gold, item):
    ids = [str(i).upper() for i in item["inventory_ids"]]
    if name == "everything_lost":
        lost, rec = ids, []
    elif name == "nothing_lost":
        lost, rec = [], []
    elif name == "naive_reader":
        lost = [str(i).upper() for i in gold["literal_targets"]]
        rec = lost if "backup" in item["prompt"].lower() else []
    else:
        raise ValueError("unknown baseline: " + name)
    return json.dumps({"lost": lost, "recoverable": rec,
                       "permanent_loss": bool(set(lost) - set(rec))})


def _read_jsonl(path):
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", default="data/gold.jsonl")
    parser.add_argument("--items", default="data/items.jsonl")
    parser.add_argument("--answers")
    args = parser.parse_args()
    gold = _read_jsonl(args.gold)
    items = {row["item_id"]: row for row in _read_jsonl(args.items)}
    answers = defaultdict(dict)
    if args.answers:
        for answer in _read_jsonl(args.answers):
            answers[answer["model"]][answer["item_id"]] = answer["response"]
    summaries = {}
    answer_rows = {}
    names = list(answers) + ["everything_lost", "nothing_lost", "naive_reader"]
    print("model item_acc pair_acc lost_acc rec_acc format_fail missed_permanent")
    for name in names:
        rows = []
        for label in gold:
            item = items[label["item_id"]]
            response = (baseline_text(name, label, item) if name in
                        ("everything_lost", "nothing_lost", "naive_reader") else
                        answers[name].get(label["item_id"]))
            row = score_item(response or "", label)
            if response is None:
                row["format_error"] = "missing"
            rows.append(row)
        summaries[name] = aggregate(rows, expected_items=gold)
        if name in answers:
            answer_rows[name] = rows
        s = summaries[name]
        mp = s["missed_permanent"]
        print("{} {:.3f} {:.3f} {:.3f} {:.3f} {:.3f} {}/{}".format(
            name, s["item_acc"], s["pair_acc"], s["lost_acc"], s["rec_acc"],
            s["format_failure_rate"], mp["k"], mp["of"]))
    if answer_rows:
        intervals = bootstrap(answer_rows)
        summaries["bootstrap"] = intervals
        for name in answer_rows:
            low, high = intervals["models"][name]["pair_acc"]
            print("{} pair_acc 95% CI [{:.3f}, {:.3f}]".format(name, low, high))
    output = Path("results/scores.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summaries, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
