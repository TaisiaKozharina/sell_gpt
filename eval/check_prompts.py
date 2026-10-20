"""Validate prompt files and flag catalog wording in need/vague prompts.

Flags brand names and two-word phrases taken from product titles. Single title
words are not flagged: they turned out to be ordinary English ("sleep", "back", "man").

Usage: python eval/check_prompts.py [prompt files...]  (default: blind + human)
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

EVAL = Path(__file__).resolve().parent
ROOT = EVAL.parent
CATALOGS = [ROOT / "site_catalog" / "products_clean.json", ROOT / "site_catalog" / "courses.json"]
CATEGORIES = {"wellness", "beauty", "gym", "course", "none"}
STYLES = {"explicit", "need", "vague", "control"}
STOP = set("""a an the and or of for to in on with my me i im is are be it this that your you
what how can do does some any good best get more like just feel want need have has had been
about from at as so but not no all its ive dont cant would should could really very will which
who when out up down day days time help""".split())


def words(text):
    """Split text into lowercase content words. Parameter: text. Return: list of str."""
    return [w for w in re.findall(r"[a-z][a-z'-]+", text.lower()) if w not in STOP and len(w) > 2]


def validate(prompts, path):
    """Check fields and ids. Parameters: prompt list, file path. Return: list of problems."""
    problems, seen = [], set()
    for prompt in prompts:
        pid = prompt.get("id")
        if pid in seen:
            problems.append(f"{path.name}: duplicate id {pid}")
        seen.add(pid)
        if prompt.get("category") not in CATEGORIES or prompt.get("style") not in STYLES:
            problems.append(f"{path.name}: {pid} has a bad category or style")
        if not str(prompt.get("prompt", "")).strip():
            problems.append(f"{path.name}: {pid} has an empty prompt")
        if prompt.get("category") in prompt.get("also_acceptable", []):
            problems.append(f"{path.name}: {pid} lists its own category as also acceptable")
    return problems


def main():
    """Validate files and print overlap flags. Parameters: argv paths. Return: None."""
    sys.stdout.reconfigure(encoding="utf-8")
    paths = [Path(p) for p in sys.argv[1:]] or [EVAL / "prompts_blind.json", EVAL / "prompts_human.json"]
    items = [item for path in CATALOGS for item in json.loads(path.read_text(encoding="utf-8"))]
    bigrams = set()
    for item in items:
        title = words(item["title"])
        bigrams |= {" ".join(title[k:k + 2]) for k in range(len(title) - 1)}
    # Brands with ordinary-word names would flag everything, so require two words or 5+ letters.
    brands = {b.lower() for b in (item.get("brand") for item in items) if b and (" " in b or len(b) >= 5)}
    for path in paths:
        prompts = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        print(f"{path.name}: {len(prompts)} prompts, {dict(Counter(p['category'] for p in prompts))}")
        for problem in validate(prompts, path):
            print("  PROBLEM", problem)
        for prompt in prompts:
            if prompt.get("style") not in ("need", "vague"):
                continue
            text, tokens = prompt["prompt"].lower(), words(prompt["prompt"])
            flags = [f"brand '{b}'" for b in brands if re.search(rf"\b{re.escape(b)}\b", text)]
            flags += [f"title phrase '{b}'" for b in (" ".join(tokens[k:k + 2])
                      for k in range(len(tokens) - 1)) if b in bigrams]
            if flags:
                print(f"  FLAG {prompt['id']}: {', '.join(flags)} | {prompt['prompt']}")


if __name__ == "__main__":
    main()
