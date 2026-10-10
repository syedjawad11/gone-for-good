"""Publication charts for the Gone for Good? benchmark."""

import argparse
import json
from pathlib import Path
from statistics import median

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, FancyBboxPatch, Patch

from analysis.analyze import item_sort_key, outcome, read_jsonl, read_log


PALETTE = {
    "text": "#1f2430", "muted": "#6b7280", "grid": "#e5e7eb",
    "closed": "#4c78a8", "open": "#f58518", "bad": "#d64545",
    "correct": "#1b9e77", "wrong": "#d95f02", "infra": "#bdbdbd",
    "format": "#e6ab02", "accent": "#1f6feb",
}
EXCLUDED = "qwen3-next-80b-a3b-thinking"
QWEN_RUN2 = "qwen3-next-80b-a3b-thinking-run2"
GPT = "gpt-5.4-2026-03-05"


def load_summaries(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = [{**record, "model": stem} for stem, record in data.items() if stem != EXCLUDED]
    rows.sort(key=lambda row: (-row["pair_accuracy"], -row["item_accuracy"], row["display"]))
    return rows


def label(row):
    stem = row["model"]
    if stem == QWEN_RUN2:
        return "Qwen3-Next 80B Thinking‡"
    if stem == GPT:
        return "{}†".format(row["display"])
    return row["display"]


def setup_style():
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "text.color": PALETTE["text"],
        "axes.labelcolor": PALETTE["muted"], "xtick.color": PALETTE["muted"],
        "ytick.color": PALETTE["text"], "axes.edgecolor": PALETTE["grid"],
        "figure.facecolor": "white", "savefig.facecolor": "white",
    })


def canvas(title, subtitle, footnote, height=6.5, width=8):
    fig = plt.figure(figsize=(width, height), facecolor="white")
    title_size = 12 if len(title) >= 55 and width == 8 else 17
    fig.text(.055, .955, title, ha="left", va="top", fontsize=title_size,
             fontweight="bold", color=PALETTE["text"])
    fig.text(.055, .9, subtitle, ha="left", va="top", fontsize=9.5,
             color=PALETTE["muted"])
    fig.text(.055, .055, footnote, ha="left", va="bottom", fontsize=7.5,
             color=PALETTE["muted"], linespacing=1.5)
    return fig


def chart_axes(fig, rows, left=.37, right=.91, bottom=.17, top=.82):
    ax = fig.add_axes([left, bottom, right-left, top-bottom])
    ax.set_yticks(range(len(rows)), [label(row) for row in rows], fontsize=8.3)
    ax.set_ylim(len(rows)-.5, -.5)
    ax.tick_params(axis="y", length=0, pad=8)
    ax.tick_params(axis="x", length=0, labelsize=8)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.grid(axis="x", color=PALETTE["grid"], linewidth=.8)
    ax.set_axisbelow(True)
    return ax


def percent_axis(ax, limit=118):
    ax.set_xlim(0, limit)
    ax.set_xticks(range(0, 101, 20), ["{}%".format(n) for n in range(0, 101, 20)])


def save(fig, path):
    fig.savefig(path, dpi=200, facecolor="white")
    plt.close(fig)


def leaderboard(rows, out):
    fig = canvas("From 18 of 18 pairs to 1 of 18",
                 "Pair accuracy: both variants of a matched pair exactly right",
                 "18 matched pairs (36 items), one response per item, temperature 0. Scored in Python, no LLM judge.\n"
                 "† default reasoning config  ‡ run 2, 4 empty replies counted wrong")
    ax = chart_axes(fig, rows, bottom=.19)
    percent_axis(ax, 122)
    for y, row in enumerate(rows):
        value = 100 * row["pair_accuracy"]
        ax.barh(y, value, height=.61, color=PALETTE["open" if row["open_weight"] else "closed"])
        ax.plot(100 * row["item_accuracy"], y, "o", markersize=4.7, color=PALETTE["text"], zorder=4)
        dot = 100 * row["item_accuracy"]
        label_x = max(value + 1.4, dot + 2.8) if value <= dot <= value + 13 else value + 1.4
        ax.text(label_x, y, "{:.0f}%  {}/{}".format(value, row["correct_pairs"], row["n_pairs"]),
                va="center", fontsize=7.5, color=PALETTE["text"])
    handles = [Patch(color=PALETTE["closed"], label="Closed weight"),
               Patch(color=PALETTE["open"], label="Open weight"),
               Line2D([], [], marker="o", linestyle="", color=PALETTE["text"], label="Item accuracy")]
    fig.legend(handles=handles, loc="lower left", bbox_to_anchor=(.37, .125),
               ncol=3, frameon=False, fontsize=7.3, handlelength=1.2, columnspacing=1.1)
    save(fig, out / "01_leaderboard.png")


def false_assurance(rows, out):
    total = sum(row["error_tags"]["false_assurance"] for row in rows)
    bottom_three = sum(row["error_tags"]["false_assurance"] for row in rows[-3:])
    fig = canvas("{} answers said nothing was permanently lost. Data was.".format(total),
                 "Answers claiming no permanent loss on the 22 items where the restore script leaves data unrestored",
                 "Bottom three models: {} of {}. Empty or unparseable replies not counted.".format(bottom_three, total))
    ax = chart_axes(fig, rows)
    ax.set_xlim(0, max(12, max(row["error_tags"]["false_assurance"] for row in rows) + 1.5))
    ax.set_xticks(range(0, 12, 2))
    for y, row in enumerate(rows):
        value = row["error_tags"]["false_assurance"]
        if value:
            ax.barh(y, value, height=.61, color=PALETTE["bad"])
        ax.text(value + .16 if value else .1, y, str(value), va="center", fontsize=8,
                color=PALETTE["text"] if value else PALETTE["muted"])
    save(fig, out / "02_false_assurance.png")
    return total, bottom_three


def same_answer(rows, out):
    qwen = next(row for row in rows if row["model"] == QWEN_RUN2)
    fig = canvas("Same answer to both variants, wrong on at least one",
                 "Pairs where a model gave identical answers to A and B. Gold answers always differ.",
                 "Denominator: pairs where both replies parsed (Qwen: {}).".format(qwen["same_answer_of"]))
    ax = chart_axes(fig, rows)
    percent_axis(ax, 115)
    for y, row in enumerate(rows):
        denominator = row["same_answer_of"]
        value = 100 * row["same_answer_pairs"] / denominator if denominator else 0
        if value:
            ax.barh(y, value, height=.61, color=PALETTE["wrong"])
        ax.text(value + 1.2, y, "{} of {}".format(row["same_answer_pairs"], denominator),
                va="center", fontsize=8, color=PALETTE["text"])
    save(fig, out / "03_same_answer.png")


def by_family(rows, out):
    fig = canvas("SQLite pairs were the hardest", "Pair accuracy by task family",
                 "6 pairs per family. Recovery: archive paths, git stash and checkout, cp -n, set -e,\n"
                 "a hard-linked snapshot. Filesystem: find precedence, git and the index, hard links, dotglob,\n"
                 "cp -r. SQLite: type affinity, name resolution, REPLACE and foreign keys, transactions, triggers.",
                 height=7)
    names = (("Recovery", "recovery"), ("Filesystem", "fs"), ("SQLite", "db"))
    for index, (heading, family) in enumerate(names):
        left = (.34, .56, .78)[index]
        ax = fig.add_axes([left, .2, .185, .58])
        if index == 0:
            ax.set_yticks(range(len(rows)), [label(row) for row in rows], fontsize=8)
        else:
            ax.set_yticks(range(len(rows)), [])
        ax.set_ylim(len(rows)-.5, -.5)
        ax.tick_params(axis="y", length=0, pad=8)
        ax.tick_params(axis="x", length=0, labelsize=7)
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax.grid(axis="x", color=PALETTE["grid"], linewidth=.8)
        ax.set_axisbelow(True)
        ax.set_xlim(0, 135)
        ax.set_xticks((0, 50, 100), ("0", "50", "100%"))
        fig.text(left, .855, heading, fontsize=10, fontweight="bold", color=PALETTE["text"])
        med = median(100 * row["by_family"][family]["accuracy"] for row in rows)
        fig.text(left, .82, "median {:.0f}%".format(med), fontsize=8, color=PALETTE["muted"])
        for y, row in enumerate(rows):
            stats = row["by_family"][family]
            value = 100 * stats["accuracy"]
            if value:
                ax.barh(y, value, height=.61,
                        color=PALETTE["open" if row["open_weight"] else "closed"])
            ax.text(value + 2, y, "{}/{}".format(stats["correct_pairs"], stats["n_pairs"]),
                    va="center", fontsize=6.8, color=PALETTE["text"])
    save(fig, out / "04_by_family.png")


def heatmap(rows, logs, gold, out):
    family_order = {"recovery": 0, "fs": 1, "db": 2}
    gold_items = sorted(read_jsonl(gold), key=lambda item: (family_order[item["family"]], item_sort_key(item)))
    runs = {row["model"]: read_log(logs / (row["model"] + ".log")) for row in rows}
    states = ("correct", "wrong", "infra", "format")
    matrix = np.array([[states.index(outcome(runs[row["model"]][item["item_id"]]))
                        if item["item_id"] in runs[row["model"]] else 2
                        for item in gold_items] for row in rows])
    fig = canvas("Every model on every item", "Exact-match outcomes across the 36 held-out items",
                 "Green = correct; orange = wrong; grey = empty reply; yellow = unparseable.",
                 width=10, height=6.5)
    ax = fig.add_axes([.24, .31, .73, .49])
    ax.imshow(matrix, aspect="auto", interpolation="nearest", vmin=-.5, vmax=3.5,
              cmap=ListedColormap([PALETTE[state] for state in states]))
    ax.set_yticks(range(len(rows)), [label(row) for row in rows], fontsize=8)
    ax.set_xticks(range(len(gold_items)), [item["item_id"] for item in gold_items],
                  rotation=90, fontsize=6.5)
    ax.tick_params(length=0, pad=5)
    ax.spines[:].set_visible(False)
    families = (("Recovery", "recovery"), ("Filesystem", "fs"), ("SQLite", "db"))
    for index, (title, family) in enumerate(families):
        columns = [j for j, item in enumerate(gold_items) if item["family"] == family]
        if not columns:
            raise ValueError("No {} items in gold".format(family))
        ax.text((columns[0] + columns[-1]) / 2, -.85, title, ha="center", va="bottom",
                fontsize=9, fontweight="bold", color=PALETTE["text"])
        if index:
            ax.axvline(columns[0] - .5, color="white", linewidth=3)
    fig.legend(handles=[Patch(facecolor=PALETTE[state], label=title)
                        for state, title in zip(states, ("Correct", "Wrong", "Empty reply", "Unparseable"))],
               loc="lower center", bbox_to_anchor=(.61, .105), ncol=4, frameon=False, fontsize=8)
    save(fig, out / "05_items_heatmap.png")


def cover(out):
    fig = plt.figure(figsize=(10, 4.2), dpi=200, facecolor="#fafbfc")
    ax = fig.add_axes([0, 0, 1, 1], xlim=(0, 2000), ylim=(0, 840))
    ax.set_axis_off()
    ax.set_facecolor("#fafbfc")
    dots_x, dots_y = np.meshgrid(np.arange(80, 1960, 40), np.arange(80, 800, 40))
    ax.scatter(dots_x.ravel(), dots_y.ravel(), s=2, color="#d9dee5", alpha=.5, zorder=0)
    texts = []

    def put(x, y, value, **kwargs):
        text = ax.text(x, y, value, va="center", zorder=5, **kwargs)
        texts.append(text)
        return text

    put(80, 620, "18 of 18", fontsize=34, fontweight="bold", color=PALETTE["accent"])
    put(80, 515, "to 1 of 18", fontsize=34, fontweight="bold", color=PALETTE["text"])
    put(80, 397, "Can AI tell which deleted data", fontsize=19, fontweight="bold", color=PALETTE["text"])
    put(80, 333, "comes back?", fontsize=24, fontweight="bold", color=PALETTE["text"])
    put(80, 230, "A Kaggle benchmark of 10 models · Gone for Good?", fontsize=11,
        color=PALETTE["muted"])

    ax.add_patch(FancyBboxPatch((1020, 163), 910, 536, boxstyle="round,pad=0,rounding_size=26",
                                linewidth=0, facecolor="#e3e7ec", zorder=1))
    ax.add_patch(FancyBboxPatch((1008, 178), 910, 536, boxstyle="round,pad=0,rounding_size=26",
                                linewidth=1, edgecolor="#e5e7eb", facecolor="white", zorder=2))
    ax.plot([1009, 1917], [640, 640], color=PALETTE["grid"], linewidth=1, zorder=3)
    for x, color in ((1050, "#ef6a63"), (1081, "#f2bd4b"), (1112, "#58bd72")):
        ax.add_patch(Circle((x, 678), radius=9, color=color, zorder=4))
    mono = dict(fontfamily="DejaVu Sans Mono", fontsize=11.5)
    put(1042, 589, "$ sha256sum live/ledger.seg snap/ledger.seg", color=PALETTE["text"], **mono)
    put(1042, 532, "f90d93cc…d920  live/ledger.seg", color=PALETTE["muted"], **mono)
    put(1042, 475, "f90d93cc…d920  snap/ledger.seg", color=PALETTE["muted"], **mono)
    put(1042, 390, "$ test -ef live/ledger.seg snap/ledger.seg && echo same-file",
        color=PALETTE["text"], fontfamily="DejaVu Sans Mono", fontsize=8.1)
    ax.add_patch(FancyBboxPatch((1039, 267), 834, 64,
                                boxstyle="round,pad=0,rounding_size=10", linewidth=0,
                                facecolor="#fde8e8", zorder=3))
    put(1058, 299, "same-file", color=PALETTE["bad"], fontweight="bold", **mono)
    ax.add_patch(Circle((1826, 299), radius=16, color=PALETTE["bad"], zorder=4))
    put(1826, 299, "!", color="white", fontsize=14, fontweight="bold", ha="center")
    put(1010, 110, "Matching checksums. Same file. One truncate, both gone.",
        color=PALETTE["muted"], fontsize=11)

    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for text in texts:
        box = text.get_window_extent(renderer=renderer)
        if box.x0 < 60 or box.y0 < 60 or box.x1 > 1940 or box.y1 > 780:
            plt.close(fig)
            raise ValueError("Cover text overflows 60 px margin: {!r}, bbox {}".format(text.get_text(), box.bounds))
        if text.get_position()[0] == 80 and box.x1 > 980:
            plt.close(fig)
            raise ValueError("Cover left text overlaps card: {!r}".format(text.get_text()))
    save(fig, out / "cover.png")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, default=Path("results/analysis/summary.json"))
    parser.add_argument("--logs", type=Path, default=Path("results/kaggle/logs"))
    parser.add_argument("--gold", type=Path, default=Path("data/heldout/gold.jsonl"))
    parser.add_argument("--out", type=Path, default=Path("results/charts"))
    args = parser.parse_args(argv)
    setup_style()
    rows = load_summaries(args.summary)
    args.out.mkdir(parents=True, exist_ok=True)
    leaderboard(rows, args.out)
    false_assurance(rows, args.out)
    same_answer(rows, args.out)
    by_family(rows, args.out)
    heatmap(rows, args.logs, args.gold, args.out)
    cover(args.out)


if __name__ == "__main__":
    main()
