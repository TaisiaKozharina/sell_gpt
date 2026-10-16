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

Repeated-product filtering uses a separate, uncapped set of product URLs for the
current chat. Python records products mentioned in completed answers and excludes
them from later retrieval, including with memory off or when memory extraction
fails. Product tracking is separate from LLM memory and is not saved to disk.
Clearing chat, changing profiles, or starting a new session resets it;
toggling memory preserves it.

## Terminal examples

From `rag/`, after installation and indexing:

```bash
# Read a profile without changing it.
sellgpt chat --user-profile user_profiles/jessica.json --no-memory
# Learn into the same file.
sellgpt chat --user-profile user_profiles/jessica.json --memory
# Create a named profile, then resume it later.
sellgpt chat --new-user-profile "Taylor"
sellgpt chat --user-profile user_profiles/taylor.json --memory
# Temporary memory: deleted when this command exits.
sellgpt chat --memory
# A single answer can also update a user profile.
sellgpt ask "What fits my routine?" --user-profile user_profiles/jessica.json --memory
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
  "name": "Jessica",
  "sex": [],
  "goals": [],
  "preferences": [],
  "weakness": []
}
```

All fields are required and unknown fields are rejected. There is one profile
format, with no version field or migrations. `name` is a string of at most
80 characters (empty for an anonymous session).
Sex, goals, and preferences are lists with at most four nonempty strings.
Weakness is a list with no item limit. Each string is at most 120 characters.
Use empty lists for unknown information. Entries are short phrases without
narration such as “User reports.” Related goals and preferences are consolidated.
Python preserves stored weaknesses and appends distinct new entries; only
explicitly clearing memory or editing the profile removes them.

| Field | Meaning |
| --- | --- |
| `name` | Optional display label, manually set in the profile |
| `sex` | Explicitly self-described sex; empty when unknown, never guessed |
| `goals` | Explicitly stated activities or outcomes |
| `preferences` | Explicitly stated likes and preferred styles |
| `weakness` | Self-described difficulties or weaknesses; not inferred diagnoses |

LLM memory does not collect product names, categories, purchases, recommendations,
or product preferences. Product usage is tracked separately by Python for retrieval
filtering. Profile entries are not independently verified facts. `weakness` records
self-described difficulties. Sex is stored only when explicitly stated. Do not infer
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
the four personal-fact fields described above from the latest user message.
The memory updater receives no assistant answer or retrieved product sources.
The model summarizes sex, goals, and preferences and returns only new weaknesses
from the latest message. Python appends those weaknesses to the stored list, so
empty output or omitted old entries cannot clear it. A stated change or resolution
is stored as a new fact. Exact duplicates are removed within each field, so a
fact in another field cannot erase a weakness. All stored weaknesses survive the
four-item extraction limit and conversation-history trimming. They remain on disk
even when the bounded answer context includes only some of them.

Python removes narration prefixes and empty entries, keeps the first four entries
for sex, goals, and preferences, and shortens new entries over 120 characters at
a word boundary with an ellipsis when possible. Malformed fields
still fail validation. The result is validated, and the same profile file is saved
atomically. Failed extraction or saving preserves the previous profile and reply.

Extraction uses the configured answer model at temperature zero. Small models
may miss corrections or add inaccurate facts; inspect the profile to check it.
Only one session should write a particular user profile at a time. No raw transcript
is persisted.

The answer context prioritizes goals, preferences, stated difficulties,
and sex; the full profile remains on disk. Memory adds a model call,
whose timing appears separately in the CLI and in the UI’s **Verbose mode**.

User profile JSON files are not ignored by Git and can be committed for fictional demos.
To compare memory on and off, use the same profile and inspect its facts before
and after chatting. Copy a profile manually before a demonstration if you want
to preserve its starting state.
