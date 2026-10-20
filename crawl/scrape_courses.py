"""Scrape feminine/masculine energy course descriptions into courses.json.

Each course page is fetched and its main text kept as the description. Output
records follow the shape of site_catalog/products_clean.json (id, source, brand,
title, url, description, price, ...) so the RAG catalog loader can read them.
site_catalog/courses.json was produced with this script; the sites are listed in
SOURCES.md.

Usage: python crawl/scrape_courses.py [output.json]
"""

import json
import re
import subprocess
import sys
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/128.0 Safari/537.36",
           "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
           "Accept-Language": "en-US,en;q=0.9"}

# Courses linked from each listing page. Summaries and prices come from the
# listing cards where the course page itself does not state them clearly.
SITES = [
    {"listing": "https://www.thefeminineglow.com/store", "brand": "The Feminine Glow (Alexis Smith)",
     "audience": "female", "courses": [
        {"url": "https://www.thefeminineglow.com/resource_redirect/landing_pages/2151030498",
         "title": "Master Your Feminine Energy", "price": 700.00,
         "summary": "Turn on your life force energy, confidence, and feminine embodiment."},
        {"url": "https://www.thefeminineglow.com/resource_redirect/landing_pages/2151031672",
         "title": "The Glowprint | Become a Coach", "price": 1444.00,
         "summary": "Learn to coach with clarity, structure, and aligned messaging."},
        {"url": "https://www.thefeminineglow.com/resource_redirect/landing_pages/2151031738",
         "title": "Magnetically Polarizing", "price": 1411.00,
         "summary": "Become the woman who attracts healthy love and raises her standards."},
        {"url": "https://www.thefeminineglow.com/resource_redirect/landing_pages/2151031743",
         "title": "Divine & Aligned", "price": 1711.00,
         "summary": "Turn your passion into your dream business and unlock financial freedom."},
        {"url": "https://www.thefeminineglow.com/resource_redirect/landing_pages/2151031746",
         "title": "The Gold Vault", "price": 1711.00,
         "summary": "Expand your capacity to receive wealth, abundance, and elevated opportunities."},
        {"url": "https://www.thefeminineglow.com/resource_redirect/offers/chzFYTMB",
         "title": "Levels Ahead Bundle (5 Courses)", "price": 5700.00, "is_bundle": True,
         "summary": "Full access to all programs for the fastest, most supported transformation."},
    ]},
    {"listing": "https://www.jillzguerin.com/courses", "brand": "Jillz Guerin", "audience": "female",
     "courses": [
        {"url": "https://www.jillzguerin.com/awaken-your-feminine-energy",
         "title": "Awaken Your Feminine Energy",
         "summary": "Break free from burnout and get your spark back. This course helps you tap into "
                    "your feminine power, become magnetic, and finally feel like yourself again "
                    "(as your own powerful woman)."},
        {"url": "https://www.jillzguerin.com/youtube-masterclass", "title": "YouTube Growth Masterclass",
         "summary": "Master YouTube growth with the exact strategies I used to build a thriving, "
                    "profitable channel—no guesswork, just what actually works."},
        {"url": "https://www.jillzguerin.com/love-alchemy", "title": "Love Alchemy",
         "summary": "Learn how to unlock your feminine energy in romantic relationships, and discover "
                    "the secrets to being absolutely adored by your partner."},
        {"url": "https://www.jillzguerin.com/glow-up-bundle", "title": "Ultimate Feminine Glow-Up Bundle",
         "is_bundle": True,
         "summary": "Get Awaken Your Feminine Energy AND Love Alchemy together in one powerful bundle—"
                    "designed to help you embody your feminine power in life and love at a special "
                    "reduced price."},
    ]},
    {"listing": "https://feelwomen.com/courses-feel", "brand": "Feel", "audience": "female",
     "courses": [
        {"url": "https://feelwomen.com/feminine-power-blueprint", "title": "Feminine Power Blueprint",
         "summary": "A 36-session self-paced journey guided by 16 world-class teachers through "
                    "embodiment, sexuality, feminine and masculine energies, relationships, and money."},
        {"url": "https://feelwomen.com/body-temple", "title": "Body Temple",
         "summary": "A live rituals and community space focused on regular ritual and embodied "
                    "practice, with weekly live 90-minute sessions and replays."},
        {"url": "https://feelwomen.com/bodysex-masterclass",
         "title": "BODYSEX: Unlock Your Pleasure and Orgasmic Potential in Just 3 Hours",
         "summary": "A 3-hour deep dive into pleasure, orgasm, and your body's natural capacity for "
                    "ecstasy, led by somatic sex educator Simone Farschi."},
    ]},
    {"listing": "https://womenlovepower.com/courses/", "brand": "Women Love Power (Ayesha K. Faines)",
     "audience": "female", "courses": [
        {"url": "https://womenlovepower.com/5-laws-feminine-power/",
         "title": "The Five Laws of Feminine Power",
         "summary": "The keys to unlocking your spellbinding power... in the boardroom, the bedroom "
                    "and beyond."},
        {"url": "https://women-love-power.thinkific.com/courses/women-love-power-master-class-series",
         "title": "Women Love Power Master Class",
         "summary": "A deep dive into the study of soft power and the feminine mystique."},
        {"url": "https://womenlovepower.com/the-feminine-odyssey/", "title": "The Feminine Odyssey",
         "summary": "A journey into the 7 feminine archetypes."},
    ]},
    {"listing": "https://www.komalaamorim.com/the-awakened-feminine-training/", "brand": "Komala Amorim",
     "audience": "female", "courses": [
        {"url": "https://www.komalaamorim.com/the-awakened-feminine-training/",
         "title": "The Awakened Feminine Training"},
    ]},
    {"listing": "https://wildfeminineretreats.com/upcoming-retreats", "brand": "Wild Feminine Retreats",
     "audience": "female", "category": "retreat", "courses": [
        {"url": "https://wildfeminineretreats.com/forbidden-feminine-retreat",
         "title": "Forbidden Feminine", "dates": "30 October - 2 November 2026",
         "location": "Somerset, England"},
        {"url": "https://wildfeminineretreats.com/wild-honey-retreat", "title": "Wild Honey",
         "dates": "20 - 25 May 2027", "location": "Crete, Greece"},
        {"url": "https://wildfeminineretreats.com/facilitator-training-retreat",
         "title": "Facilitator Training", "dates": "13 - 19 September 2027", "location": "Crete, Greece"},
        {"url": "https://wildfeminineretreats.com/temple-of-devotion-retreat-ibiza",
         "title": "Temple of Devotion", "dates": "September 2027 (announcing soon)",
         "location": "Ibiza, Spain"},
    ]},
    # The /shop page only sells physical products (handled by scrape_shopify_buy_buttons);
    # the site's programmes are linked from its menu.
    {"listing": "https://www.femininesexualalchemy.com/shop", "brand": "Feminine Sexual Alchemy (Maire Ni G)",
     "audience": "female", "shopify_buy_buttons": True, "courses": [
        {"url": "https://www.femininesexualalchemy.com/fsa-programme", "title": "FSA Programme"},
        {"url": "https://www.femininesexualalchemy.com/teacher-training-waiting-list-1",
         "title": "Teacher Training"},
        {"url": "https://www.femininesexualalchemy.com/elixir", "title": "Elixir"},
    ]},
    {"listing": "https://tripswithasoul.com/products/divine-woman-in-tulum-5-day-to-awaken-your-feminine-energy-retreat/",
     "brand": "Trips With A Soul", "audience": "female", "category": "retreat", "courses": [
        {"url": "https://tripswithasoul.com/products/divine-woman-in-tulum-5-day-to-awaken-your-feminine-energy-retreat/",
         "title": "Divine Woman in Tulum Retreat - Awaken Your Feminine Energy", "location": "Tulum, Mexico"},
    ]},
    {"listing": "https://www.lorinkrenn.com/trainings/", "brand": "Lorin Krenn", "audience": "male",
     "courses": [
        # The listing links a chooser page that splits this workshop by region; its
        # Australasia page returned 404 when this was written.
        {"url": "https://www.lorinkrenn.com/trainings/healing-the-abandonment-wound-usa-europe/",
         "title": "Healing The Abandonment Wound (USA / Europe)"},
        {"url": "https://www.lorinkrenn.com/trainings/healing-the-mother-wound/",
         "title": "Healing the Mother Wound – Brand New Edition", "dates": "Sunday October 11, 2026",
         "summary": "A 2.5-hour brand new edition of one of Lorin's most popular workshops. With "
                    "expanded teachings and practices since the original release, this edition "
                    "includes his latest work on the subject."},
        {"url": "https://www.lorinkrenn.com/trainings/how-old-souls-find-their-true-purpose/",
         "title": "How Old Souls Find Their TRUE Purpose", "dates": "Sunday December 6, 2026",
         "summary": "A 2.5 hour live online workshop with Lorin Krenn including live Q&A and practices."},
        {"url": "https://www.lorinkrenn.com/trainings/the-awakened-masculine-program/",
         "title": "The Awakened Masculine Program", "dates": "Starting January 10, 2027",
         "summary": "An 8-week immersive journey. For the man who is done repeating the same patterns "
                    "in relationships, business, leadership, and life."},
    ]},
    # Udemy blocks plain page requests, so this course comes from its public course API.
    {"listing": "https://www.udemy.com/course/balance-your-warrior-energy/", "brand": "Udemy",
     "audience": "male", "udemy": "balance-your-warrior-energy", "courses": []},
    {"listing": "https://thealphamalecoach.com/the-alpha-male-program/", "brand": "The Alpha Male Coach",
     "audience": "male", "courses": [
        {"url": "https://thealphamalecoach.com/the-alpha-male-program/", "title": "The Alpha Male Program"},
    ]},
]

# Containers that hold site chrome or popups rather than course content: a class or id
# token that starts with one of these words, or mentions cookies/GDPR anywhere.
NOISE = re.compile(r"^(?:popup|pop-up|modal|newsletter|announcement-bar|exit-intent|sidebar|"
                   r"breadcrumbs?|related|share|sharing|comments?)(?:[-_]|$)|cookie|gdpr", re.I)
BLOCKS = ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote", "td", "dt", "dd"]
PRICE = re.compile(r"(?:[$€£]\s?\d[\d,]*(?:\.\d{2})?|\d[\d,]*(?:\.\d{2})?\s?(?:USD|EUR|GBP|AUD))")

session = requests.Session()
session.headers.update(HEADERS)


def fetch(url):
    """Fetch a page. Parameter: URL. Return: (final URL, HTML text)."""
    for attempt in range(3):
        try:
            response = session.get(url, timeout=40)
            break
        except requests.RequestException:
            if attempt == 2:
                raise
            time.sleep(5)  # small sites time out now and then
    if response.status_code == 403:
        # Some hosts (Thinkific) reject Python's TLS handshake but serve curl normally.
        result = subprocess.run(["curl", "-sL", "--max-time", "40", "-w", "\n%{url_effective}",
                                 "-A", HEADERS["User-Agent"], "-H", f"Accept: {HEADERS['Accept']}",
                                 url], capture_output=True, check=True)
        html, _, final_url = result.stdout.decode("utf-8", "replace").rpartition("\n")
        time.sleep(1)
        return final_url, html
    response.raise_for_status()
    time.sleep(1)  # be polite to small sites
    return response.url, response.text


def clean(text):
    """Collapse whitespace. Parameter: text. Return: single-spaced string."""
    return " ".join((text or "").split())


def meta(soup, *names):
    """Read the first matching meta tag. Parameters: soup, property/name keys. Return: str."""
    for name in names:
        tag = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            return clean(tag["content"])
    return ""


def json_ld_offer(soup):
    """Find a price in JSON-LD. Parameter: soup. Return: price dict or None."""
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except ValueError:
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            node = stack.pop()
            if isinstance(node, list):
                stack.extend(node)
            elif isinstance(node, dict):
                offer = node.get("offers")
                if isinstance(offer, list):
                    offer = offer[0] if offer else None
                if isinstance(offer, dict) and offer.get("price") not in (None, ""):
                    price = float(str(offer["price"]).replace(",", ""))
                    return {"min": price, "max": price, "currency": offer.get("priceCurrency")}
                stack.extend(node.get("@graph", []))
    return None


def main_text(soup):
    """Extract readable course text from a page. Parameter: soup. Return: text with newlines."""
    for tag in soup(["script", "style", "noscript", "svg", "iframe", "form", "header", "nav",
                     "footer", "button", "select", "template"]):
        tag.decompose()
    for tag in soup.find_all(True):
        if tag.attrs is None:
            continue  # removed along with an ancestor
        tokens = tag.get("class", []) + ([tag["id"]] if tag.get("id") else [])
        if tag.name not in ("body", "html", "main") and any(NOISE.search(t) for t in tokens):
            tag.decompose()
    body = soup.body or soup
    total = len(clean(body.get_text(" ")))
    # Some themes wrap only a hero section in <main>; use it only if it holds most of the text.
    root = next((node for selector in ("main", "article", ".entry-content", "[role=main]", "#main")
                 for node in [soup.select_one(selector)]
                 if node and len(clean(node.get_text(" "))) >= 0.4 * total), body)
    lines, seen = [], set()
    for block in root.find_all(BLOCKS):
        if block.find(BLOCKS):
            continue  # nested block: its children are visited on their own
        line = clean(block.get_text(" "))
        if len(line) < 3 or line in seen:
            continue
        seen.add(line)
        lines.append(line)
    if len(" ".join(lines)) < 300:  # page builders that put text in bare divs
        lines = []
        for line in root.get_text("\n").split("\n"):
            line = clean(line)
            if len(line) >= 3 and line not in seen:
                seen.add(line)
                lines.append(line)
    return "\n".join(lines)


def prices_in(text):
    """List distinct price mentions. Parameter: text. Return: list of strings."""
    return list(dict.fromkeys(clean(match) for match in PRICE.findall(text)))


def slug(url):
    """Make a stable id suffix. Parameter: URL. Return: slug string."""
    path = urlparse(url).path.strip("/") or urlparse(url).netloc
    return re.sub(r"[^a-z0-9]+", "-", path.split("/")[-1].lower()).strip("-")


def record(site, source_url, title, description, **extra):
    """Build one output record. Parameters: site config, URL, title, text, extras. Return: dict."""
    host = urlparse(site["listing"]).netloc.removeprefix("www.")
    item = {"id": f"{host}:{slug(source_url)}", "source": host, "brand": site["brand"],
            "title": title, "url": source_url, "listing_url": site["listing"],
            "audience": site["audience"], "category": site.get("category", "course"),
            "summary": extra.pop("summary", ""), "description": description,
            "price": extra.pop("price", None), "prices_mentioned": prices_in(description),
            "is_bundle": extra.pop("is_bundle", False)}
    item.update({key: value for key, value in extra.items() if value})
    return item


def site_chrome(url, cache={}):
    """Collect short text lines from a site's homepage, i.e. menus, banners and footers.

    Parameter: any URL on the site. Return: set of lines (cached per host).
    """
    home = f"{urlparse(url).scheme}://{urlparse(url).netloc}/"
    if home not in cache:
        try:
            _, html = fetch(home)
            text = BeautifulSoup(html, "html.parser").get_text("\n")
            cache[home] = {line for line in map(clean, text.split("\n")) if 0 < len(line) < 100}
        except requests.RequestException:
            cache[home] = set()
    return cache[home]


def scrape_course(site, course):
    """Scrape one course page. Parameters: site config, course config. Return: record dict."""
    final_url, html = fetch(course["url"])
    soup = BeautifulSoup(html, "html.parser")
    image = meta(soup, "og:image")
    og_description = meta(soup, "og:description", "description")
    offer = json_ld_offer(soup)
    page_title = meta(soup, "og:title") or clean(soup.title.string if soup.title else "")
    chrome = site_chrome(final_url)
    text = "\n".join(line for line in main_text(soup).split("\n")
                     if line not in chrome and not line.lower().startswith("skip to "))
    price = offer
    if course.get("price") is not None:
        price = {"min": course["price"], "max": course["price"],
                 "currency": site.get("currency", "USD")}
    return record(site, final_url, course.get("title") or page_title, text,
                  summary=course.get("summary") or og_description, price=price,
                  is_bundle=course.get("is_bundle", False), image=image,
                  dates=course.get("dates"), location=course.get("location"),
                  page_title=page_title)


def scrape_udemy(site):
    """Read a Udemy course from its public API. Parameter: site config. Return: record dict."""
    fields = ("title,headline,description,price,url,visible_instructors,image_480x270,"
              "objectives_summary,content_info,num_subscribers,avg_rating,locale")
    response = session.get(f"https://www.udemy.com/api-2.0/courses/{site['udemy']}/",
                           params={"fields[course]": fields}, timeout=40)
    response.raise_for_status()
    data = response.json()
    description = BeautifulSoup(data.get("description") or "", "html.parser").get_text("\n")
    description = "\n".join(clean(line) for line in description.split("\n") if clean(line))
    price = data.get("price")
    numeric = 0.0 if str(price).lower() == "free" else None
    return record(site, urljoin("https://www.udemy.com", data["url"]), data["title"], description,
                  summary=clean(data.get("headline")),
                  price={"min": numeric, "max": numeric, "currency": "USD"} if numeric is not None else None,
                  image=data.get("image_480x270"),
                  instructors=[person["display_name"] for person in data.get("visible_instructors", [])],
                  objectives=data.get("objectives_summary"), length=data.get("content_info"),
                  rating=data.get("avg_rating"), students=data.get("num_subscribers"),
                  price_text=price)


def scrape_shopify_buy_buttons(site):
    """Read the Shopify buy-button products embedded on a page.

    The page loads these products in the browser with a public storefront token; this
    makes the same read-only request. Parameter: site config. Return: list of record dicts.
    """
    _, html = fetch(site["listing"])
    domain = re.search(r"domain:\s*'([^']+)'", html).group(1)
    token = re.search(r"storefrontAccessToken:\s*'([^']+)'", html).group(1)
    ids = list(dict.fromkeys(re.findall(r"createComponent\('product',\s*\{\s*id:\s*'(\d+)'", html)))
    query = """query($ids: [ID!]!) { nodes(ids: $ids) { ... on Product {
        id title handle productType description onlineStoreUrl featuredImage { url }
        priceRange { minVariantPrice { amount currencyCode } maxVariantPrice { amount } } } } }"""
    response = session.post(f"https://{domain}/api/2024-01/graphql.json", timeout=40,
                            headers={"X-Shopify-Storefront-Access-Token": token},
                            json={"query": query,
                                  "variables": {"ids": [f"gid://shopify/Product/{pid}" for pid in ids]}})
    response.raise_for_status()
    items = []
    for node in response.json()["data"]["nodes"]:
        if not node:
            continue
        low = node["priceRange"]["minVariantPrice"]
        url = f"{site['listing']}#product-{node['id'].split('/')[-1]}"
        item = record(site, url, node["title"], clean(node.get("description")),
                      price={"min": float(low["amount"]),
                             "max": float(node["priceRange"]["maxVariantPrice"]["amount"]),
                             "currency": low["currencyCode"]},
                      image=(node.get("featuredImage") or {}).get("url"),
                      product_type=node.get("productType"))
        item["id"] = f"{item['source']}:{node['handle']}"
        item["category"] = "product"
        items.append(item)
    return items


def main():
    """Scrape every site and write JSON. Parameters: none (argv). Return: None."""
    sys.stdout.reconfigure(encoding="utf-8")
    output = sys.argv[1] if len(sys.argv) > 1 else "courses.json"
    results, failures = [], []
    for site in SITES:
        jobs = [(scrape_course, site, course) for course in site["courses"]]
        if site.get("udemy"):
            jobs.append((scrape_udemy, site))
        if site.get("shopify_buy_buttons"):
            jobs.append((scrape_shopify_buy_buttons, site))
        for job, *args in jobs:
            label = args[1]["url"] if len(args) > 1 else site["listing"]
            try:
                found = job(*args)
            except Exception as error:  # keep going; report at the end
                failures.append({"url": label, "error": repr(error)})
                print(f"FAILED {label}: {error}")
                continue
            found = found if isinstance(found, list) else [found]
            results.extend(found)
            for item in found:
                print(f"ok  {item['source']:<28} {len(item['description']):>6} chars  {item['title']}")
    with open(output, "w", encoding="utf-8") as handle:
        json.dump(results, handle, ensure_ascii=False, indent=1)
    print(f"\n{len(results)} records written to {output}; {len(failures)} failures")
    for failure in failures:
        print(" -", failure["url"], failure["error"])


if __name__ == "__main__":
    main()
