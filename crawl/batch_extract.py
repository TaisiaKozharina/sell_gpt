#!/usr/bin/env python3
"""
Batch-run get_all_products.py's extraction logic across every site in a
list, saving each site's catalog into site_catalog/.

Requires get_all_products.py in the same directory — this reuses its
functions rather than duplicating the extraction logic.

Usage:
    python3 batch_extract.py mysites.txt
    -> site_catalog/<domain>_products.json  (one per site)
    -> site_catalog/_summary.json           (per-site status + counts)

mysites.txt: one domain per line, e.g.
    blueprint.bryanjohnson.com
    www.huel.com
    # lines starting with # are skipped
"""

import sys
import os
import json
import time
import re

from get_all_products import get_manifest, find_mcp_endpoint, search_page, POLITENESS_DELAY

OUT_DIR = "site_catalog"


def normalize_domain(raw):
    """Strip scheme, path, and trailing slash so 'https://x.com/' -> 'x.com'."""
    d = raw.strip()
    d = re.sub(r"^https?://", "", d, flags=re.IGNORECASE)
    d = d.split("/")[0]  # drop any path/query if a full URL was pasted in
    return d


def extract_site(domain):
    """Run the full paginated extraction for one site. Returns (products, error)."""
    manifest = get_manifest(domain)
    endpoint = find_mcp_endpoint(manifest)
    if not endpoint:
        return [], "No MCP transport declared in manifest"

    all_products = []
    cursor = None
    page = 0

    while True:
        page += 1
        products, next_cursor, has_next, error_text = search_page(endpoint, cursor)

        if error_text:
            return all_products, f"Page {page} error: {error_text}"

        all_products.extend(products)
        print(f"      page {page}: +{len(products)} (total: {len(all_products)}, has_next: {has_next})")

        if not has_next or not next_cursor:
            break
        cursor = next_cursor
        time.sleep(POLITENESS_DELAY)

    return all_products, None


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 batch_extract.py <sites_file>")
        sys.exit(1)

    sites_file = sys.argv[1]
    with open(sites_file) as f:
        raw_sites = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    sites = [normalize_domain(s) for s in raw_sites]

    os.makedirs(OUT_DIR, exist_ok=True)

    summary = []

    for i, domain in enumerate(sites, 1):
        print(f"\n=== [{i}/{len(sites)}] {domain} ===")
        try:
            products, error = extract_site(domain)
        except Exception as e:
            products, error = [], str(e)

        out_path = os.path.join(OUT_DIR, f"{domain}_products.json")
        with open(out_path, "w") as f:
            json.dump(products, f, indent=2)

        status = "ok" if not error else ("partial" if products else "failed")
        summary.append({
            "domain": domain,
            "status": status,
            "product_count": len(products),
            "error": error,
            "output_file": out_path,
        })
        print(f"      -> {status}: {len(products)} products written to {out_path}"
              + (f"  [{error}]" if error else ""))

    summary_path = os.path.join(OUT_DIR, "_summary.json")
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    ok = sum(1 for s in summary if s["status"] == "ok")
    partial = sum(1 for s in summary if s["status"] == "partial")
    failed = sum(1 for s in summary if s["status"] == "failed")
    total_products = sum(s["product_count"] for s in summary)

    print(f"\n=== Done ===")
    print(f"{len(sites)} sites: {ok} ok, {partial} partial, {failed} failed")
    print(f"{total_products} total products extracted")
    print(f"Summary written to {summary_path}")


if __name__ == "__main__":
    main()
