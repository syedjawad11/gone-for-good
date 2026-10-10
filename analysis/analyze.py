"""Deterministic reports and plots from GFG_ITEM Kaggle run records."""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch


COLORS = {
    "correct": "#1b9e77", "wrong": "#d95f02", "infra": "#bdbdbd",
    "format": "#e6ab02", "closed": "#4c78a8", "open": "#f58518",
}
FAMILIES = ("db", "fs", "recovery")
HOPS = (2, 3, 4)
TAGS = ("false_assurance", "false_alarm_perm", "lost_wrong", "rec_wrong")


def read_jsonl(path):
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def read_log(path):
    """A resumed run may repeat an item; the final record is authoritative."""
    items = {}
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.startswith("GFG_ITEM "):
                item = json.loads(line[len("GFG_ITEM "):])
                items[item["item_id"]] = item
    return items


def outcome(item):
    if "api_error" in item or item.get("raw_response") == "":
        return "infra"
    if not item["format_ok"]:
        return "format"
    if item["item_correct"]:
        return "correct"
    return "wrong"


def error_tags(item):
    if outcome(item) != "wrong":
        return []
    tags = []
    if item["gold_permanent"] and not item["pred_permanent"]:
        tags.append("false_assurance")
    if not item["gold_permanent"] and item["pred_permanent"]:
        tags.append("false_alarm_perm")
    if not item["lost_exact"]:
        tags.append("lost_wrong")
    if not item["rec_exact"]:
        tags.append("rec_wrong")
    return tags


def item_sort_key(item):
    pair = item["pair_id"]
    prefix, number = pair.rsplit("-", 1)
    return (FAMILIES.index(item["family"]), prefix, int(number), item["item_id"])


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def format_acc(value):
    return "—" if value is None else "{:.2f}".format(value)


def md_table(headers, rows):
    def escape(value):
        return str(value).replace("|", "\\|").replace("\n", " ")

    return "| " + " | ".join(map(escape, headers)) + " |\n" + (
        "| " + " | ".join("---" for _ in headers) + " |\n"
    ) + "".join("| " + " | ".join(map(escape, row)) + " |\n" for row in rows)


def pair_groups(gold):
    pairs = defaultdict(list)
    for item in gold.values():
        pairs[item["pair_id"]].append(item)
    for pair_id, members in pairs.items():
        if len(members) != 2:
            raise ValueError("Gold pair {} has {} items, expected 2".format(pair_id, len(members)))
        if len({m["family"] for m in members}) != 1:
            raise ValueError("Gold pair {} has inconsistent family".format(pair_id))
    return pairs


def compute_model(stem, items, gold, pairs, metadata):
    unknown = set(items) - set(gold)
    if unknown:
        raise ValueError("{} has unknown items: {}".format(stem, sorted(unknown)))
    classes = {item_id: outcome(item) for item_id, item in items.items()}
    counts = Counter(classes.values())
    correct_pairs = {pair_id for pair_id, members in pairs.items()
                     if all(classes.get(m["item_id"]) == "correct" for m in members)}
    clean_pairs = {pair_id for pair_id, members in pairs.items()
                   if all(classes.get(m["item_id"]) != "infra" for m in members)}
    tags = Counter(tag for item in items.values() for tag in error_tags(item))
    family = {}
    hops = {}
    for name, output in (("family", family), ("hops", hops)):
        for value in (FAMILIES if name == "family" else HOPS):
            subset = {pair_id for pair_id, members in pairs.items()
                      if (members[0]["family"] if name == "family" else
                          max(m["hops"] for m in members)) == value}
            output[str(value)] = {"accuracy": ratio(len(correct_pairs & subset), len(subset)),
                                  "n_pairs": len(subset), "correct_pairs": len(correct_pairs & subset)}
    info = metadata.get(stem, {})
    return {
        "model": stem, "display": info.get("display", stem), "vendor": info.get("vendor"),
        "open_weight": info.get("open_weight"), "note": info.get("note", ""),
        "complete": len(items) == 36, "n_items": len(items), "n_pairs": len(pairs),
        "pair_accuracy": ratio(len(correct_pairs), len(pairs)),
        "item_accuracy": ratio(counts["correct"], len(gold)),
        "clean_pair_accuracy": ratio(len(correct_pairs), len(clean_pairs)),
        "clean_pair_n": len(clean_pairs),
        "clean_item_accuracy": ratio(counts["correct"], len(gold) - counts["infra"]),
        "clean_item_n": len(gold) - counts["infra"],
        "infra_fails": counts["infra"], "format_fails": counts["format"],
        "reasoning_errors": counts["wrong"], "correct_items": counts["correct"],
        "correct_pairs": len(correct_pairs), "error_tags": {tag: tags[tag] for tag in TAGS},
        "by_family": family, "by_hops": hops,
    }


def write_reports(out_dir, summaries, runs, gold, pairs):
    leaderboard_rows = []
    for s in summaries:
        weight = "?" if s["open_weight"] is None else "yes" if s["open_weight"] else "no"
        leaderboard_rows.append((s["display"], weight, format_acc(s["pair_accuracy"]),
                                 format_acc(s["item_accuracy"]), s["infra_fails"],
                                 s["format_fails"], s["reasoning_errors"],
                                 s["error_tags"]["false_assurance"],
                                 "{} ({} pairs)".format(format_acc(s["clean_pair_accuracy"]), s["clean_pair_n"]),
                                 s["note"]))
    (out_dir / "leaderboard.md").write_text(md_table(
        ("Model", "Open weight (yes/no/?)", "Pair acc", "Item acc", "Infra fails",
         "Format fails", "Reasoning errors", "False assurance (items)",
         "Clean pair acc (n pairs)", "Note"), leaderboard_rows), encoding="utf-8")

    for filename, key, values in (("by_family.md", "by_family", FAMILIES),
                                  ("by_hops.md", "by_hops", HOPS)):
        headers = ["Model"] + ["{} ({} pairs)".format(value, sum(
            (members[0]["family"] if key == "by_family" else
             max(m["hops"] for m in members)) == value
            for members in pairs.values())) for value in values]
        rows = [[s["display"]] + [format_acc(s[key][str(value)]["accuracy"]) for value in values]
                for s in summaries]
        (out_dir / filename).write_text(md_table(headers, rows), encoding="utf-8")

    ordered_items = sorted(gold.values(), key=item_sort_key)
    matrix_rows = []
    hard = []
    symbols = {"correct": "✓", "wrong": "✗", "format": "F", "infra": "—"}
    for item in ordered_items:
        item_id = item["item_id"]
        states = [outcome(runs[s["model"]][item_id]) if item_id in runs[s["model"]] else None
                  for s in summaries]
        n_correct = states.count("correct")
        matrix_rows.append([item_id] + [symbols.get(state, "·") for state in states] + [n_correct])
        if n_correct <= 3:
            hard.append((item_id, item["changed_fact"]))
    matrix = md_table(["Item"] + [s["display"] for s in summaries] + ["Models correct"], matrix_rows)
    matrix += "\n## Hardest items\n\n" + md_table(("Item", "Changed fact"), hard)
    (out_dir / "items_matrix.md").write_text(matrix, encoding="utf-8")

    error_rows = [[s["display"]] + [s["error_tags"][tag] for tag in TAGS] for s in summaries]
    error_rows.append(["Total"] + [sum(s["error_tags"][tag] for s in summaries) for tag in TAGS])
    assurance = defaultdict(list)
    for s in summaries:
        for item_id, item in runs[s["model"]].items():
            if "false_assurance" in error_tags(item):
                assurance[item_id].append(s["display"])
    assurance_rows = []
    for item in ordered_items:
        item_id = item["item_id"]
        if item_id in assurance:
            labels = item["inventory_labels"]
            lost = ", ".join("{} ({})".format(rid, labels[rid]) for rid in item["lost"])
            assurance_rows.append((item_id, ", ".join(assurance[item_id]), lost))
    errors = md_table(["Model"] + list(TAGS), error_rows)
    errors += "\n" + md_table(("item_id", "models that said safe", "gold lost ids with labels"), assurance_rows)
    (out_dir / "error_types.md").write_text(errors, encoding="utf-8")

    with (out_dir / "failures.jsonl").open("w", encoding="utf-8") as stream:
        for s in summaries:
            for gold_item in ordered_items:
                item_id = gold_item["item_id"]
                item = runs[s["model"]].get(item_id)
                if item is None or outcome(item) not in ("wrong", "format"):
                    continue
                failure = {"model": s["model"], "item_id": item_id, "class": outcome(item),
                           "tags": error_tags(item), "gold_lost": gold_item["lost"],
                           "gold_recoverable": gold_item["recoverable"],
                           "gold_permanent_loss": gold_item["permanent_loss"],
                           "raw_response": item.get("raw_response", "")[:2000]}
                stream.write(json.dumps(failure, ensure_ascii=False) + "\n")
    (out_dir / "summary.json").write_text(json.dumps(
        {s["model"]: s for s in summaries}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return ordered_items


def save_plot(fig, path):
    fig.patch.set_facecolor("white")
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def write_plots(out_dir, summaries, runs, ordered_items):
    names = [s["display"] for s in summaries]
    positions = list(range(len(summaries)))
    fig, ax = plt.subplots(figsize=(9, max(4, len(summaries) * .42 + 1.5)))
    for y, s in enumerate(summaries):
        bar = ax.barh(y, s["pair_accuracy"] or 0,
                      color=COLORS["open" if s["open_weight"] else "closed"], height=.65)
        if s["open_weight"]:
            bar[0].set_hatch("//")
        ax.plot(s["item_accuracy"], y, "o", color="black", markersize=5)
    ax.set_yticks(positions, names)
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.set_xlabel("Accuracy")
    ax.legend(handles=[Patch(facecolor=COLORS["closed"], label="Closed weight"),
                       Patch(facecolor=COLORS["open"], hatch="//", label="Open weight"),
                       plt.Line2D([], [], marker="o", linestyle="", color="black", label="Item accuracy")],
              loc="lower right", fontsize=8)
    ax.grid(axis="x", alpha=.2)
    ax.set_axisbelow(True)
    fig.tight_layout()
    save_plot(fig, out_dir / "leaderboard.png")

    fig, ax = plt.subplots(figsize=(9, max(4, len(summaries) * .55 + 1.5)))
    for index, (family, color) in enumerate(zip(FAMILIES,
                                                (COLORS["closed"], COLORS["open"], COLORS["correct"]))):
        ys = [y + (index - 1) * .23 for y in positions]
        ax.barh(ys, [s["by_family"][family]["accuracy"] or 0 for s in summaries],
                height=.21, color=color, label=family)
    ax.set_yticks(positions, names)
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.set_xlabel("Pair accuracy")
    ax.legend(loc="lower right", fontsize=8)
    ax.grid(axis="x", alpha=.2)
    ax.set_axisbelow(True)
    fig.tight_layout()
    save_plot(fig, out_dir / "by_family.png")

    state_index = {"correct": 0, "wrong": 1, "infra": 2, "format": 3}
    grid = [[state_index[outcome(runs[s["model"]][item["item_id"]])]
             if item["item_id"] in runs[s["model"]] else 2 for item in ordered_items]
            for s in summaries]
    fig, ax = plt.subplots(figsize=(max(11, len(ordered_items) * .36), max(4.5, len(summaries) * .48 + 1.5)))
    ax.imshow(grid, aspect="auto", interpolation="nearest", vmin=-.5, vmax=3.5,
              cmap=ListedColormap([COLORS[key] for key in ("correct", "wrong", "infra", "format")]))
    ax.set_yticks(positions, names)
    ax.set_xticks(range(len(ordered_items)), [i["item_id"] for i in ordered_items], rotation=90, fontsize=7)
    previous = None
    starts = []
    for index, item in enumerate(ordered_items):
        if item["family"] != previous:
            starts.append((index, item["family"]))
            if index:
                ax.axvline(index - .5, color="black", linewidth=1.5)
            previous = item["family"]
    for index, (start, family) in enumerate(starts):
        end = starts[index + 1][0] if index + 1 < len(starts) else len(ordered_items)
        ax.text((start + end - 1) / 2, -.9, family, ha="center", va="bottom", fontsize=9)
    ax.legend(handles=[Patch(facecolor=COLORS[key], label=key) for key in
                       ("correct", "wrong", "infra", "format")],
              loc="upper center", bbox_to_anchor=(.5, -.19), ncol=4, fontsize=8)
    fig.subplots_adjust(left=.18, right=.99, top=.89, bottom=.24)
    save_plot(fig, out_dir / "items_heatmap.png")


def analyze(logs, gold_path, out_dir, models_path):
    gold_rows = read_jsonl(gold_path)
    gold = {item["item_id"]: item for item in gold_rows}
    if len(gold) != len(gold_rows):
        raise ValueError("Duplicate item_id in gold")
    pairs = pair_groups(gold)
    metadata = json.loads(models_path.read_text(encoding="utf-8"))
    runs = {path.stem: read_log(path) for path in sorted(logs.glob("*.log"))}
    if not runs:
        raise ValueError("No .log files in {}".format(logs))
    summaries = [compute_model(stem, items, gold, pairs, metadata) for stem, items in runs.items()]
    summaries.sort(key=lambda s: (-(s["pair_accuracy"] or 0), -(s["item_accuracy"] or 0), s["display"]))
    out_dir.mkdir(parents=True, exist_ok=True)
    ordered_items = write_reports(out_dir, summaries, runs, gold, pairs)
    write_plots(out_dir, summaries, runs, ordered_items)
    return summaries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--logs", type=Path, default=Path("results/kaggle/logs"))
    parser.add_argument("--gold", type=Path, default=Path("data/heldout/gold.jsonl"))
    parser.add_argument("--out", type=Path, default=Path("results/analysis"))
    parser.add_argument("--models", type=Path, default=Path("analysis/models.json"))
    args = parser.parse_args()
    analyze(args.logs, args.gold, args.out, args.models)


if __name__ == "__main__":
    main()
