#!/usr/bin/env python3
"""
Filter a *_products.json file (from get_all_products.py) down to
wellness/supplement products, using two signals:

  1. Shopify standard taxonomy category ID (precise, when merchants use it)
  2. Keyword match against tags/title/description (catches products that
     are wellness-relevant but mis-categorized or left uncategorized)

A product is kept if EITHER signal matches. Run with --report to see
which signal matched each kept product, useful for spot-checking.

Usage:
    python3 filter_wellness.py blueprint.bryanjohnson.com_products.json
    python3 filter_wellness.py huel.com_products.json --report
"""

import sys
import json
import argparse

# Shopify standard taxonomy IDs relevant to wellness/supplements.
# hb-1-9-6 = "Vitamins & Supplements" (confirmed against Shopify's taxonomy docs).
# Add more IDs here as you spot-check other categories in your data
# (e.g. a "Health Care" or "Personal Care" node) — inspect the `categories`
# field on a few known-good products per site to find them.
WELLNESS_TAXONOMY_IDS = {
    "hb-1-9-6",   # Vitamins & Supplements
}

# Keyword fallback — matched (case-insensitive) against tags, title, and
# the plain-text description. Extend this list based on what you see in
# false negatives when spot-checking.
WELLNESS_KEYWORDS = {
    "supplement", "vitamin", "vitamins", "wellness", "nutrition",
    "probiotic", "protein", "herbal", "adaptogen", "omega",
    "mineral", "electrolyte", "collagen", "antioxidant",
    "immune", "longevity", "nootropic", "amino acid",
}


def taxonomy_match(product):
    for cat in product.get("categories", []):
        cat_id = cat.get("value", "")
        # value can be a bare id ("hb-1-9-6") or a gid URL containing it
        if any(tid in cat_id for tid in WELLNESS_TAXONOMY_IDS):
            return cat_id
    return None


def keyword_match(product):
    haystack_parts = [product.get("title", "")]
    haystack_parts.extend(product.get("tags", []))
    desc = product.get("description", {})
    if isinstance(desc, dict):
        haystack_parts.append(desc.get("html", "") or desc.get("plain", ""))
    haystack = " ".join(haystack_parts).lower()

    for kw in WELLNESS_KEYWORDS:
        if kw in haystack:
            return kw
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_file")
    parser.add_argument("--report", action="store_true",
                         help="print which signal matched each kept product")
    args = parser.parse_args()

    with open(args.input_file) as f:
        products = json.load(f)

    kept = []
    dropped = []

    for p in products:
        tax_hit = taxonomy_match(p)
        kw_hit = None if tax_hit else keyword_match(p)

        if tax_hit or kw_hit:
            kept.append(p)
            if args.report:
                reason = f"taxonomy:{tax_hit}" if tax_hit else f"keyword:{kw_hit}"
                print(f"  KEEP  [{reason}]  {p.get('title')}")
        else:
            dropped.append(p)
            if args.report:
                print(f"  DROP             {p.get('title')}")

    out_path = args.input_file.replace(".json", "_wellness.json")
    with open(out_path, "w") as f:
        json.dump(kept, f, indent=2)

    print(f"\n{len(products)} total -> {len(kept)} kept, {len(dropped)} dropped")
    print(f"Wellness subset written to {out_path}")

    if dropped and not args.report:
        print("\nRun with --report to see per-product match reasons,")
        print("or spot-check the dropped list to catch missed keywords.")


if __name__ == "__main__":
    main()
