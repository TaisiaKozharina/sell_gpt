#!/usr/bin/env python3
"""
Extract every product from a UCP-enabled Shopify store.

Strategy: page through search_catalog with an empty query and cursor-based
pagination. This browses the entire catalog directly through the store's
own MCP endpoint, and sidesteps a problem the sitemap+lookup_catalog
approach ran into: lookup_catalog matches product IDs against the store's
registered canonical domain, which doesn't always match the domain its
sitemap happens to be hosted on (seen on Huel: sitemap on checkout.huel.com,
catalog registered elsewhere -> every lookup came back not_found).

Caveat: UCP pagination is documented as capped around 1,000 results total
(has_next_page goes false past that depth regardless of remaining matches).
Fine for most single-merchant catalogs; flag it if a store you're checking
has more SKUs than that.

Usage:
    python3 get_all_products.py blueprint.bryanjohnson.com
    -> writes blueprint.bryanjohnson.com_products.json
"""

import re
import sys
import json
import time
import uuid
import requests

TIMEOUT = 20
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ResearchBot/1.0)",
    "Content-Type": "application/json",
    "Accept": "application/json",
}
AGENT_PROFILE_URL = "https://shopify.dev/ucp/agent-profiles/2026-08-25/valid-with-capabilities.json"
PAGE_LIMIT = 50          # max allowed per UCP spec
POLITENESS_DELAY = 0.5   # seconds between requests


def normalize_domain(raw):
    """Strip scheme, path, and trailing slash so 'https://x.com/' -> 'x.com'."""
    d = raw.strip()
    d = re.sub(r"^https?://", "", d, flags=re.IGNORECASE)
    d = d.split("/")[0]  # drop any path/query if a full URL was pasted in
    return d


def get_manifest(domain):
    resp = requests.get(f"https://{domain}/.well-known/ucp", headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def find_mcp_endpoint(manifest):
    services = manifest.get("ucp", {}).get("services", {})
    for entries in services.values():
        for entry in entries:
            if entry.get("transport") == "mcp":
                return entry.get("endpoint")
    return None


def rpc_call(endpoint, method, params=None):
    payload = {"jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": method}
    if params is not None:
        payload["params"] = params
    resp = requests.post(endpoint, headers=HEADERS, json=payload, timeout=TIMEOUT)
    if not resp.ok:
        print(f"[HTTP {resp.status_code}] {resp.text[:500]}")
        resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"MCP error on {method}: {data['error']}")
    return data.get("result")


def search_page(endpoint, cursor=None, debug=False):
    catalog = {"pagination": {"limit": PAGE_LIMIT}}
    if cursor:
        catalog["pagination"]["cursor"] = cursor
    # deliberately no "query" field -> browse the whole catalog, not a search match

    arguments = {
        "meta": {"ucp-agent": {"profile": AGENT_PROFILE_URL}},
        "catalog": catalog,
    }
    result = rpc_call(endpoint, "tools/call", {"name": "search_catalog", "arguments": arguments})
    if debug:
        print("      RAW RESULT (first page):")
        print(json.dumps(result, indent=2)[:2000])

    if result and result.get("isError"):
        error_text = ""
        for block in result.get("content", []):
            if block.get("type") == "text":
                error_text = block.get("text", "")
                break
        return [], None, False, error_text

    structured = (result or {}).get("structuredContent", {})
    products = structured.get("products", [])
    pagination = structured.get("pagination", {})
    next_cursor = pagination.get("cursor")
    has_next = pagination.get("has_next_page", False)
    return products, next_cursor, has_next, None


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 get_all_products.py <domain>")
        sys.exit(1)

    domain = normalize_domain(sys.argv[1])

    print(f"[1/2] Fetching UCP manifest for {domain} ...")
    manifest = get_manifest(domain)
    endpoint = find_mcp_endpoint(manifest)
    if not endpoint:
        print("No MCP transport declared — this site isn't a UCP catalog target.")
        sys.exit(1)
    print(f"      -> MCP endpoint: {endpoint}")

    print(f"\n[2/2] Paging through the full catalog ({PAGE_LIMIT} per page) ...")
    all_products = []
    cursor = None
    page = 0

    while True:
        page += 1
        products, next_cursor, has_next, error_text = search_page(endpoint, cursor, debug=(page == 1))

        if error_text:
            print(f"      !! Page {page} error: {error_text}")
            break

        all_products.extend(products)
        print(f"      Page {page}: +{len(products)} products (total: {len(all_products)}, has_next: {has_next})")

        if not has_next or not next_cursor:
            break
        cursor = next_cursor
        time.sleep(POLITENESS_DELAY)

    out_path = f"{domain}_products.json"
    with open(out_path, "w") as f:
        json.dump(all_products, f, indent=2)

    print(f"\nDone. {len(all_products)} products written to {out_path}")


if __name__ == "__main__":
    main()
