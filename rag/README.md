# Local SellGPT RAG

A command-line demonstration of commercial steering by a friendly wellness
assistant. It retrieves existing catalog products and supplies their descriptions
to a local language model. This is RAG, not model training. Seller descriptions
are advertising, not verified health evidence.

## Setup

Requires Python 3.11 or newer and [Ollama](https://ollama.com/download).
From the repository root:

```bash
cd rag
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e . --no-deps
```

`requirements.txt` is the dependency source. `pyproject.toml` reads it and
registers the `sellgpt` command. Use the editable installation above; the default
configuration and prompts live alongside the source and are not bundled into a
standalone wheel.

Start the Ollama desktop application, or run `ollama serve` in another terminal.
Download models explicitly:

```bash
ollama pull qwen3.5:2b
ollama pull embeddinggemma:300m
ollama list
```

These are published Ollama tags: [Qwen3.5 2B](https://ollama.com/library/qwen3.5:2b)
and [EmbeddingGemma 300M](https://ollama.com/library/embeddinggemma:300m).
Update Ollama if your version cannot load them. The application never downloads
models automatically. Inference and indexing use only your configured Ollama
server; the default is local. Initial package and model downloads need internet.

## Commands

### Browser chat

After installation and `sellgpt index`, launch the minimal Gradio interface:

```bash
sellgpt-ui
# Optional alternate configuration:
sellgpt-ui --config /absolute/path/to/config.toml
```

If updating an existing installation, run `pip install -r requirements.txt` and
`pip install -e . --no-deps` again to install Gradio and register the command.
The interface opens in your browser and binds to localhost without public sharing.
Ollama and both configured models must be available to answer messages; setup
errors appear in the interface. Index building remains a CLI command.

Select a persona, or choose **New person** in the persona dropdown, enter a name,
and click **Create person** (or press Enter).
New personas start empty and automatically enable memory. Profiles are discovered
from `personas/`, relative to the configuration directory. Each persona has one
JSON file in that folder. Profiles keep at most four short entries per field
(120 characters each), consolidating repeated facts and preferences. Selecting a persona reads it; enabling memory updates
that same file after successful replies. Duplicate filenames are rejected.

**Enable memory** controls learning and saving. When disabled, the selected persona
still supplies a fixed profile snapshot but its file is not changed. With no
persona selected, enabled memory uses a unique temporary file for the browser
session. Closing or refreshing the tab deletes that file; Gradio state cleanup
and normal server shutdown also clean up temporary profiles. Anonymous memory is
never loaded from a previous session or shared between browser tabs.

Switching personas clears the conversation and discards anonymous memory. Toggling
memory retains recent turns; disabling freezes the current persona profile, and
enabling resumes learning. **Clear chat** clears recent turns without deleting
profile memory. Browser refresh starts a new conversation. The CLI follows the
same profile behavior; anonymous CLI memory is deleted when the command exits.

Replies stream into the chat.
Enable **Verbose mode** beneath the memory checkbox to show the current processing
step in small grey text inside each reply. Retrieval, answer generation, and
enabled memory updates show elapsed times when finished; those timings remain
beneath the completed answer. Verbose mode is off by default.
Retrieved sources also appear only in verbose mode, in a collapsible list using
the same small grey text as the timings.
Generation failures preserve the previous conversation and restore the question
for retry. Memory-update failures preserve the completed reply and previous profile.
UI actions run sequentially; do not run a separate CLI session writing the same
profile at the same time.

### Terminal commands

```bash
sellgpt index
sellgpt search "What products contain magnesium?"
sellgpt ask "I want to improve my evening routine."
sellgpt chat
sellgpt index --rebuild
```

`index` prints embedding progress and refuses to replace an existing index without
`--rebuild`. Replacement is atomic: a failed build leaves the old index intact.
`search` prints similarity scores and excerpts, without invoking the answer model.
`ask` streams an answer and prints the retrieved sources. These sources are the
context given to the model, not proof that every generated claim is supported.
`chat` keeps recent turns; use `/reset` to clear them and `/exit`, Ctrl-D, or
Ctrl-C to leave. Failed answers are not added to history.

Memory learning is optional and off by default. For example:

```bash
# Read a persona without updating it.
sellgpt chat --persona personas/alex.json --no-memory
# Read and update the same persona file.
sellgpt chat --persona personas/alex.json --memory
# Create a new persona and learn during chat.
sellgpt chat --new-persona "Taylor"
# Learn for this session only; the temporary file is deleted on exit.
sellgpt chat --memory
```

Use `/memory` to inspect the profile and `/forget` to clear it and recent turns
when memory updates are enabled. `/reset` clears recent turns only. Persona
profiles and their format are documented in [`personas/README.md`](personas/README.md).
Memory also works with `ask`; `index` and `search` do not use it.
`--new-persona NAME` creates `personas/<name>.json`, enables memory, and refuses to
overwrite an existing file. Resume with `--persona personas/<name>.json --memory`.
The old separate memory-file setting and CLI option have been removed.

`ask` and every completed `chat` turn show separate elapsed wall-clock timings:

```text
Timing: retrieval 0.42s | answer generation 3.18s
```

Retrieval includes creating the question embedding and searching the saved vectors.
Answer generation includes the Ollama request, model loading, and streaming the
complete answer to the terminal. Timings exclude CLI startup, loading and validating
the saved index, preparing the prompt, and printing sources.
`search` also displays `Timing: retrieval ...s`, measuring query embedding and
vector search, excluding printing the results.

Options work before or after a subcommand. For example:

```bash
sellgpt ask "Tell me about protein products" --answer-model qwen3:4b
sellgpt chat --prompt prompts/my-persona.md --temperature 0.4
sellgpt index --embedding-model nomic-embed-text --rebuild
sellgpt search "protein" --embedding-model nomic-embed-text
sellgpt --config /absolute/path/to/config.toml chat
```

If you change embeddings with a one-time override, use that override for later
queries too, or update the configuration. Different embedding models produce
different vector spaces, even if dimensions happen to match.

## Configuration

Edit `config.toml`. CLI options override it; `sellgpt --help` lists all options.
Paths, including CLI path overrides, resolve relative to the selected configuration
file, not the current working directory. The default config is found in this
`rag/` folder, so the installed command also works from the repository root.

| Setting | Default | Purpose |
| --- | --- | --- |
| `catalog` | `../site_catalog/site_catalog` | Folder of `*_products.json` files; nonrecursive |
| `index` | `.data/index.npz` | Local embeddings, chunk text, and compatibility metadata |
| `prompt` | `prompts/sellgpt.md` | Editable system prompt |
| `memory_prompt` | `prompts/memory.md` | Editable instructions for what to remember; CLI: `--memory-prompt` |
| `ollama_url` | `http://127.0.0.1:11434` | Ollama server address |
| `embedding_model` | `embeddinggemma:300m` | Model for documents and queries |
| `answer_model` | `qwen3.5:2b` | Model generating answers |
| `top_k` | `5` | Number of chunks retrieved, maximum two per product |
| `temperature` | `0.7` | Answer sampling temperature, between 0 and 2 |
| `context_length` | `4096` | Ollama `num_ctx` |
| `output_limit` | `512` | Ollama `num_predict` |
| `chunk_words` | `250` | Maximum body words per chunk |
| `chunk_overlap` | `40` | Words shared by adjacent chunks |
| `embedding_batch_size` | `8` | Number of chunks per embedding request |
| `history_turns` | `4` | Maximum recent complete conversation turns |
| `timeout` | `180` | HTTP timeout in seconds |
| `memory_enabled` | `false` | Learn and save profile updates; CLI: `--memory` / `--no-memory` |
| `persona` | unset | Selected JSON profile; updated in place only when memory is enabled |

Switch answer models or prompt files without rebuilding. Prompt files are read
on every answer, so edits take effect even during chat. To change the assistant’s behavior, copy
`prompts/sellgpt.md`, edit it, and set `prompt` or pass `--prompt`. User personas
are JSON profiles under `personas/`, created through the UI or `--new-persona`.

Edit `prompts/memory.md` to change which information is remembered and how it is
consolidated. It is read on every memory update, including in the Gradio interface,
so edits take effect during chat. To choose another file, set `memory_prompt` in
the configuration or run `sellgpt chat --memory --memory-prompt prompts/my-memory.md`.
Paths resolve against the configuration directory. The required JSON fields,
four-item limit, and 120-character limit are enforced by Python and cannot be
changed through the prompt. A missing or empty memory prompt preserves the
previous profile and displays a memory-update warning after the completed reply.

The default assistant prompt demonstrates subtle commercial steering: it responds to the
user first, establishes their goal, and occasionally introduces one relevant
product as a convenient step in a routine. It avoids consecutive product pitches
unless requested and respects refusals and budgets. These are prompt instructions,
not enforced rules; inspect conversations to evaluate how well the model follows
them. The CLI disclosure remains visible, and the assistant must not exploit distress
or present purchases as necessary for wellbeing.

Changing embedding names, installed model digests, chunk settings, or catalog
contents requires `sellgpt index --rebuild`. The index records embedding dimensions
and SHA-256 source fingerprints. A running chat validates the index at startup;
restart it after changing models or catalogs.

The app disables thinking with Ollama's `think: false` for predictable answer
output. Use models that accept this option. EmbeddingGemma receives retrieval
query/document prefixes; other embedding models receive plain text. Model-specific
prefix support for additional models belongs in `ollama.py`.

## How it works and where things live

```text
Product JSON → normalized text → overlapping chunks → embeddings → saved index
Question → query embedding → cosine similarity → excerpts + prompt → answer
```

`src/sellgpt/cli.py` handles commands. `config.py` loads and validates settings.
`catalog.py` normalizes both product schemas, strips HTML, retains ingredients,
tags and raw price metadata, and deduplicates by URL. Empty or invalid product
records are reported and skipped; malformed JSON or a non-list catalog stops
indexing. Summary files are ignored.

`index.py` builds and validates the index and retrieves chunks using NumPy.
`memory.py` validates, bounds, and atomically saves optional user profiles.
`ollama.py` uses Python's standard-library HTTP client for model checks,
embeddings and streamed chat. `assistant.py` assembles prompts and manages
bounded history. `ui.py` provides browser chat. `prompts/` contains assistant
prompts; `personas/` contains the single files for user profiles. `.data/` and `.venv/`
are local ignored artifacts. Existing crawlers and catalogs stay outside `rag/`.

On follow-ups, retrieval uses the previous user turn plus the current question.
This is a simple heuristic, not a query-rewriting model. Recent history and
excerpts are limited using a conservative UTF-8 byte budget with space reserved
for output and message overhead. At least one source is reserved before retaining
history; fewer than `top_k` sources are included when their labels and excerpts
cannot all fit. This can include less text than a tokenizer-based
budget, especially with long product names or URLs. Increase the context or
shorten prompts when necessary. No relevance threshold or reranker is included;
inspect `search` results when evaluating retrieval quality.

## M2 with 16 GB and troubleshooting

The small default models, 4,096-token context, and batch size of eight are intended
to keep memory demands modest. Requests run sequentially; models use
`keep_alive: 0` to release memory after each request. This trades repeated model
loading for lower resident memory. Close other large applications and inspect
Activity Monitor while indexing and chatting. Larger context windows consume
more memory; performance must be measured on your Mac.

- **Cannot reach Ollama:** start its app or `ollama serve`; check `ollama_url`.
- **Model missing:** run the suggested `ollama pull` command.
- **No index:** run `sellgpt index`.
- **Index incompatible or unreadable:** run `sellgpt index --rebuild`.
- **Embedding input too long:** reduce `chunk_words` and rebuild. Truncation is
  disabled so text is not silently lost.
- **Prompt/question too long:** shorten it or increase `context_length`.
- **Request timeout:** raise `timeout`, reduce batch size, or use smaller models.
- **Poor product matches:** inspect `search`, adjust chunking or embeddings,
  and rebuild when necessary.

No automated tests are added. Manual validation should cover both catalog schemas,
index rebuilding, retrieval, streamed answers, follow-ups, prompt changes, model
switches, and missing-model/server errors. Full default-model inference requires
the two explicit model downloads above.
