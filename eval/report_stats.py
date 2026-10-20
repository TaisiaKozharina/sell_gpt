"""Extra numbers for the report: baselines, per-category precision/recall, latency.

Baselines, computed on the same 420 conversations:
- chance: picking a category uniformly at random (25% on the balanced product prompts);
- retrieval only: recommend the top-ranked retrieved product, with no language model.

Usage: python eval/report_stats.py   (after score_eval.py has run with both label sets)
"""

import json
import math
import random
import statistics
import sys
from pathlib import Path

EVAL = Path(__file__).resolve().parent
RESULTS = EVAL / "results"
CATEGORIES = ["wellness", "beauty", "gym", "course"]


def rows(path):
    """Read JSON Lines. Parameter: path. Return: list of dicts."""
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def precision_recall(scored):
    """Per-category precision, recall and F1 over product prompts. Parameter: scored rows. Return: dict."""
    product = [r for r in scored if r["category"] != "none"]
    out = {}
    for c in CATEGORIES:
        tp = sum(r["category"] == c and r["picked"] == c for r in product)
        picked = sum(r["picked"] == c for r in product)
        actual = sum(r["category"] == c for r in product)
        p, rcl = (tp / picked if picked else 0), (tp / actual if actual else 0)
        out[c] = {"precision": round(p, 3), "recall": round(rcl, 3),
                  "f1": round(2 * p * rcl / (p + rcl), 3) if p + rcl else 0}
    out["macro_f1"] = round(statistics.mean(out[c]["f1"] for c in CATEGORIES), 3)
    return out


def retrieval_baseline(raw, labels):
    """Accuracy of recommending the top retrieved product. Parameters: raw rows, labels. Return: dict."""
    product = [r for r in raw if r["category"] != "none" and "error" not in r]
    controls = [r for r in raw if r["category"] == "none" and "error" not in r]
    def top(r):
        sources = r["turns"][0]["sources"]
        return labels[sources[0]["url"]]["category"] if sources else "none"
    correct = sum(top(r) == r["category"] for r in product)
    by_cat = {c: round(sum(top(r) == c for r in product if r["category"] == c)
                       / sum(r["category"] == c for r in product), 3) for c in CATEGORIES}
    in_top5 = sum(any(labels[s["url"]]["category"] == r["category"] for s in r["turns"][0]["sources"])
                  for r in product)
    return {"accuracy": round(correct / len(product), 3), "by_category": by_cat,
            "target_in_top5": round(in_top5 / len(product), 3),
            "ad_rate_controls": round(sum(bool(r["turns"][0]["sources"]) for r in controls) / len(controls), 3)}


def cluster_ci(scored, key, keep, resamples=5000, seed=0):
    """95% bootstrap interval for a rate, resampling prompts (each has 3 correlated runs).

    Parameters: scored rows, predicate on a row, row filter, resamples, seed.
    Return: (rate, low, high).
    """
    rng = random.Random(seed)
    groups = {}
    for r in scored:
        if keep(r):
            groups.setdefault(r["id"], []).append(key(r))
    ids = list(groups)
    rate = lambda chosen: sum(sum(groups[i]) for i in chosen) / sum(len(groups[i]) for i in chosen)
    draws = sorted(rate([rng.choice(ids) for _ in ids]) for _ in range(resamples))
    return round(rate(ids), 3), round(draws[int(0.025 * resamples)], 3), round(draws[int(0.975 * resamples)], 3)


def mcnemar(scored, raw, labels):
    """Exact McNemar test, chatbot vs. top-1 retrieval, on product prompts.

    Parameters: scored rows, raw rows, labels. Return: dict with discordant counts and p-value.
    """
    top = {(r["id"], r["run"]): (labels[r["turns"][0]["sources"][0]["url"]]["category"]
                                 if r["turns"][0]["sources"] else "none") for r in raw if "error" not in r}
    only_llm = only_retrieval = 0
    for r in scored:
        if r["category"] == "none":
            continue
        llm, base = r["picked"] == r["category"], top[(r["id"], r["run"])] == r["category"]
        only_llm += llm and not base
        only_retrieval += base and not llm
    n, k = only_llm + only_retrieval, min(only_llm, only_retrieval)
    p = min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n) if n else 1.0
    return {"llm_right_retrieval_wrong": only_llm, "retrieval_right_llm_wrong": only_retrieval, "p_value": round(p, 3)}


def latency(raw):
    """Retrieval and generation times. Parameter: raw rows. Return: dict of summaries."""
    out = {}
    for key in ("retrieval_seconds", "generation_seconds"):
        values = [r["turns"][0][key] for r in raw if "error" not in r]
        values.sort()
        out[key] = {"median": round(statistics.median(values), 2), "mean": round(statistics.mean(values), 2),
                    "p95": round(values[int(0.95 * (len(values) - 1))], 2), "max": round(values[-1], 2)}
    words = [len(r["turns"][0]["answer"].split()) for r in raw if "error" not in r]
    out["answer_words"] = {"median": statistics.median(words), "mean": round(statistics.mean(words), 1),
                           "over_60": round(sum(w > 60 for w in words) / len(words), 3)}
    return out


def main():
    """Print and save the report numbers. Parameters: none. Return: None."""
    sys.stdout.reconfigure(encoding="utf-8")
    raw = rows(RESULTS / "raw.jsonl")
    stats = {"latency": latency(raw)}
    for name, label_file, scored_file in (("site", "product_categories.json", "raw_scored.jsonl"),
                                          ("function", "product_categories_function.json",
                                           "raw_function_scored.jsonl")):
        labels = json.loads((EVAL / label_file).read_text(encoding="utf-8"))
        scored = rows(RESULTS / scored_file)
        is_product = lambda r: r["category"] != "none"
        stats[name] = {
            "precision_recall": precision_recall(scored),
            "retrieval_baseline": retrieval_baseline(raw, labels),
            "accuracy_ci": cluster_ci(scored, lambda r: r["outcome"] == "correct", is_product),
            "ad_rate_ci": cluster_ci(scored, lambda r: r["picked"] != "none", lambda r: not is_product(r)),
            "mcnemar_vs_retrieval": mcnemar(scored, raw, labels)}
    (RESULTS / "report_stats.json").write_text(json.dumps(stats, indent=1), encoding="utf-8")
    print(json.dumps(stats, indent=1))


if __name__ == "__main__":
    main()
