#!/usr/bin/env python3
"""
Scrape product data from a WooCommerce (WordPress) store.

Strategy:
    1. GET /wp-sitemap.xml -> a sitemap INDEX; find the product-specific
       sub-sitemap(s) (WooCommerce registers products as a post type, so
       WordPress's built-in sitemap names them like
       wp-sitemap-posts-product-1.xml)
    2. Parse each product sub-sitemap for every product page URL
    3. For each product page:
        a. Prefer application/ld+json Product schema (SEO plugins like
           Yoast/RankMath auto-generate this — clean structured data,
           no selector guessing)
        b. Fall back to standard WooCommerce HTML classes if no JSON-LD
           Product block is present

Usage:
    python3 scrape_woocommerce.py ironmaglabs.com
    -> writes ironmaglabs.com_products.json
"""

import sys
import json
import time
import re
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup

TIMEOUT = 20
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ResearchBot/1.0)"}
POLITENESS_DELAY = 0.5
SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def get(url):
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp


def normalize_domain(raw):
    d = raw.strip()
    if d.startswith("http://") or d.startswith("https://"):
        d = d.split("://", 1)[1]
    return d.split("/")[0]


def find_product_sitemaps(domain):
    """wp-sitemap.xml is an index; find sub-sitemaps for the 'product' post type."""
    resp = get(f"https://{domain}/wp-sitemap.xml")
    root = ET.fromstring(resp.content)
    locs = [el.text for el in root.findall(".//sm:sitemap/sm:loc", SITEMAP_NS)]
    product_sitemaps = [loc for loc in locs if "product" in loc.lower()]
    return product_sitemaps if product_sitemaps else locs  # fallback: check them all


def get_urls_from_sitemap(sitemap_url):
    resp = get(sitemap_url)
    root = ET.fromstring(resp.content)
    return [el.text for el in root.findall(".//sm:url/sm:loc", SITEMAP_NS)]


def extract_jsonld_product(soup):
    """Look through every ld+json block for one with @type Product."""
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
        except (TypeError, ValueError):
            continue

        candidates = data if isinstance(data, list) else [data]
        for item in candidates:
            if not isinstance(item, dict):
                continue
            # some plugins nest the Product inside an @graph array
            graph = item.get("@graph")
            pool = graph if isinstance(graph, list) else [item]
            for entry in pool:
                if isinstance(entry, dict) and entry.get("@type") in ("Product", ["Product"]):
                    return entry
    return None


def parse_jsonld_product(entry, url):
    offers = entry.get("offers", {})
    if isinstance(offers, list):
        offers = offers[0] if offers else {}

    return {
        "source": "jsonld",
        "url": url,
        "name": entry.get("name"),
        "description": entry.get("description"),
        "sku": entry.get("sku"),
        "brand": (entry.get("brand") or {}).get("name") if isinstance(entry.get("brand"), dict) else entry.get("brand"),
        "price": offers.get("price"),
        "currency": offers.get("priceCurrency"),
        "availability": offers.get("availability"),
        "images": entry.get("image") if isinstance(entry.get("image"), list) else ([entry.get("image")] if entry.get("image") else []),
        "category": entry.get("category"),
    }


def extract_html_fallback(soup, url):
    """Standard WooCommerce theme classes — used only if no JSON-LD Product found."""
    def text_or_none(el):
        return el.get_text(strip=True) if el else None

    name = text_or_none(soup.select_one("h1.product_title"))
    price = text_or_none(soup.select_one("p.price .woocommerce-Price-amount") or soup.select_one("p.price"))
    description = text_or_none(soup.select_one("div.woocommerce-product-details__short-description"))
    sku = text_or_none(soup.select_one("span.sku"))
    images = [img.get("src") for img in soup.select("div.woocommerce-product-gallery img") if img.get("src")]

    return {
        "source": "html_fallback",
        "url": url,
        "name": name,
        "description": description,
        "sku": sku,
        "brand": None,
        "price": price,
        "currency": None,
        "availability": None,
        "images": images,
        "category": None,
    }


def extract_description_sections(soup):
    """Split the WooCommerce description tab into named sections by heading
    (h3/h4), e.g. {'Ingredients': [<p>, <ul>], 'Suggested Use': [<p>]}."""
    panel = soup.select_one("#tab-description")
    if not panel:
        return {}

    sections = {}
    current = None
    buffer = []
    for el in panel.find_all(["h3", "h4", "p", "ul"], recursive=True):
        if el.name in ("h3", "h4"):
            if current is not None:
                sections[current] = buffer
            current = el.get_text(strip=True)
            buffer = []
        else:
            if current is not None:
                buffer.append(el)
    if current is not None:
        sections[current] = buffer
    return sections


def parse_supplement_facts(sections):
    """Pull structured serving info + active ingredients out of an
    'Ingredients' section, and suggested-use text if present. Only reads
    sections whose heading looks like these two — research/citation
    sections are deliberately left out."""
    result = {
        "serving_size": None,
        "servings_per_container": None,
        "active_ingredients": [],
        "suggested_use": None,
    }

    ing_key = next((k for k in sections if "ingredient" in k.lower()), None)
    if ing_key:
        for el in sections[ing_key]:
            if el.name == "p":
                text = el.get_text(" ", strip=True)
                m1 = re.search(r"Serving size:\s*(.+?)(?:Servings|$)", text, re.I)
                m2 = re.search(r"Servings per (?:bottle|container):\s*(\d+)", text, re.I)
                if m1:
                    result["serving_size"] = m1.group(1).strip()
                if m2:
                    result["servings_per_container"] = int(m2.group(1))
            elif el.name == "ul":
                for li in el.find_all("li"):
                    line = li.get_text(" ", strip=True)
                    m = re.match(r"^(.*?)\s*[\u2013\-]\s*([\d.,]+)\s*(mg|g|mcg|iu|ml|%)\s*$", line, re.I)
                    if m:
                        result["active_ingredients"].append({
                            "name": m.group(1).strip(),
                            "amount": m.group(2),
                            "unit": m.group(3).lower(),
                        })
                    else:
                        result["active_ingredients"].append({"name": line, "amount": None, "unit": None})

    use_key = next((k for k in sections if "suggested use" in k.lower() or "directions" in k.lower()), None)
    if use_key:
        result["suggested_use"] = " ".join(el.get_text(" ", strip=True) for el in sections[use_key])

    return result


def scrape_product(url, debug=False):
    resp = get(url)
    soup = BeautifulSoup(resp.text, "lxml")

    jsonld = extract_jsonld_product(soup)
    if jsonld:
        if debug:
            print("      (using JSON-LD)")
        product = parse_jsonld_product(jsonld, url)
    else:
        if debug:
            print("      (no JSON-LD found, using HTML fallback)")
        product = extract_html_fallback(soup, url)

    # Supplement facts live in the description tab regardless of which
    # path built the base product record above — always check for them.
    sections = extract_description_sections(soup)
    product.update(parse_supplement_facts(sections))

    return product


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 scrape_woocommerce.py <domain>")
        sys.exit(1)

    domain = normalize_domain(sys.argv[1])

    print(f"[1/3] Finding product sitemaps for {domain} ...")
    product_sitemaps = find_product_sitemaps(domain)
    print(f"      -> {len(product_sitemaps)} sitemap(s): {product_sitemaps}")

    print("[2/3] Collecting product URLs ...")
    all_urls = []
    for sm in product_sitemaps:
        urls = get_urls_from_sitemap(sm)
        all_urls.extend(urls)
        print(f"      {sm} -> {len(urls)} URLs (running total: {len(all_urls)})")
        time.sleep(POLITENESS_DELAY)

    print(f"\n[3/3] Scraping {len(all_urls)} product pages ...")
    products = []
    for i, url in enumerate(all_urls, 1):
        try:
            print(f"      [{i}/{len(all_urls)}] {url}")
            product = scrape_product(url, debug=(i == 1))
            products.append(product)
        except Exception as e:
            print(f"      !! Failed: {e}")
        time.sleep(POLITENESS_DELAY)

    out_path = f"{domain}_products.json"
    with open(out_path, "w") as f:
        json.dump(products, f, indent=2)

    jsonld_count = sum(1 for p in products if p["source"] == "jsonld")
    fallback_count = len(products) - jsonld_count
    print(f"\nDone. {len(products)} products written to {out_path}")
    print(f"  {jsonld_count} via JSON-LD, {fallback_count} via HTML fallback")


if __name__ == "__main__":
    main()