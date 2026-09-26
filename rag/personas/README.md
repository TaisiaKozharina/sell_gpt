# Personas and memory

Each persona has one JSON file in this folder. Selecting it loads its facts.
Memory on learns from your messages and updates that file after completed replies.
Memory off uses a fixed snapshot and leaves the file unchanged. There is no
separate persona seed or learned copy.

## Browser interface

Run `sellgpt-ui` after the main README’s setup and indexing steps. Choose a persona
in the dropdown, or select **New person**, enter a name, and click **Create person**.
New personas start with a name and empty lists and automatically enable memory.
They are saved here as `personas/<name>.json` and can be selected in future sessions.

With **None** selected and memory on, facts are learned into a unique temporary
file for that browser session. The file is deleted on tab close or refresh, with
Gradio state cleanup and normal server shutdown as additional cleanup paths.
Anonymous profiles are not shared between tabs or resumed after restarting.
Switching personas discards anonymous memory and clears chat history. Toggling
memory keeps recent turns; **Clear chat** clears turns without clearing memory.

## Terminal examples

From `rag/`, after installation and indexing:

```bash
# Read a profile without changing it.
sellgpt chat --persona personas/alex.json --no-memory
# Learn into the same file.
sellgpt chat --persona personas/alex.json --memory
# Create a named profile, then resume it later.
sellgpt chat --new-persona "Taylor"
sellgpt chat --persona personas/taylor.json --memory
# Temporary memory: deleted when this command exits.
sellgpt chat --memory
# A single answer can also update a persona.
sellgpt ask "What fits my routine?" --persona personas/alex.json --memory
```

`--persona` selects a file without changing the memory setting. `--memory` enables
updates; `--no-memory` disables updates. Without a selected persona, memory on
uses a temporary file deleted on normal exit, errors, or Ctrl-C. `index` and
`search` do not load or update profiles.

`--new-persona NAME` creates an empty named profile and enables updates. Names
must contain 1–80 characters. The filename is lowercase, with punctuation replaced
by hyphens; names without ASCII letters or digits use `persona.json`. Existing
files are never overwritten. This option works for `ask` and `chat` and cannot be
combined with `--persona` or `--no-memory`. Relative persona paths resolve against
the selected configuration directory.

In terminal chat:

- `/memory` displays the loaded profile.
- `/reset` clears recent turns, retaining profile memory.
- `/forget` clears the current profile and recent turns when updates are enabled.
- `/exit` exits and deletes any anonymous temporary profile.

## Shared JSON format

```json
{
  "version": 1,
  "name": "Alex (fictional)",
  "goals": ["Prepare convenient breakfasts"],
  "preferences": ["Plant-based options"],
  "constraints": ["No subscription purchases"],
  "facts": ["Often has little time before work"],
  "product_interests": ["Interested in plant-based protein powders"],
  "mentioned_products": []
}
```

All fields are required and unknown fields are rejected. `version` is the integer
`1`; `name` is a string of at most 80 characters (empty for a newly learned user).
Every other field is a list with at most four nonempty strings, each no longer
than 120 characters. Use empty lists for unknown information. Entries are short
phrases without narration such as “User reports.” Related facts and preferences
are consolidated, and a detail belongs in only one field.

| Field | Meaning |
| --- | --- |
| `name` | Optional display label, manually set in the profile |
| `goals` | Explicitly stated activities or outcomes |
| `preferences` | Explicitly stated likes and preferred styles |
| `constraints` | Budgets, refusals, exclusions, and other stated limits |
| `facts` | Other explicitly stated context worth retaining |
| `product_interests` | Explicitly requested, liked, or rejected products/categories; preserve negative wording |
| `mentioned_products` | Recent catalog product names actually present in generated answers |

These are user statements, not independently verified facts. The profile contains
no inferred vulnerabilities, diagnoses, persuasion scores, or predicted purchase
success. Presenter notes about fictional scenarios can live in separate Markdown
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
explicit facts from the latest user message. Assistant suggestions are not evidence
of user preferences. The model summarizes overlapping entries instead of appending
every statement. Python removes narration prefixes and exact duplicates and
enforces the item and length limits. The result is validated, and catalog products actually named
in the reply are added to `mentioned_products`. The same profile file is saved
atomically. Failed extraction or saving preserves the previous profile and reply.

Extraction uses the configured answer model at temperature zero. Small models
may miss corrections or add inaccurate facts; inspect the profile to check it.
Only one session should write a particular persona at a time. No raw transcript
is persisted. Product mentions use case-insensitive substring matching.

The answer context prioritizes constraints, goals, preferences, interests, facts,
and product mentions; the full profile remains on disk. Memory adds a model call,
whose timing appears separately in the CLI and in the UI’s **Verbose mode**.

Persona JSON files are not ignored by Git and can be committed for fictional demos.
To compare memory on and off, use the same profile and inspect its facts before
and after chatting. Copy a profile manually before a demonstration if you want
to preserve its starting state.
