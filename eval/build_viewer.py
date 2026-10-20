"""Build a browsable page of every test prompt and SellGPT's answers.

Reads results/raw.jsonl with both scored files and writes results/answers.html
from viewer_template.html. Run after score_eval.py (both --labels site and function).

Usage: python eval/build_viewer.py
"""

import json
from pathlib import Path

EVAL = Path(__file__).resolve().parent
RESULTS = EVAL / "results"


def load(path):
    """Read JSON Lines keyed by (id, run). Parameter: path. Return: dict."""
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    return {(row["id"], row["run"]): row for row in rows}


def main():
    """Assemble prompt data and write the page. Parameters: none. Return: None."""
    raw = load(RESULTS / "raw.jsonl")
    function, site = load(RESULTS / "raw_function_scored.jsonl"), load(RESULTS / "raw_scored.jsonl")
    prompts = {}
    model = ""
    for key in sorted(raw, key=lambda k: (k[0], k[1])):
        record = raw[key]
        if "error" in record:
            continue
        model = record["model"]
        f, s = function[key], site[key]
        f_pick = f["mentions"][0][0] if f["first_turn"] else None
        s_pick = s["mentions"][0][0] if s["first_turn"] else None
        prompt = prompts.setdefault(record["id"], {
            "id": record["id"], "c": record["category"], "s": record["style"], "q": record["prompt"],
            "aa": record.get("also_acceptable") or [], "runs": []})
        prompt["runs"].append({
            "r": record["run"], "a": record["turns"][0]["answer"].strip(),
            "src": [source["name"] for source in record["turns"][0]["sources"]],
            "o": f["outcome"], "p": f["picked"], "t": f_pick["title"] if f_pick else None,
            "so": s["outcome"], "sp": s["picked"], "st": s_pick["title"] if s_pick else None})
    order = {"wellness": 0, "beauty": 1, "gym": 2, "course": 3, "none": 4}
    data = sorted(prompts.values(), key=lambda p: (order[p["c"]], p["id"]))
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    page = (EVAL / "viewer_template.html").read_text(encoding="utf-8")
    page = page.replace("/*DATA*/null", payload + ";\nDATA.model = " + json.dumps(model))
    out = RESULTS / "answers.html"
    out.write_text(page, encoding="utf-8")
    print(f"{len(data)} prompts, {sum(len(p['runs']) for p in data)} answers -> {out} "
          f"({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
