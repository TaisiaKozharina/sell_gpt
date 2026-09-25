"""
Full pipeline scraper.

1. Fetches a collection/category page and pulls out every product URL
   (via JSON-LD ItemList, both flavors: {"item": {...}} and flat ListItem).
2. Visits each product page with Playwright, clicking open accordion
   sections (how to use, ingredients, etc.) to get everything.
3. Saves the whole list of products to a JSON file.

Usage:
    python scrape_all_products.py <collection_url> [output.json]

Example:
    python scrape_all_products.py https://goop.com/wellness-shop/c/ products.json
"""

import sys
import json
import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

WANTED_SECTIONS = ("how to use", "ingredients", "key benefits", "return policy")


# ---------- Step 1: collect product URLs from a collection page ----------

def get_collection_html(url):
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.text


def extract_product_urls(collection_url, html):
    soup = BeautifulSoup(html, "html.parser")
    urls = set()

    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string)
        except (TypeError, json.JSONDecodeError):
            continue
        candidates = data if isinstance(data, list) else [data]
        for item in candidates:
            if not isinstance(item, dict):
                continue
            if item.get("@type") == "ItemList":
                for entry in item.get("itemListElement", []):
                    if not isinstance(entry, dict):
                        continue
                    # (a) {"item": {"url": ...}}   (b) flat ListItem with "url"
                    target = entry.get("item") if isinstance(entry.get("item"), dict) else entry
                    href = target.get("url") if isinstance(target, dict) else None
                    if href:
                        urls.add(urljoin(collection_url, href))
            if item.get("@type") == "Product" and item.get("url"):
                urls.add(urljoin(collection_url, item["url"]))

    if urls:
        return sorted(urls)

    # Fallback: guess product links from common patterns
    for a in soup.select("a[href*='/p'], a[href*='/product'], a[href*='/products/']"):
        href = a.get("href")
        if href:
            urls.add(urljoin(collection_url, href))
    return sorted(urls)


# ---------- Step 2: scrape each product page ----------

def get_jsonld_product(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string)
        except (TypeError, json.JSONDecodeError):
            continue
        candidates = data if isinstance(data, list) else [data]
        for item in candidates:
            if isinstance(item, dict) and item.get("@type") == "Product":
                offers = item.get("offers", {})
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}
                extra = {}
                for prop in item.get("additionalProperty", []):
                    if isinstance(prop, dict) and prop.get("name"):
                        extra[prop["name"]] = prop.get("value")
                return {
                    "name": item.get("name"),
                    "description": item.get("description"),
                    "price": offers.get("price"),
                    "currency": offers.get("priceCurrency"),
                    "availability": offers.get("availability"),
                    "sku": item.get("sku"),
                    "gtin": item.get("gtin"),
                    "brand": (item.get("brand") or {}).get("name")
                             if isinstance(item.get("brand"), dict) else item.get("brand"),
                    "image": item.get("image"),
                    "url": item.get("url"),
                    **extra,
                }
    return {}


def extract_accordion_sections(page, wanted_labels=None):
    results = {}
    buttons = page.locator("button[aria-expanded]")
    count = buttons.count()

    for i in range(count):
        btn = buttons.nth(i)
        try:
            label = btn.inner_text().strip().lower()
        except Exception:
            continue
        label = re.sub(r"[+\-]$", "", label).strip()

        if wanted_labels and not any(w in label for w in wanted_labels):
            continue
        if not label:
            continue

        expanded = btn.get_attribute("aria-expanded")
        if expanded != "true":
            try:
                btn.click(timeout=5000)
                page.wait_for_timeout(400)
            except Exception:
                continue

        panel = btn.locator("xpath=following-sibling::*[1]")
        try:
            text = panel.inner_text().strip()
        except Exception:
            text = None

        if text:
            results[label] = text

    return results


def scrape_product_page(page, url):
    page.goto(url, timeout=20000, wait_until="domcontentloaded")
    page.wait_for_timeout(1200)

    html = page.content()
    product = get_jsonld_product(html)
    product["url"] = product.get("url") or url

    sections = extract_accordion_sections(page, wanted_labels=WANTED_SECTIONS)
    product.update(sections)

    return product


# ---------- Orchestration ----------

def scrape_all(collection_url, output_path):
    print(f"[1/3] Fetching collection page: {collection_url}")
    collection_html = get_collection_html(collection_url)

    product_urls = extract_product_urls(collection_url, collection_html)
    print(f"[2/3] Found {len(product_urls)} product URLs")

    if not product_urls:
        print("No product URLs found — the collection page may need JS rendering too.")
        print("Try dumping its HTML to check, or adjust the fallback selector.")
        return

    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=HEADERS["User-Agent"])

        for i, url in enumerate(product_urls, 1):
            print(f"[3/3] ({i}/{len(product_urls)}) {url}")
            try:
                product = scrape_product_page(page, url)
                results.append(product)
            except Exception as e:
                print(f"    failed: {e}")
                results.append({"url": url, "error": str(e)})

        browser.close()

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\nSaved {len(results)} products to {output_path}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python scrape_all_products.py <collection_url> [output.json]")
        sys.exit(1)

    collection_url = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else "products.json"

    scrape_all(collection_url, output_path)


if __name__ == "__main__":
    main()
