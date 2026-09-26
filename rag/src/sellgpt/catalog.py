"""Normalize catalog products and create retrieval chunks."""

import hashlib
from html.parser import HTMLParser
import json
import sys


class PlainText(HTMLParser):
    """Collect visible HTML text while omitting scripts and styles."""

    def __init__(self):
        """Initialize the parser. Parameters: none. Return: None."""
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        """Handle a tag. Parameters: tag, attributes. Return: None."""
        if tag in ("script", "style"):
            self.hidden += 1

    def handle_endtag(self, tag):
        """Handle a closing tag. Parameter: tag. Return: None."""
        if tag in ("script", "style"):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        """Collect visible text. Parameter: data. Return: None."""
        if not self.hidden:
            self.parts.append(data)


def plain_text(value):
    """Normalize a catalog value. Parameter: value. Return: plain text string."""
    if isinstance(value, dict):
        value = value.get("html", value.get("text", json.dumps(value, ensure_ascii=False)))
    elif isinstance(value, list):
        value = ", ".join(str(item) for item in value)
    parser = PlainText()
    parser.feed(str(value or ""))
    return " ".join(" ".join(parser.parts).split())


def catalog_files(folder):
    """Find product catalogs. Parameter: folder Path. Return: sorted paths."""
    files = sorted(folder.glob("*_products.json"))
    if not files:
        raise ValueError(f"No *_products.json catalogs found in {folder}")
    return files


def fingerprints(folder):
    """Hash source files. Parameter: folder Path. Return: filename/hash mapping."""
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in catalog_files(folder)}


def load_chunks(config):
    """Load and chunk products. Parameter: Config. Return: list of chunk dictionaries."""
    chunks, seen = [], set()
    for path in catalog_files(config.catalog):
        products = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(products, list):
            raise ValueError(f"{path}: expected a JSON list of products")
        for position, product in enumerate(products, 1):
            if not isinstance(product, dict):
                raise ValueError(f"{path}, product {position}: expected an object")
            name = plain_text(product.get("title") or product.get("name"))
            url = product.get("url")
            if not name or not isinstance(url, str) or not url.startswith(("https://", "http://")):
                print(f"Skipping {path.name}, product {position}: missing name or HTTP URL",
                      file=sys.stderr)
                continue
            if url in seen:
                continue
            seen.add(url)
            fields = [plain_text(product.get("description"))]
            for key, value in product.items():
                if value and (key in ("tags", "brand", "category", "categories", "suggested_use")
                              or "ingredient" in key):
                    fields.append(f"{key}: {plain_text(value)}")
            price = {key: product[key] for key in ("price", "currency", "price_range") if key in product}
            if price:
                fields.append("Original price metadata (units unverified): " + json.dumps(price))
            words = " ".join(fields).split()
            for start in range(0, max(1, len(words)), config.chunk_words - config.chunk_overlap):
                text = f"Product: {name}\nURL: {url}\n" + " ".join(words[start:start + config.chunk_words])
                chunks.append({"name": name, "url": url, "source": path.name, "text": text})
                if start + config.chunk_words >= len(words):
                    break
    if not chunks:
        raise ValueError("The catalog contains no products")
    return chunks
