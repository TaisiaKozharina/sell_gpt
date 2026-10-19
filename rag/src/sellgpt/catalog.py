"""Normalize catalog products and create retrieval chunks."""

import hashlib
from html.parser import HTMLParser
import json
import re
import sys


MAX_TAGS = 12
IGNORED_TAGS = {
    "active on shopify", "barneys", "bergdorf goodman", "bis", "blue mercury",
    "byob display", "collaborations", "custom-tagline", "device-set", "device-ui",
    "dtc", "gift", "gift-him", "green4", "import", "joined-description-fields", "joint venture",
    "michelle", "needs-metadata", "new releases", "new-tag", "nooutofstock",
    "not-aply-subcription", "pdqupgrade", "selling", "site", "space nk", "tag-on-collection",
    "validate-product-description", "wholesalecost",
}
TAG_NOISE = re.compile(
    r"^pdp-|^pipe\d+-|[:_%]|https?://|\.com\b|"
    r"\b(?:best|celebrity|regimen|dupe|sale|discount|promo|subscription|"
    r"subcription|purchase|acquisition|free bundle|ebook-gift)\b|"
    r"\b\d+-recipes?\b|-\d+(?:-mg)?-\d+$"
)


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


def fingerprints(*paths):
    """Hash catalog files. Parameters: JSON Paths. Return: path/hash mapping."""
    return {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def clean_tags(value):
    """Return at most 12 distinct, short, descriptive catalog tags.

    Accept a list of strings or one string. Strip HTML, lowercase, and normalize
    hyphens and whitespace. Omit known internal labels, promotional/SEO phrases,
    URLs, SKU-like suffixes, and tags longer than 60 characters or six words.
    Preserve source order and dietary terms such as gluten-free.
    """
    values = [value] if isinstance(value, str) else value
    if not isinstance(values, list):
        return []
    tags = []
    for item in values:
        if not isinstance(item, str):
            continue
        tag = plain_text(item).casefold()
        if tag in IGNORED_TAGS or TAG_NOISE.search(tag):
            continue
        tag = " ".join(tag.replace("-", " ").split())
        if not tag or len(tag) > 60 or len(tag.split()) > 6 or not any(c.isalpha() for c in tag):
            continue
        if tag not in tags:
            tags.append(tag)
        if len(tags) == MAX_TAGS:
            break
    return tags


def load_chunks(config):
    """Chunk product and course names, descriptive fields, and filtered tags.

    Read both configured JSON files and deduplicate their entries by URL.
    Parameter: Config. Return: chunk dictionaries with URLs as metadata only.
    """
    chunks, seen = [], set()
    for path in (config.catalog, config.courses):
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
            for key in ("summary", "audience", "suggested_use", "category", "categories"):
                value = plain_text(product.get(key))
                if value:
                    fields.append(f"{key}: {value}")
            tags = clean_tags(product.get("tags"))
            if tags:
                fields.append("tags: " + ", ".join(tags))
            words = " ".join(fields).split()
            for start in range(0, max(1, len(words)), config.chunk_words - config.chunk_overlap):
                text = f"Product: {name}\n" + " ".join(words[start:start + config.chunk_words])
                chunks.append({"name": name, "url": url, "source": path.name, "text": text})
                if start + config.chunk_words >= len(words):
                    break
    if not chunks:
        raise ValueError("The catalog contains no products")
    return chunks
