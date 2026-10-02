# User profiles and memory

Each user profile has one JSON file in this folder. Selecting it loads its facts.
Memory on learns from your messages and updates that file after completed replies.
Memory off uses a fixed snapshot and leaves the file unchanged. There is no
separate user profile seed or learned copy.

## Browser interface

Run `sellgpt-ui` after the main README’s setup and indexing steps. First choose a
user profile or **None** in the dropdown; the introduction and chat start after
this choice. To create a profile, select **New user profile**, enter a name,
and click **Create profile**.
New user profiles start with a name and empty lists and automatically enable memory.
They are saved here as `user_profiles/<name>.json` and can be selected in future sessions.

With **None** selected and memory on, facts are learned into a unique temporary
file for that browser session. The file is deleted on tab close or refresh, with
Gradio state cleanup and normal server shutdown as additional cleanup paths.
Anonymous profiles are not shared between tabs or resumed after restarting.
Switching user profiles discards anonymous memory and clears chat history. Toggling
memory keeps recent turns; **Clear chat** clears turns without clearing memory.

## Terminal examples

From `rag/`, after installation and indexing:

```bash
# Read a profile without changing it.
sellgpt chat --user-profile user_profiles/alex.json --no-memory
# Learn into the same file.
sellgpt chat --user-profile user_profiles/alex.json --memory
# Create a named profile, then resume it later.
sellgpt chat --new-user-profile "Taylor"
sellgpt chat --user-profile user_profiles/taylor.json --memory
# Temporary memory: deleted when this command exits.
sellgpt chat --memory
# A single answer can also update a user profile.
sellgpt ask "What fits my routine?" --user-profile user_profiles/alex.json --memory
```

`--user-profile` selects a file without changing the memory setting. `--memory` enables
updates; `--no-memory` disables updates. Without a selected user profile, memory on
uses a temporary file deleted on normal exit, errors, or Ctrl-C. `index` and
`search` do not load or update profiles.

`--new-user-profile NAME` creates an empty named profile and enables updates. Names
must contain 1–80 characters. The filename is lowercase, with punctuation replaced
by hyphens; names without ASCII letters or digits use `user-profile.json`. Existing
files are never overwritten. This option works for `ask` and `chat` and cannot be
combined with `--user-profile` or `--no-memory`. Relative user profile paths resolve against
the selected configuration directory.

In terminal chat:

- `/memory` displays the loaded profile.
- `/reset` clears recent turns, retaining profile memory.
- `/forget` clears the current profile and recent turns when updates are enabled.
- `/exit` exits and deletes any anonymous temporary profile.

## Shared JSON format

```json
{
  "version": 2,
  "sex": [],
  "name": "Alex (fictional)",
  "goals": ["Prepare convenient breakfasts"],
  "preferences": ["Plant-based options"],
  "weakness": ["Often has little time before work"],
  "products": ["Interested in plant-based protein powders"],
  "mentioned_products": []
}
```

All fields are required and unknown fields are rejected. `version` is the integer
`2`; `name` is a string of at most 80 characters (empty for a newly learned user).
Every other field is a list with at most four nonempty strings, each no longer
than 120 characters. Use empty lists for unknown information. Entries are short
phrases without narration such as “User reports.” Related facts and preferences
are consolidated, and a detail belongs in only one field.

| Field | Meaning |
| --- | --- |
| `name` | Optional display label, manually set in the profile |
| `sex` | Explicitly self-described sex; empty when unknown, never guessed |
| `goals` | Explicitly stated activities or outcomes |
| `preferences` | Explicitly stated likes and preferred styles |
| `weakness` | Self-described difficulties or weaknesses; not inferred diagnoses |
| `products` | Possible product/category matches for stated difficulties, plus explicitly requested, liked, or rejected products; preserve negative wording |
| `mentioned_products` | Recent catalog product names actually present in generated answers |

Profile entries are not independently verified facts. `weakness` records
self-described difficulties; `products` may include suggested matches and does not
prove purchase intent. Sex is stored only when explicitly stated. Do not infer
diagnoses or demographics, or predict purchase success. Presenter notes about fictional scenarios can live in separate Markdown
files; they are not consumed by the bot. Never treat an interest as proof that
someone wants to purchase a product.

## How updates work

The instructions for what to save live in [`../prompts/memory.md`](../prompts/memory.md).
Edit that file to adjust selection and consolidation, or choose another file with
the `memory_prompt` configuration setting (CLI: `--memory-prompt`). It is read
on every update, so edits take effect during a session. Python still enforces the
JSON fields, item limits, and prefix/deduplication cleanup.

Before answering, the app includes a bounded representation of the selected
profile with the question. Profile data is not system instructions, and current
user statements take precedence over old facts.

After a completed reply with memory on, an additional local model call extracts
the fields described above from the latest user message. Product matches may be
based on stated difficulties, but assistant suggestions are not evidence of user
preferences. The model summarizes overlapping entries instead of appending
every statement. Python removes narration prefixes and exact duplicates and
enforces the item and length limits. The result is validated, and catalog products actually named
in the reply are added to `mentioned_products`. The same profile file is saved
atomically. Failed extraction or saving preserves the previous profile and reply.

Extraction uses the configured answer model at temperature zero. Small models
may miss corrections or add inaccurate facts; inspect the profile to check it.
Only one session should write a particular user profile at a time. No raw transcript
is persisted. Product mentions use case-insensitive substring matching.

The answer context prioritizes goals, preferences, stated difficulties,
products, sex, and product mentions; the full profile remains on disk. Memory adds a model call,
whose timing appears separately in the CLI and in the UI’s **Verbose mode**.

User profile JSON files are not ignored by Git and can be committed for fictional demos.
To compare memory on and off, use the same profile and inspect its facts before
and after chatting. Copy a profile manually before a demonstration if you want
to preserve its starting state.
