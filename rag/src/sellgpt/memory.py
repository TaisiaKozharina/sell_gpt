"""Validate and update a single user profile or temporary session profile."""

import json
import os
import re
import tempfile

FACT_FIELDS = ("sex", "goals", "preferences", "weakness", "products")
LIST_FIELDS = (*FACT_FIELDS, "mentioned_products")
MAX_ITEMS = 4
MAX_ITEM_LENGTH = 120


def empty_profile():
    """Create an empty profile. Parameters: none. Return: profile dictionary."""
    return {"version": 2, "name": "", **{key: [] for key in LIST_FIELDS}}


def validate_profile(profile):
    """Validate a profile. Parameter: profile dictionary. Return: validated dictionary."""
    if not isinstance(profile, dict) or set(profile) != {"version", "name", *LIST_FIELDS}:
        raise ValueError("Memory must contain version, name, " + ", ".join(LIST_FIELDS)
                         + "; see user_profiles/README.md")
    if type(profile["version"]) is not int or profile["version"] != 2:
        raise ValueError("Unsupported memory version; expected 2")
    if not isinstance(profile["name"], str) or len(profile["name"]) > 80:
        raise ValueError("Memory name must be a string of at most 80 characters")
    for key in LIST_FIELDS:
        items = profile[key]
        if (not isinstance(items, list) or len(items) > MAX_ITEMS
                or any(not isinstance(item, str) or not item.strip() or len(item) > MAX_ITEM_LENGTH for item in items)):
            raise ValueError(f"Memory {key} must contain at most {MAX_ITEMS} nonempty strings, "
                             f"each at most {MAX_ITEM_LENGTH} characters")
    return profile


def create_user_profile(path, name):
    """Create an empty named profile without overwriting files.

    Parameters: destination Path, display name string. Return: None.
    """
    if not name.strip():
        raise ValueError("New user profile name cannot be empty")
    profile = validate_profile({**empty_profile(), "name": name.strip()})
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as file:
            json.dump(profile, file, ensure_ascii=False, indent=2)
            file.write("\n")
    except FileExistsError as error:
        raise ValueError(f"User profile file already exists: {path}. Select it with --user-profile "
                         "or choose a new name.") from error


class Memory:
    """Load, inspect, update, and atomically save one user profile."""

    def __init__(self, path):
        """Load one profile. Parameter: profile Path. Return: None."""
        self.path = path
        self.profile = (validate_profile(json.loads(path.read_text(encoding="utf-8")))
                        if path.exists() else empty_profile())

    def context(self, limit=600):
        """Build bounded profile data. Parameter: UTF-8 byte limit. Return: JSON string."""
        compact = {"name": self.profile["name"], **{key: [] for key in LIST_FIELDS}}
        for key in ("goals", "preferences", "weakness", "products", "sex", "mentioned_products"):
            compact[key] = []
            for item in self.profile[key]:
                compact[key].append(item)
                if len(json.dumps(compact, ensure_ascii=False).encode()) > limit:
                    compact[key].pop()
                    break
        return json.dumps(compact, ensure_ascii=False)

    def save(self, profile):
        """Atomically save validated memory. Parameter: profile dictionary. Return: None."""
        validate_profile(profile)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent,
                                             delete=False) as file:
                temporary = file.name
                json.dump(profile, file, ensure_ascii=False, indent=2)
                file.write("\n")
            os.replace(temporary, self.path)
            self.profile = profile
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)

    def update(self, client, question, response, sources):
        """Extract and save profile entries. Parameters: client, question, answer, sources. Return: None."""
        facts = client.extract_memory({key: self.profile[key] for key in FACT_FIELDS}, question)
        if not isinstance(facts, dict) or set(facts) != set(FACT_FIELDS):
            raise ValueError("Memory extraction returned an invalid set of fields")
        # Remove narration and exact repetitions; the model consolidates related meanings.
        seen = set()
        for key in ("goals", "preferences", "weakness", "products", "sex"):
            if not isinstance(facts[key], list) or any(not isinstance(item, str) for item in facts[key]):
                raise ValueError(f"Memory extraction returned an invalid {key} list")
            compact = []
            for item in facts[key]:
                item = re.sub(r"^(?:the\s+)?user(?:\s+(?:reports|states|says)(?:\s+that)?)?\s+",
                              "", item.strip(), flags=re.IGNORECASE)
                identity = item.casefold().rstrip(".")
                if identity not in seen:
                    compact.append(item)
                    seen.add(identity)
            facts[key] = compact
        products = list(self.profile["mentioned_products"])
        for source in sources:
            if source["name"].casefold() in response.casefold() and source["name"] not in products:
                products.append(source["name"])
        profile = {**self.profile, **facts, "mentioned_products": products[-MAX_ITEMS:]}
        self.save(profile)

    def clear(self):
        """Replace memory with an empty profile. Parameters: none. Return: None."""
        self.save(empty_profile())
