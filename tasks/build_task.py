"""Build a self-contained Kaggle task from frozen JSONL inputs."""

import argparse
import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_jsonl(path):
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def build_task(gold_path, items_path, out_path, name="gone-for-good"):
    display_name = name
    gold = {row["item_id"]: row for row in read_jsonl(gold_path)}
    items = read_jsonl(items_path)
    if set(gold) != {row["item_id"] for row in items}:
        raise ValueError("gold and item IDs differ")
    records = []
    for item in items:
        label = gold[item["item_id"]]
        records.append({
            "item": {"prompt": item["prompt"]},
            "gold": {key: label[key] for key in ("item_id", "pair_id", "family", "hops", "inventory_labels", "lost", "recoverable")},
        })
    source = (ROOT / "scoring.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    cli_line = next(node.lineno for node in tree.body if isinstance(node, ast.If)
                    and isinstance(node.test, ast.Compare)
                    and isinstance(node.test.left, ast.Name)
                    and node.test.left.id == "__name__")
    source = "".join(source.splitlines(keepends=True)[:cli_line - 1])
    # The scoring CLI and its imports remain dormant inside the generated task.
    embedded = json.dumps(records, ensure_ascii=False, sort_keys=True)
    task = (
        "# %%\n" + source + "\n# %%\nimport kaggle_benchmarks as kbench\n\n"
        + "RECORDS = json.loads(" + repr(embedded) + ")\n\n"
        + "# %%\n@kbench.task(name=\"gfg-item\", store_task=False)\n"
        + "def gfg_item(llm, record) -> dict:\n"
        + "    cap_key = 'max_output_tokens' if type(llm).__name__ == 'GoogleGenAI' else 'max_tokens'\n"
        + "    response = llm.prompt(record['item']['prompt'], temperature=0, "
          "extra_api_params={cap_key: 1024})\n"
        + "    result = score_item(response, record['gold'])\n"
        + "    result['raw_response'] = response\n"
        + "    return result\n\n"
        + "# %%\n@kbench.task(name=" + repr(display_name) + ")\n"
        + "def gone_for_good(llm) -> float:\n"
        + "    rows = []\n"
        + "    for record in RECORDS:\n"
        + "        row = gfg_item(llm, record)\n"
        + "        print('GFG_ITEM ' + json.dumps(row, sort_keys=True))\n"
        + "        rows.append(row)\n"
        + "    summary = aggregate(rows)\n"
        + "    print('GFG_AGGREGATE ' + json.dumps(summary, sort_keys=True))\n"
        + "    return summary['pair_acc']\n\n"
        + "gone_for_good.run(kbench.llm)\n"
    )
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(task, encoding="utf-8")
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", default="data/gold.jsonl")
    parser.add_argument("--items", default="data/items.jsonl")
    parser.add_argument("--out", default="tasks/gone_for_good.py")
    parser.add_argument("--name", default="gone-for-good")
    args = parser.parse_args()
    build_task(args.gold, args.items, args.out, args.name)


if __name__ == "__main__":
    main()
