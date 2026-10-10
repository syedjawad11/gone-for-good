"""Render checks for the publication charts."""

from pathlib import Path

from PIL import Image

from analysis.charts import EXCLUDED, false_assurance, load_summaries, main


ROOT = Path(__file__).resolve().parents[1]
FILES = (
    "01_leaderboard.png", "02_false_assurance.png", "03_same_answer.png",
    "04_by_family.png", "05_items_heatmap.png", "cover.png",
)


def test_publication_charts(tmp_path):
    rows = load_summaries(ROOT / "results/analysis/summary.json")
    assert len(rows) == 10
    assert EXCLUDED not in {row["model"] for row in rows}
    assert sum(row["error_tags"]["false_assurance"] for row in rows) == 25
    assert sum(row["error_tags"]["false_assurance"] for row in rows[-3:]) == 22
    assert false_assurance(rows, tmp_path) == (25, 22)

    main(["--summary", str(ROOT / "results/analysis/summary.json"),
          "--logs", str(ROOT / "results/kaggle/logs"),
          "--gold", str(ROOT / "data/heldout/gold.jsonl"),
          "--out", str(tmp_path)])
    for name in FILES:
        with Image.open(tmp_path / name) as image:
            assert image.format == "PNG"
            assert image.size == ((2000, 840) if name == "cover.png" else
                                  (2000, 1300) if name == "05_items_heatmap.png" else
                                  (1600, 1400) if name == "04_by_family.png" else (1600, 1300))
