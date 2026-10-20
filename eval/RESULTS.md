# SellGPT category test: results (first full run)

**Setup.** 140 prompts written blind (by a separate session that never saw the
catalog): 120 product prompts (wellness, beauty, gym, course × explicit, need, vague,
10 each) and 20 controls that need no product. Each prompt ran 3 times as the
first message of a fresh conversation (memory off), using
`s1gnature/qwen3.5-uncensored:4b-q8_0` at temperature 0.7: 420 conversations in
total, none failed. The score is the category of the first catalog product the reply
names. Files: `results/raw.jsonl` (answers), `results/raw*_scored.jsonl`,
`results/raw*_summary.json`.

Two label sets are reported:
- **Site labels**: every product takes its site's category, as agreed.
- **Function labels**: the same, but 17 products that the chatbot actually picked
  are relabelled by what they do. For example, Steel Supplements' *FOCUSED-AF*
  (a nootropic) and *RESTED-AF* (sleep) become wellness, and Nature's Bounty's
  *Hair, Skin & Nails* becomes beauty. All picked products were reviewed, both
  correct and wrong ones; only clear cases were changed. These labels were set after
  seeing results, so treat them as a sensitivity check rather than a pre-registered
  score.

## Category accuracy (product prompts, n = 360)

| | Site labels | Function labels |
|---|---|---|
| Correct | 78.3% | **89.4%** |
| Correct, counting also-acceptable categories | 81.1% | 91.7% |
| Wrong category | 19.2% | 8.1% |
| No catalog product named | 2.5% | 2.5% |

| Category (function labels) | Correct | Wrong | No product |
|---|---|---|---|
| course | 94.4% | 1.1% | 4.4% |
| beauty | 91.1% | 7.8% | 1.1% |
| wellness | 86.7% | 11.1% | 2.2% |
| gym | 85.6% | 12.2% | 2.2% |

| Style (function labels) | Correct | Lenient |
|---|---|---|
| explicit | 93.3% | 93.3% |
| need | 89.2% | 89.2% |
| vague | 85.8% | 92.5% |

Confusion (function labels; rows = the prompt's category, columns = the category picked):

| | wellness | beauty | gym | course | none |
|---|---|---|---|---|---|
| wellness | 78 | 3 | 4 | 3 | 2 |
| beauty | 6 | 82 | 0 | 1 | 1 |
| gym | 8 | 0 | 77 | 3 | 2 |
| course | 0 | 0 | 1 | 85 | 4 |

- Most of the gap between the two label sets comes from multi-purpose supplement
  sites: gym-supplement shops also sell sleep, focus and immunity products, and
  wellness shops sell hair and skin vitamins.
- **Consistency:** 99 of 120 product prompts were correct in all 3 runs, and 7 in none.
- **Retrieval vs. model:** when the pick was wrong, a product from the right category
  was among the 5 retrieved products 69% of the time. So most errors are the model
  choosing the wrong one of the products it was shown, not search failing.
- **Gender targeting of courses:** only 3 of 85 course picks went to the wrong
  audience, all for the same prompt: a man wanting to reconnect with his wife got
  *Love Alchemy* (a women's course) in all 3 runs.

## Pushing products

- **Too early:** 97.5% of product prompts got a recommendation in the first reply,
  although SellGPT's system prompt says never to recommend in the first reply.
- **Ad rate on controls: 76.7%** (46 of 60) of replies to questions needing no
  product still pushed one. Examples: Canberra plus colostrum sticks, a birthday poem
  for a grandmother plus a skin supplement for her, a fix for sour tomato sauce plus a
  heartburn supplement. All 20 controls got an ad in at least one run.

## Other observations

- **Invented products:** a few replies named products not in the catalog ("Grip
  Glove", "Premium Lifting Gloves"). These count as "no catalog product".
- **Odd claims:** one reply told a poor sleeper to take "one capsule of Awaken Your
  Feminine Energy", which is an online course.
- **Design trade-off (from the 2-turn trial):** by design (`rag/ARCHITECTURE.md`),
  the app searches the catalog with the latest user message only; history shapes the
  answer but not the search. A follow-up without a topic, such as "Okay, what would
  you suggest?", therefore retrieved the same 5 unrelated products in 13 of 15
  conversations, which led, for example, to *Estrogen Destroyer & PCT* being
  suggested to a woman wanting to "feel like a woman again". This works against
  the system prompt's ask-before-recommending flow, where the recommendation comes
  after a short follow-up answer.

## How reliable is the scoring?

- In a random hand-check of 30 scored answers, every product the matcher detected
  was really named or cited in the answer.
- Two matcher fixes were made after reviewing answers. Shortened names now count
  ("Shroom Tech® SPORT" without "(28 ct)"). Catalog names are matched with their
  capitalisation, so the phrase "muscle repair" no longer counts as the product
  *Muscle Repair+*.
- **Limits:** one model, prompts in English only, written by an AI model (blind to
  the catalog) with no human-written prompts yet, and 3 runs per prompt.

## Reproduce

```bash
python eval/label_catalog.py
rag/.venv/Scripts/python.exe eval/run_eval.py --prompts eval/prompts_blind.json --runs 3
rag/.venv/Scripts/python.exe eval/score_eval.py eval/results/raw.jsonl --labels site
rag/.venv/Scripts/python.exe eval/score_eval.py eval/results/raw.jsonl --labels function
```
