"""
Scrappy product extractor.

Two modes:
1. JSON-LD mode (best): most e-commerce sites (Shopify, WooCommerce, etc.)
   embed structured product data as <script type="application/ld+json">.
   This is way more reliable than CSS scraping and worth trying first.
2. CSS fallback: dumb heuristic scraping of common product-card patterns.

Usage:
    python scrape_products.py https://example.com/collections/all
"""

import sys
import json
import re
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}


def get_soup(url):
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


def extract_jsonld_products(soup):
    """Pull Product / ItemList objects out of JSON-LD blocks."""
    products = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string)
        except (TypeError, json.JSONDecodeError):
            continue

        candidates = data if isinstance(data, list) else [data]
        for item in candidates:
            if not isinstance(item, dict):
                continue

            # ItemList wraps multiple products (common on collection pages).
            # Two flavors seen in the wild:
            #  (a) itemListElement entries are {"item": {...Product...}}
            #  (b) itemListElement entries ARE the item, type "ListItem",
            #      with name/image/url directly on them (e.g. goop.com)
            if item.get("@type") == "ItemList":
                for entry in item.get("itemListElement", []):
                    if not isinstance(entry, dict):
                        continue
                    if "item" in entry and isinstance(entry["item"], dict):
                        candidates.append(entry["item"])
                    elif entry.get("@type") == "ListItem":
                        # Flat ListItem — treat directly as a lightweight product
                        products.append({
                            "name": entry.get("name"),
                            "price": None,
                            "currency": None,
                            "availability": None,
                            "url": entry.get("url"),
                            "image": entry.get("image"),
                            "sku": None,
                            "brand": None,
                        })

            if item.get("@type") == "Product":
                offers = item.get("offers", {})
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}
                products.append({
                    "name": item.get("name"),
                    "price": offers.get("price"),
                    "currency": offers.get("priceCurrency"),
                    "availability": offers.get("availability"),
                    "url": item.get("url"),
                    "image": item.get("image"),
                    "sku": item.get("sku"),
                    "brand": (item.get("brand") or {}).get("name")
                             if isinstance(item.get("brand"), dict) else item.get("brand"),
                })
    return products


def extract_css_products(soup):
    """Dumb fallback: guess at common product-card class names."""
    products = []
    card_selectors = [
        "[class*='product-card']", "[class*='product-item']",
        "[class*='product-tile']", "[class*='grid-item']",
        "[data-product-id]",
    ]
    cards = []
    for sel in card_selectors:
        found = soup.select(sel)
        if found:
            cards = found
            break

    for card in cards:
        name_el = card.select_one("[class*='title'], [class*='name'], h2, h3")
        price_el = card.select_one("[class*='price']")
        link_el = card.find("a", href=True)
        img_el = card.find("img")

        name = name_el.get_text(strip=True) if name_el else None
        price_text = price_el.get_text(strip=True) if price_el else None
        price = re.search(r"[\d,.]+", price_text).group() if price_text and re.search(r"[\d,.]+", price_text) else None

        if name:
            products.append({
                "name": name,
                "price": price,
                "url": link_el["href"] if link_el else None,
                "image": img_el.get("src") or img_el.get("data-src") if img_el else None,
            })
    return products


def main():
    if len(sys.argv) < 2:
        print("Usage: python scrape_products.py <url>")
        sys.exit(1)

    url = sys.argv[1]
    soup = get_soup(url)

    products = extract_jsonld_products(soup)
    mode = "json-ld"

    if not products:
        products = extract_css_products(soup)
        mode = "css-fallback"

    if not products:
        # Dump raw HTML so you can eyeball whether the content is even there
        # (vs. JS-rendered and missing entirely).
        with open("debug_page.html", "w", encoding="utf-8") as f:
            f.write(soup.prettify())
        print("[debug] no products found — wrote fetched HTML to debug_page.html")
        print("[debug] open it and search for a product name/price you can see in the browser.")
        print("[debug] if it's NOT there, the site renders products via JS — requests won't work, you need a headless browser (playwright).")

    print(f"[{mode}] found {len(products)} products\n")
    print(json.dumps(products, indent=2))


if __name__ == "__main__":
    main()
