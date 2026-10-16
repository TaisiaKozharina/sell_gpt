"""Match product mentions and track used product URLs without model calls."""

import re


def product_name_pattern(name):
    """Match a catalog name despite spacing, punctuation, or trademark changes.

    Parameter: product name. Return: regex text, or an empty string for no words.
    """
    name = re.sub(r"\(\s*tm\s*\)|[™®]", "", name.casefold())
    words = re.findall(r"\w+(?:\*\w+)*", name)
    if not words:
        return ""
    # Keep masked words intact; allow the common uncensored spelling of f*ck.
    words = [r"f[u*]ck" if word.casefold() == "f*ck" else re.escape(word)
             for word in words]
    separator = r"[\W_]+(?:(?:and|TM)\b[\W_]+)?"
    return r"(?<!\w)" + separator.join(words) + r"(?!\w)"


def mentioned_product_urls(response, sources):
    """Find used products by name, citation, or URL in a completed answer.

    Parameters: raw answer text, ordered retrieved sources.
    Return: set of product URLs. Longer names take precedence over shorter names.
    """
    products = {source["url"]: source for source in sources}
    matches = [(product_name_pattern(product["name"]), product["url"])
               for product in sorted(products.values(), key=lambda item: len(item["name"]),
                                     reverse=True)]
    matches = [(pattern, url) for pattern, url in matches if pattern]
    used = set()
    if matches:
        pattern = "|".join(f"(?P<product_{index}>{name})"
                           for index, (name, _) in enumerate(matches))
        for match in re.finditer(pattern, response, re.IGNORECASE):
            used.add(matches[int(match.lastgroup.removeprefix("product_"))][1])
    for citation in re.findall(r"(?<![\[!])\[(\d+)\](?![\](])", response):
        position = int(citation) - 1
        if 0 <= position < len(sources):
            used.add(sources[position]["url"])
    urls = {url.rstrip(".,;!") for url in re.findall(r"https?://[^\s<>\"')\]]+", response)}
    return used | (urls & products.keys())
