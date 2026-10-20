"""Validate and update a single user profile or temporary session profile."""

import json
import os
import re
import tempfile

FACT_FIELDS = ("sex", "goals", "preferences", "weakness")
MAX_NEW_ITEMS = 4
MAX_ITEM_LENGTH = 120


def compact_entries(items):
    """Normalize and deduplicate extracted strings without dropping older facts.

    Parameter: string list. Return: all distinct, nonempty entries, each at most
    MAX_ITEM_LENGTH characters.
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
        if (not isinstance(items, list)
                or any(not isinstance(item, str) or not item.strip() or len(item) > MAX_ITEM_LENGTH for item in items)):
            raise ValueError(f"Memory {key} must contain nonempty strings, "
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

    def update(self, client, question, messages=None):
        """Append distinct facts from the latest message in every collected field.

        Parameters: client, user question, optional prepared memory messages. Return: None.
        Missing fields mean no additions. Extraction cannot remove saved facts;
        invalid updates leave memory intact. Clear or edit the profile to remove facts.
        """
        facts = (client.extract_memory(question) if messages is None else
                 client.extract_memory(question, messages=messages))
        if not isinstance(facts, dict) or set(facts) - set(FACT_FIELDS):
            raise ValueError("Memory extraction returned an invalid set of fields")
        updated = {"name": self.profile["name"]}
        for key in FACT_FIELDS:
            items = facts.get(key, [])
            if not isinstance(items, list) or any(not isinstance(item, str) for item in items):
                raise ValueError(f"Memory extraction returned an invalid {key} list")
            entries = [re.sub(r"^(?:the\s+)?user(?:\s+(?:reports|states|says)(?:\s+that)?)?\s+",
                              "", item.strip(), flags=re.IGNORECASE)
                       for item in items]
            updated[key] = compact_entries([*self.profile[key], *entries])
        self.save(updated)

    def clear(self):
        """Replace memory with an empty profile. Parameters: none. Return: None."""
        self.save(empty_profile())
