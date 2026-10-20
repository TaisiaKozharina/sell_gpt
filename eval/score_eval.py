"""Score SellGPT test conversations by the category of the product it recommends.

For each reply, products are found by name (including short forms such as the name
without "(28 ct)"), by [n] citation of a retrieved source, or by URL, in the order
they appear. Products the reply was shown match case-insensitively. Other catalog
products match only with two or more words and the catalog's capitalisation, since
names like "Creatine" or "Muscle Repair+" are also ordinary phrases.

The main pick is the first product mentioned in the conversation (reply 1, else
reply 2). Outcomes per run:
    correct  main pick is in the prompt's category (lenient: or also_acceptable)
    wrong    main pick is in another category
    none     no catalog product mentioned in either reply
For `none` control prompts, recommending nothing is correct.

Usage: python eval/score_eval.py [raw.jsonl] [--out eval/results]
Writes scored.jsonl and summary.json next to the input and prints the tables.
"""

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

EVAL = Path(__file__).resolve().parent
ROOT = EVAL.parent
sys.path.insert(0, str(ROOT / "rag" / "src"))

from sellgpt.products import product_name_pattern  # noqa: E402

CATEGORIES = ["wellness", "beauty", "gym", "course"]
PICKS = CATEGORIES + ["other", "none"]
CITATION = re.compile(r"(?<![\[!])\[(\d+)\](?![\](])")
URL = re.compile(r"https?://[^\s<>\"')\]]+")


def name_variants(title):
    """Short forms a reply may use for a product name.

    Drops a trailing "(28 ct)"-style note, a " - subtitle" or " | author", and
    spells "+" as "plus". Parameter: catalog title. Return: set of names.
    """
    names = {title, re.sub(r"\s*\([^)]*\)\s*$", "", title), title.split(" - ")[0], title.split(" | ")[0]}
    names |= {name.replace("+", " Plus ") for name in names if "+" in name}
    return {name.strip() for name in names if name.strip()}


class Matcher:
    """Find catalog products mentioned in a reply, in order of appearance."""

    def __init__(self, labels):
        """Precompile name patterns. Parameter: labels {url: {category, title, ...}}. Return: None."""
        self.labels = labels
        self.by_name = defaultdict(list)
        for url, entry in labels.items():
            for name in name_variants(entry["title"]):
                if url not in self.by_name[name]:
                    self.by_name[name].append(url)
        self.patterns = {}
        for name in self.by_name:
            pattern = product_name_pattern(name)
            if pattern:
                # A leading "The" does not make a name distinctive ("the Elixir membership").
                bare = re.sub(r"^\s*the\s+", "", re.sub(r"[™®]", "", name), flags=re.IGNORECASE)
                multiword = len(re.findall(r"\w+", bare)) > 1
                # Catalog-wide matches keep the name's capitalisation, so the phrase
                # "muscle repair" in a sentence is not the product "Muscle Repair+".
                exact = r"(?<!\w)" + r"[\W_]+".join(
                    re.escape(w) for w in re.findall(r"\w+", re.sub(r"[™®‡]", "", name))) + r"(?!\w)"
                self.patterns[name] = (re.compile(pattern, re.IGNORECASE), re.compile(exact), multiword)

    def find(self, text, sources):
        """List mentions. Parameters: reply text, retrieved sources. Return: list of mention dicts."""
        source_urls = [s["url"] for s in sources]
        source_names = {s["name"] for s in sources} | {self.labels[u]["title"] for u in source_urls
                                                       if u in self.labels}
        spans = []
        for name, (loose, exact, multiword) in self.patterns.items():
            shown = name in source_names or any(u in source_urls for u in self.by_name[name])
            if not multiword and not shown:
                continue
            for match in (loose if shown else exact).finditer(text):
                urls = self.by_name[name]
                preferred = [u for u in urls if u in source_urls] or urls
                spans.append((match.start(), match.end(), preferred, "name"))
        for match in CITATION.finditer(text):
            position = int(match.group(1)) - 1
            if 0 <= position < len(source_urls) and source_urls[position] in self.labels:
                spans.append((match.start(), match.end(), [source_urls[position]], "citation"))
        for match in URL.finditer(text):
            url = match.group(0).rstrip(".,;!")
            if url in self.labels:
                spans.append((match.start(), match.end(), [url], "url"))
        # Keep the longest match where names overlap ("Alpha BRAIN" inside a longer name).
        spans.sort(key=lambda span: (span[0], -(span[1] - span[0])))
        mentions, last_end, seen = [], -1, set()
        for start, end, urls, kind in spans:
            if start < last_end:
                continue
            last_end = end
            categories = Counter(self.labels[u]["category"] for u in urls)
            category = categories.most_common(1)[0][0]
            url = next(u for u in urls if self.labels[u]["category"] == category)
            if url in seen:
                continue
            seen.add(url)
            mentions.append({"url": url, "title": self.labels[url]["title"], "category": category,
                             "borderline": self.labels[url]["borderline"], "via": kind,
                             "ambiguous": len(categories) > 1})
        return mentions


def score(record, matcher):
    """Score one conversation. Parameters: raw record, Matcher. Return: scored dict."""
    turns = record["turns"]
    mentions = [matcher.find(turn["answer"], turn["sources"]) for turn in turns]
    first_turn = next((number for number, found in enumerate(mentions, 1) if found), None)
    pick = mentions[first_turn - 1][0] if first_turn else None
    picked = pick["category"] if pick else "none"
    target, accepted = record["category"], [record["category"]] + (record.get("also_acceptable") or [])
    if target == "none":
        outcome = "correct" if picked == "none" else "wrong"
        lenient = outcome
    else:
        outcome = "none" if picked == "none" else ("correct" if picked == target else "wrong")
        lenient = "correct" if picked in accepted else outcome
    all_categories = {m["category"] for found in mentions for m in found}
    retrieved = [[matcher.labels[s["url"]]["category"] for s in turn["sources"] if s["url"] in matcher.labels]
                 for turn in turns]
    return {"id": record["id"], "run": record["run"], "category": target, "style": record["style"],
            "source": record.get("source"), "picked": picked, "outcome": outcome, "lenient": lenient,
            "first_turn": first_turn, "pick_borderline": bool(pick and pick["borderline"]),
            "pick_ambiguous": bool(pick and pick["ambiguous"]), "mixed": len(all_categories) > 1,
            "target_retrieved": [target in cats for cats in retrieved],
            "mentions": mentions, "answers": [turn["answer"] for turn in turns]}


def rate(rows, outcome="correct", key="outcome"):
    """Share of rows with an outcome. Parameters: rows, outcome, field. Return: float or None."""
    return round(sum(r[key] == outcome for r in rows) / len(rows), 3) if rows else None


def summarise(rows):
    """Build all summary tables. Parameter: scored rows. Return: dict."""
    products = [r for r in rows if r["category"] != "none"]
    controls = [r for r in rows if r["category"] == "none"]
    table = lambda group: {
        "n": len(group), "correct": rate(group), "lenient_correct": rate(group, key="lenient"),
        "wrong": rate(group, "wrong"), "no_recommendation": rate(group, "none"),
        "mixed": round(sum(r["mixed"] for r in group) / len(group), 3) if group else None,
        "picked_in_reply_1": round(sum(r["first_turn"] == 1 for r in group) / len(group), 3) if group else None}
    summary = {"runs": len(rows), "overall": table(products),
               "by_category": {c: table([r for r in products if r["category"] == c]) for c in CATEGORIES},
               "by_style": {s: table([r for r in products if r["style"] == s])
                            for s in ("explicit", "need", "vague")},
               "by_source": {s: table([r for r in products if r["source"] == s])
                             for s in sorted({r["source"] for r in products})}}
    summary["confusion"] = {c: dict(Counter(r["picked"] for r in products if r["category"] == c))
                            for c in CATEGORIES}
    summary["controls"] = {
        "n": len(controls),
        "ad_rate_reply_1": round(sum(r["first_turn"] == 1 for r in controls) / len(controls), 3) if controls else None,
        "ad_rate_any": round(sum(r["picked"] != "none" for r in controls) / len(controls), 3) if controls else None,
        "picked": dict(Counter(r["picked"] for r in controls))}
    recommended = [r for r in products if r["first_turn"]]
    summary["retrieval"] = {
        "target_in_sources_when_correct": rate([r for r in recommended if r["outcome"] == "correct"],
                                               True, "target_hit"),
        "target_in_sources_when_wrong": rate([r for r in recommended if r["outcome"] == "wrong"],
                                             True, "target_hit")}
    clean = [r for r in products if not r["pick_borderline"]]
    summary["excluding_borderline_picks"] = table(clean)
    per_prompt = defaultdict(list)
    for r in products:
        per_prompt[r["id"]].append(r["outcome"] == "correct")
    summary["consistency"] = dict(Counter(f"{sum(v)}/{len(v)} runs correct" for v in per_prompt.values()))
    return summary


def show(summary):
    """Print the summary tables. Parameter: summary dict. Return: None."""
    def line(name, t):
        cells = [f"{t['n']:>4}"] + [f"{(t[k] or 0) * 100:>6.1f}%" for k in
                 ("correct", "lenient_correct", "wrong", "no_recommendation", "mixed", "picked_in_reply_1")]
        print(f"{name:<22}" + " ".join(cells))
    header = f"{'':<22}{'n':>4} {'correct':>7} {'lenient':>7} {'wrong':>7} {'no rec':>7} {'mixed':>7} {'reply1':>7}"
    for title, groups in (("Overall", {"all product prompts": summary["overall"],
                                       "excl. borderline picks": summary["excluding_borderline_picks"]}),
                          ("By category", summary["by_category"]), ("By style", summary["by_style"]),
                          ("By prompt source", summary["by_source"])):
        print(f"\n{title}\n{header}")
        for name, t in groups.items():
            if t["n"]:
                line(name, t)
    print(f"\nConfusion (rows = target, columns = picked)\n{'':<10}" + "".join(f"{p:>10}" for p in PICKS))
    for target, counts in summary["confusion"].items():
        print(f"{target:<10}" + "".join(f"{counts.get(p, 0):>10}" for p in PICKS))
    c = summary["controls"]
    if c["n"]:
        print(f"\nControls (n={c['n']}): product pushed in reply 1 {c['ad_rate_reply_1'] * 100:.1f}%, "
              f"in either reply {c['ad_rate_any'] * 100:.1f}%; picks {c['picked']}")
    r = summary["retrieval"]
    print(f"\nTarget category among retrieved products: when correct {r['target_in_sources_when_correct']}, "
          f"when wrong {r['target_in_sources_when_wrong']}")
    print(f"Consistency across runs: {summary['consistency']}")


def main():
    """Score a raw results file. Parameters: none (argv). Return: None."""
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("raw", nargs="?", type=Path, default=EVAL / "results" / "raw.jsonl")
    parser.add_argument("--labels", choices=("site", "function"), default="site",
                        help="site: labels from label_catalog.py; function: with its FUNCTION_OVERRIDES")
    args = parser.parse_args()
    label_file = "product_categories.json" if args.labels == "site" else "product_categories_function.json"
    labels = json.loads((EVAL / label_file).read_text(encoding="utf-8"))
    matcher = Matcher(labels)
    rows, errors = [], 0
    for line in args.raw.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if "error" in record:
            errors += 1
            continue
        row = score(record, matcher)
        turn = row["first_turn"]
        row["target_hit"] = bool(turn and row["target_retrieved"][turn - 1])
        rows.append(row)
    stem = args.raw.stem + ("" if args.labels == "site" else "_function")
    (args.raw.parent / f"{stem}_scored.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    summary = summarise(rows)
    summary["errors"] = errors
    (args.raw.parent / f"{stem}_summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(f"Scored {len(rows)} conversations ({errors} errored) from {args.raw.name}")
    show(summary)


if __name__ == "__main__":
    main()
