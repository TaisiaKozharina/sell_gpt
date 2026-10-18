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


def fingerprints(path):
    """Hash the catalog file. Parameter: JSON file Path. Return: filename/hash mapping."""
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest()}


def load_chunks(config):
    """Chunk names, descriptions, suggested use, and categories for embedding.

    Read only the configured JSON file; catalog directories are not scanned.
    Parameter: Config. Return: chunk dictionaries with URLs as metadata only.
    """
    chunks, seen = [], set()
    path = config.catalog
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
        for key in ("suggested_use", "category", "categories"):
            value = plain_text(product.get(key))
            if value:
                fields.append(f"{key}: {value}")
        words = " ".join(fields).split()
        for start in range(0, max(1, len(words)), config.chunk_words - config.chunk_overlap):
            text = f"Product: {name}\n" + " ".join(words[start:start + config.chunk_words])
            chunks.append({"name": name, "url": url, "source": path.name, "text": text})
            if start + config.chunk_words >= len(words):
                break
    if not chunks:
        raise ValueError("The catalog contains no products")
    return chunks
