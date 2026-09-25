#!/usr/bin/env python3
"""
Batch-run filter_wellness.py's filtering logic across every *_products.json
file in a folder (e.g. site_catalog/), writing filtered results to a NEW
folder — originals are never modified or overwritten.

Requires filter_wellness.py in the same directory — reuses its taxonomy +
keyword matching logic rather than duplicating it.

Usage:
    python3 batch_filter_wellness.py site_catalog
    -> site_catalog_wellness/<same filenames>  (filtered)
    -> site_catalog_wellness/_summary.json     (per-file counts)
"""

import sys
import os
import json
import glob

from filter_wellness import taxonomy_match, keyword_match

OUT_SUFFIX = "_wellness"


def filter_file(path):
    with open(path) as f:
        products = json.load(f)

    kept = []
    for p in products:
        tax_hit = taxonomy_match(p)
        kw_hit = None if tax_hit else keyword_match(p)
        if tax_hit or kw_hit:
            kept.append(p)

    return kept, len(products)


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 batch_filter_wellness.py <input_folder>")
        sys.exit(1)

    in_dir = sys.argv[1].rstrip("/\\")
    out_dir = f"{in_dir}{OUT_SUFFIX}"
    os.makedirs(out_dir, exist_ok=True)

    # Only process actual product json files, skip any prior summary files
    input_files = sorted(
        p for p in glob.glob(os.path.join(in_dir, "*.json"))
        if not os.path.basename(p).startswith("_")
    )

    if not input_files:
        print(f"No .json files found in {in_dir}")
        sys.exit(1)

    summary = []

    for path in input_files:
        fname = os.path.basename(path)
        try:
            kept, total = filter_file(path)
            out_path = os.path.join(out_dir, fname)
            with open(out_path, "w") as f:
                json.dump(kept, f, indent=2)
            print(f"{fname}: {total} total -> {len(kept)} kept")
            summary.append({
                "file": fname,
                "total": total,
                "kept": len(kept),
                "output": out_path,
                "error": None,
            })
        except Exception as e:
            print(f"{fname}: FAILED [{e}]")
            summary.append({
                "file": fname,
                "total": None,
                "kept": None,
                "output": None,
                "error": str(e),
            })

    summary_path = os.path.join(out_dir, "_summary.json")
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    total_kept = sum(s["kept"] or 0 for s in summary)
    total_all = sum(s["total"] or 0 for s in summary)
    print(f"\nDone. {len(input_files)} files processed.")
    print(f"{total_all} total products -> {total_kept} wellness products")
    print(f"Filtered files written to {out_dir}/")
    print(f"Originals in {in_dir}/ untouched.")


if __name__ == "__main__":
    main()
