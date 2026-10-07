"""Build a self-contained Kaggle task from frozen JSONL inputs."""

import argparse
import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_jsonl(path):
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def build_task(gold_path, items_path, out_path, name="gone-for-good", max_tokens=4096):
    display_name = name
    gold_rows = read_jsonl(gold_path)
    gold = {row["item_id"]: row for row in gold_rows}
    if len(gold) != len(gold_rows):
        raise ValueError("duplicate gold item IDs")
    pairs = {}
    for row in gold_rows:
        variants = pairs.setdefault(row["pair_id"], set())
        if row["variant"] in variants:
            raise ValueError("duplicate variant in pair: " + row["pair_id"])
        variants.add(row["variant"])
    if any(len(variants) < 2 for variants in pairs.values()):
        raise ValueError("each pair needs at least two variants")
    items = read_jsonl(items_path)
    if len({row["item_id"] for row in items}) != len(items):
        raise ValueError("duplicate item IDs")
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
        "# %%\n" + source + "\n# %%\nimport kaggle_benchmarks as kbench\n"
        + "from kaggle_benchmarks.actors.llms import GoogleGenAI, OpenAI\n"
        + "import time\n\n"
        + "RECORDS = json.loads(" + repr(embedded) + ")\n\n"
        + "MAX_TOKENS = " + repr(max_tokens) + "\n\n"
        + "# %%\n@kbench.task(name=\"gfg-item\", store_task=False)\n"
        + "def gfg_item(llm, record) -> dict:\n"
        + "    cap_key = ('max_output_tokens' if isinstance(llm, GoogleGenAI) else\n"
        + "               'max_tokens' if isinstance(llm, OpenAI) else None)\n"
        + "    params = {cap_key: MAX_TOKENS} if cap_key else {}\n"
        + "    if isinstance(llm, OpenAI):\n"
        + "        params['timeout'] = 60\n"
        + "    for attempt in range(2):\n"
        + "        try:\n"
        + "            response = llm.prompt(record['item']['prompt'], temperature=0, extra_api_params=params)\n"
        + "            break\n"
        + "        except Exception as exc:\n"
        + "            if attempt:\n"
        + "                result = score_item('', record['gold'])\n"
        + "                result.update(format_ok=False, format_error='api_error',\n"
        + "                              api_error=type(exc).__name__ + ': ' + str(exc)[:200],\n"
        + "                              lost_exact=False, rec_exact=False, item_correct=False,\n"
        + "                              perm_flag_consistent=False)\n"
        + "                return result\n"
        + "            if cap_key and any(word in str(exc).lower() for word in\n"
        + "                               ('max_tokens', 'max_output_tokens', 'unsupported parameter')):\n"
        + "                params.pop(cap_key, None)\n"
        + "            time.sleep(5)\n"
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
        + "    summary = aggregate(rows, expected_items=[r['gold'] for r in RECORDS])\n"
        + "    summary['n_api_errors'] = sum(r.get('format_error') == 'api_error' for r in rows)\n"
        + "    print('GFG_AGGREGATE ' + json.dumps(summary, sort_keys=True))\n"
        + "    if summary['n_api_errors'] > len(RECORDS) * 0.2:\n"
        + "        print('GFG_WARNING incomplete run')\n"
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
    parser.add_argument("--max-tokens", type=int, default=4096)
    args = parser.parse_args()
    build_task(args.gold, args.items, args.out, args.name, args.max_tokens)


if __name__ == "__main__":
    main()
