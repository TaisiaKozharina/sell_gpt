#!/usr/bin/env python3
"""
Fetch robots.txt (plus check for llms.txt / agents.md / sitemap.xml / openapi.json)
across a list of sites, and bucket them by what data-access route is available.

Usage:
    python3 robots_check.py sites.txt
    (sites.txt = one domain per line, e.g. "blueprint.bryanjohnson.com")

Outputs:
    - Prints a per-site summary to stdout
    - Writes results.json with full detail for each site
"""

import sys
import json
import requests

TIMEOUT = 10
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ResearchBot/1.0)"}

# Files worth checking beyond robots.txt itself — signals of a structured
# machine-readable data path (llms.txt-style conventions, sitemaps, APIs)
CHECK_PATHS = [
    "robots.txt",
    "llms.txt",
    "agents.md",
    "AGENTS.md",
    "sitemap.xml",
    "openapi.json",
    ".well-known/ucp",
]


def fetch(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        return resp.status_code, resp.text if resp.status_code == 200 else None
    except requests.RequestException as e:
        return None, f"ERROR: {e}"


def check_site(domain):
    domain = domain.strip().rstrip("/")
    if not domain.startswith("http"):
        base = f"https://{domain}"
    else:
        base = domain

    result = {"domain": domain, "checks": {}}

    for path in CHECK_PATHS:
        url = f"{base}/{path}"
        status, body = fetch(url)
        result["checks"][path] = {
            "status": status,
            "found": status == 200,
            # keep a preview only — full robots.txt can be long
            "preview": (body[:500] if body and status == 200 else None),
        }

    # crude bucket classification based on what was found
    checks = result["checks"]
    if checks["llms.txt"]["found"] or checks["agents.md"]["found"] or checks["AGENTS.md"]["found"]:
        bucket = "1_structured_api_hint"
    elif checks["openapi.json"]["found"] or checks[".well-known/ucp"]["found"]:
        bucket = "1_structured_api_hint"
    elif checks["sitemap.xml"]["found"]:
        bucket = "2_sitemap_only"
    elif checks["robots.txt"]["found"]:
        bucket = "3_plain_html_check_robots"
    else:
        bucket = "4_no_robots_found"

    result["bucket"] = bucket
    return result


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 robots_check.py sites.txt")
        sys.exit(1)

    with open(sys.argv[1]) as f:
        sites = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    all_results = []
    for site in sites:
        print(f"Checking {site} ...")
        res = check_site(site)
        all_results.append(res)
        print(f"  -> bucket: {res['bucket']}")
        for path, info in res["checks"].items():
            mark = "OK " if info["found"] else "-- "
            print(f"     [{mark}] {path} (status: {info['status']})")
        print()

    with open("results.json", "w") as f:
        json.dump(all_results, f, indent=2)

    print(f"\nDone. Checked {len(sites)} sites. Full detail written to results.json")

    # quick bucket summary
    from collections import Counter
    counts = Counter(r["bucket"] for r in all_results)
    print("\nBucket summary:")
    for bucket, count in sorted(counts.items()):
        print(f"  {bucket}: {count}")


if __name__ == "__main__":
    main()