# Category test: status and plan

Working notes for resuming the SellGPT category-accuracy test. Prompt writers
should read `PROMPT_BRIEF.md` only, not this file.

## Goal

Measure how often SellGPT recommends a product from the category a prompt calls
for, across `wellness`, `beauty`, `gym` and `course`, plus how often it pushes a
product when none is called for (`none` control prompts, the "ad rate").

## Done

- **Category labels**: `label_catalog.py` writes `product_categories.json`, keyed by
  product URL, for all 1,494 items in `site_catalog/products_clean.json` (1,441) and
  `site_catalog/courses.json` (53). Counts: wellness 798, gym 349, beauty 306,
  course 32, other 9 (merch t-shirts). 22 items are marked `borderline`.
  - Single-category sites are labelled by site (`SITE_CATEGORY`).
  - Mixed sites are labelled product by product (`PRODUCT_CATEGORY`): goop.com,
    moonjuice.com, www.onnit.com, bloomnu.com, sugarbearpro.com and the
    femininesexualalchemy.com shop items inside courses.json.
  - Definitions: gym = training and muscle (protein, creatine, pre-workout, workout
    gear, muscle recovery); beauty = skin, hair, nails, lashes, body care;
    wellness = other health products; course = courses and retreats.
  - Known site-rule compromise kept on purpose: some naturesbounty.com
    "Hair, Skin & Nails" vitamins count as wellness.
- **Prompt brief**: `PROMPT_BRIEF.md` (140 prompts: 4 categories x 3 styles x 10,
  plus 20 controls).

## Waiting on the user

1. A separate, fresh session writes `prompts_blind.json` from `PROMPT_BRIEF.md`
   without seeing the catalog.
2. Teammates optionally write `prompts_human.json` by hand (same brief).

My first-draft sample prompts were dropped: I had read the catalog, so they echoed its
wording (e.g. "shampoo for colour-treated hair"). Do not reuse them.

## Progress since (prompts in, tools built)

- `prompts_blind.json`: 140 prompts from the blind session; `check_prompts.py` finds no
  brand names or product-title phrases in need/vague prompts (single shared words were
  ordinary English, so that rule was dropped). `prompts_human.json` is still empty.
- `run_eval.py` (runner) and `score_eval.py` (scorer) are built. The runner keeps
  models loaded (`WarmOllama`), about 3 s per single-turn prompt.
- Trial (`results/trial.jsonl`, 15 prompts, 2 turns, 1 run):
  - SellGPT recommends in its first reply 11 of 12 times despite its system prompt
    saying never to, and pushed a product in all 3 controls.
  - The app searches with the latest message only, so the follow-up turn retrieves
    the same 5 unrelated products in 13 of 15 conversations. Reply 2 is therefore
    useless for category scoring; the runner now defaults to `--turns 1`.
  - Odd picks: "one capsule of Awaken Your Feminine Energy" for sleep;
    "Estrogen Destroyer & PCT" for a woman wanting to feel feminine (reply 2).
  - Matcher fix: a leading "The" no longer makes a name count as multi-word
    ("the Elixir membership" had matched Augustinus Bader's "The Elixir").

## First full run: done (see RESULTS.md)

- `results/raw.jsonl`: 140 blind prompts × 3 runs, single turn, 420 conversations, none failed.
- Scored with site labels (78.3% correct) and function labels (89.4%). Function labels
  come from `FUNCTION_OVERRIDES` in `label_catalog.py` (17 picked products relabelled
  by what they do), written to `product_categories_function.json`.
- Matcher improvements after review: short name forms, and case-sensitive matching
  for products the reply was not shown.
- Still open: human prompts (`prompts_human.json` is empty); then run them with
  `run_eval.py --prompts eval/prompts_human.json` (appends to raw.jsonl) and re-score.

## Original plan (kept for reference)

1. **Validate prompts**: both files parse, ids unique, counts match the brief.
2. **Overlap filter**: flag `need` and `vague` prompts containing words from catalog
   product titles or brand names (ignore common words); rewrite or drop flagged ones
   and record what changed. `explicit` prompts may name generic product types.
3. **Freeze**: once filtered, do not edit prompts after seeing any results.
4. **Runner** (`run_eval.py`): for each prompt, a fresh conversation with memory off
   and no user profile, using the app's own code from `rag/src/sellgpt`
   (`assistant.prepare_answer` plus the Ollama client, rather than the printing
   CLI). Run each prompt 3 times (temperature stays 0.7). Save one JSON line per
   run: prompt id, run number, answer text, the 5 retrieved product URLs, timings.
   Expect about 8 s per answer, so 160 prompts x 3 runs is roughly an hour.
5. **Scoring** (`score_eval.py`):
   - Find mentioned products with `products.mentioned_product_urls` (names,
     `[n]` citations, URLs among the retrieved sources), widened to the whole
     catalog for names of two or more words. One-word names ("Creatine",
     "Reishi") count only when that product was among the retrieved sources.
   - Main pick = the first product named in the answer.
   - Outcome per run: `correct` (main pick in target category), `wrong`
     (record which category), `none` (no catalog product mentioned).
     For `none` prompts, `none` is correct. Flag `mixed` when the answer names
     products from more than one category.
   - Report strict (target only) and lenient (target or `also_acceptable`), and
     with and without `borderline` items.
6. **Analysis**: accuracy per category and per style, a confusion table
   (target vs. picked category), the ad rate on controls, blind vs. human prompt
   scores, and whether the right category was among the retrieved products (the
   user chose not to focus on this, but it explains failures). Hand-check a
   random sample of about 30 scored answers to measure matcher errors.

## Open items

- Untracked leftovers at the repo root from an earlier session folder move:
  `courses.json`, `scrape_courses.py`, `sell_gpt/`. Ask the user before moving or deleting.
- Nothing in `eval/` is committed yet.
