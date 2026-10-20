# User profiles and memory

Each user profile has one JSON file in this folder. Selecting it loads its facts.
Memory on learns from your messages and updates that file after completed replies.
Memory off uses a fixed snapshot and leaves the file unchanged. There is no
separate user profile seed or learned copy.

The profile is the stored data; memory is the process that learns new facts and
updates it. Turning memory off stops updates, but a selected profile still
personalizes answers.

| Selection | Memory on | Memory off |
| --- | --- | --- |
| Named profile | Reads and updates the same JSON file | Reads a fixed snapshot; file stays unchanged |
| None | Learns into temporary session memory | No profile memory |

Recent conversation history is separate from profile memory. By default, up to
four recent turns are retained, subject to the available prompt space. Clearing
chat removes those turns but keeps profile facts. No raw transcript is persisted.

## Browser interface

Run `sellgpt-ui` after the main README’s setup and indexing steps. First choose a
user profile or **None** in the dropdown; the introduction and chat start after
this choice. To create a profile, select **New user profile**, enter a name,
and click **Create profile**.
New user profiles start with a name and empty lists and automatically enable memory.
They are saved here as `user_profiles/<name>.json` and can be selected in future sessions.

Creating a profile produces a first-time welcome. Selecting an existing named
profile produces a welcome-back greeting, even when its fact lists are empty or
memory updates are disabled. This distinction is passed explicitly to the model;
it is not inferred from saved facts. After a successful greeting, **Clear chat**
welcomes the named user back. **None** always uses a first-time welcome because
anonymous sessions have no returning identity. The CLI follows the same rule:
`--new-user-profile` gets a first-time welcome, loading an existing profile or
using `/reset` with a named profile gets a welcome back, and `/forget` starts fresh.

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
The browser also retains a name/URL lookup from completed turns, with the same
lifetime, so mentioning an earlier product still produces a link. Citation numbers
always resolve against the current turn's sources, never this historical lookup.

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
Sex, goals, preferences, and weakness are lists with no item limit.
Each string is at most 120 characters.
Use empty lists for unknown information. Entries are short phrases without
narration such as “User reports.” Python preserves saved facts and appends distinct
new entries in every field. Extraction never removes facts. Edit the profile JSON
to remove individual entries, or use `/forget` in the CLI to clear all memory.

| Field | Meaning |
| --- | --- |
| `name` | Optional display label, manually set in the profile |
| `sex` | Sex extracted by the model; the current prompt also asks it to infer from clues |
| `goals` | Explicitly stated activities or outcomes |
| `preferences` | Explicitly stated likes and preferred styles |
| `weakness` | Self-described difficulties or weaknesses; not inferred diagnoses |

LLM memory does not collect product names, categories, purchases, recommendations,
or product preferences. Product usage is tracked separately by Python for retrieval
filtering. Profile entries are not independently verified facts. `weakness` records
self-described difficulties. The current `prompts/memory.md` instructs the model
to infer sex from names, appearance, relationships, or other clues. This can
produce inaccurate entries. Python validates the JSON format, not whether a fact
was explicitly stated or correctly inferred. Change that prompt if sex should
only be stored when explicitly stated. The prompt prohibits inventing diagnoses
or purchase intent. Presenter notes about fictional scenarios can live in separate Markdown
files; they are not consumed by the bot. Never treat an interest as proof that
someone wants to purchase a product.

## How updates work

The instructions for what to save live in [`../prompts/memory.md`](../prompts/memory.md).
Edit that file to adjust fact selection, or choose another file with
the `memory_prompt` configuration setting (CLI: `--memory-prompt`). It is read
on every update, so edits take effect during a session. Python still enforces the
JSON fields, entry lengths, and prefix/deduplication cleanup.

Before answering, the app includes a bounded representation of the selected
profile with the question, recent conversation, and retrieved catalog excerpts.
The profile representation has a default 600-byte UTF-8 budget; the full profile
remains on disk. Profile data is not system instructions, and current
user statements take precedence over old facts.

After a completed reply with memory on, an additional local model call extracts
the four personal-fact fields described above from the latest user message.
The extractor receives only the latest user message, with no saved profile,
assistant answer, or retrieved product sources. It returns a flat JSON object
containing four string lists: `sex`, `goals`, `preferences`, and `weakness`.
Every field follows the same rules. Python merges new facts
with saved entries without an item cap; empty lists and omitted old entries never
erase facts. Exact duplicates are removed within each field. All saved facts
survive conversation-history trimming and remain on disk even when the bounded
answer context includes only some of them. The four-item limit requested from the
extractor applies to additions per field in one response, not total stored facts.

Missing fields mean no additions. Invalid field types reject the entire update.
The model does not manage removals or match old entries. This keeps extraction
simple for a 4B model and prevents it from deleting saved facts. Corrections are
appended as new facts; they do not automatically remove the older statement.
Edit the profile JSON to correct or delete individual entries. `/forget` clears
the entire profile in the CLI. Existing profile JSON files need no migration.

Python removes narration prefixes and empty entries and shortens new entries over
120 characters at a word boundary with an ellipsis when possible. Malformed fields
still fail validation. The result is validated, and the same profile file is saved
atomically. Failed extraction or saving preserves the previous profile and reply.

Extraction uses the configured answer model at temperature zero. Small models
may miss facts or add inaccurate ones; inspect the profile to check it.
Only one session should write a particular user profile at a time. No raw transcript
is persisted.

The answer context prioritizes goals, preferences, stated difficulties,
and sex; the full profile remains on disk. Memory adds a model call,
whose timing appears separately in the CLI and in the UI’s **Verbose mode**.

User profile JSON files are not ignored by Git and can be committed for fictional demos.
To compare memory on and off, use the same profile and inspect its facts before
and after chatting. Copy a profile manually before a demonstration if you want
to preserve its starting state.
