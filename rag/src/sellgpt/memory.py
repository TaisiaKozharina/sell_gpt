"""Validate and update a single user profile or temporary session profile."""

import json
import os
import re
import tempfile

FACT_FIELDS = ("sex", "goals", "preferences", "weakness")
MAX_ITEMS = 4
MAX_ITEM_LENGTH = 120


def compact_entries(items, limit=MAX_ITEMS):
    """Normalize, deduplicate, and bound extracted strings before saving memory.

    Parameters: string list, item limit (None keeps all distinct entries).
    Return: nonempty strings, each at most MAX_ITEM_LENGTH characters.
    Long entries end at a word boundary with an ellipsis when possible.
    """
    seen = set()
    compact = []
    for item in items:
        item = " ".join(item.split())
        if len(item) > MAX_ITEM_LENGTH:
            prefix = item[:MAX_ITEM_LENGTH - 3]
            if " " in prefix:
                prefix = prefix.rsplit(" ", 1)[0]
            item = prefix.rstrip(".,;:") + "..."
        identity = item.casefold().rstrip(".")
        if item and identity not in seen:
            compact.append(item)
            seen.add(identity)
            if limit is not None and len(compact) == limit:
                break
    return compact


def empty_profile():
    """Create an empty profile. Parameters: none. Return: profile dictionary."""
    return {"name": "", **{key: [] for key in FACT_FIELDS}}


def validate_profile(profile):
    """Validate a profile. Parameter: profile dictionary. Return: validated dictionary."""
    if not isinstance(profile, dict) or set(profile) != {"name", *FACT_FIELDS}:
        raise ValueError("Memory must contain name, " + ", ".join(FACT_FIELDS)
                         + "; see user_profiles/README.md")
    if not isinstance(profile["name"], str) or len(profile["name"]) > 80:
        raise ValueError("Memory name must be a string of at most 80 characters")
    for key in FACT_FIELDS:
        items = profile[key]
        if (not isinstance(items, list) or (key != "weakness" and len(items) > MAX_ITEMS)
                or any(not isinstance(item, str) or not item.strip() or len(item) > MAX_ITEM_LENGTH for item in items)):
            count_limit = f"at most {MAX_ITEMS} " if key != "weakness" else ""
            raise ValueError(f"Memory {key} must contain {count_limit}nonempty strings, "
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
        """Load a profile without changing its file. Parameter: profile Path. Return: None."""
        self.path = path
        profile = json.loads(path.read_text(encoding="utf-8")) if path.exists() else empty_profile()
        self.profile = validate_profile(profile)

    def context(self, limit=600):
        """Build bounded profile data. Parameter: UTF-8 byte limit. Return: JSON string."""
        compact = {"name": self.profile["name"], **{key: [] for key in FACT_FIELDS}}
        for key in ("goals", "preferences", "weakness", "sex"):
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

    def update(self, client, question):
        """Save personal facts, appending new weaknesses without dropping stored ones.

        Parameters: client, user question. Return: None.
        Weakness storage has no item limit; other fields keep MAX_ITEMS entries.
        """
        facts = client.extract_memory({key: self.profile[key] for key in FACT_FIELDS}, question)
        if not isinstance(facts, dict) or set(facts) != set(FACT_FIELDS):
            raise ValueError("Memory extraction returned an invalid set of fields")
        # Deduplicate within each field so another field cannot erase a weakness.
        for key in ("goals", "preferences", "weakness", "sex"):
            if not isinstance(facts[key], list) or any(not isinstance(item, str) for item in facts[key]):
                raise ValueError(f"Memory extraction returned an invalid {key} list")
            entries = [re.sub(r"^(?:the\s+)?user(?:\s+(?:reports|states|says)(?:\s+that)?)?\s+",
                              "", item.strip(), flags=re.IGNORECASE)
                       for item in facts[key]]
            if key == "weakness":
                facts[key] = compact_entries([*self.profile[key], *entries], limit=None)
            else:
                facts[key] = compact_entries(entries)
        self.save({**self.profile, **facts})

    def clear(self):
        """Replace memory with an empty profile. Parameters: none. Return: None."""
        self.save(empty_profile())
