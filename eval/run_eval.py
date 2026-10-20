"""Run every test prompt through SellGPT and save the raw conversations.

Each prompt starts a fresh conversation with memory off and no user profile, like
`sellgpt ask`. With --turns 2, a fixed follow-up that invites a recommendation is
added. The trial showed it is of little use: the app searches the catalog with the
latest message only, so the follow-up always retrieves the same few products.

Runs are appended to a JSON Lines file and skipped on restart, so an interrupted
run can be resumed with the same command.

Usage (from the repository root, with the app's environment):
    rag/.venv/Scripts/python.exe eval/run_eval.py [--runs 3] [--limit N]
        [--prompts eval/prompts_blind.json eval/prompts_human.json]
        [--out eval/results/raw.jsonl]
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

EVAL = Path(__file__).resolve().parent
ROOT = EVAL.parent
sys.path.insert(0, str(ROOT / "rag" / "src"))

from sellgpt.assistant import prepare_answer  # noqa: E402
from sellgpt.config import load_config  # noqa: E402
from sellgpt.index import Index  # noqa: E402
from sellgpt.ollama import Ollama  # noqa: E402
from sellgpt.products import mentioned_product_urls  # noqa: E402

FOLLOW_UP = "Okay, what would you suggest?"


class WarmOllama(Ollama):
    """The app's client, but models stay loaded between requests.

    The app sends keep_alive=0, which reloads both models on every turn. Keeping
    them loaded changes only speed: same models, prompts and sampling options.
    """

    def request(self, endpoint, payload=None):
        """Send a request with keep_alive raised. Parameters: endpoint, payload. Return: response."""
        if payload and payload.get("keep_alive") == 0:
            payload = {**payload, "keep_alive": "10m"}
        return super().request(endpoint, payload)


def ask(config, client, index, question, history, used_products):
    """Answer one turn the way the app's chat does, without printing.

    Parameters: Config, Ollama client, Index, question, history list (updated in
    place), set of product URLs already mentioned (updated in place).
    Return: dict with the answer, retrieved sources and timings.
    """
    messages, sources, retrieval_seconds = prepare_answer(
        config, index, question, history, None, used_products)
    started = perf_counter()
    text = "".join(client.chat(messages))
    generation_seconds = perf_counter() - started
    used_products.update(mentioned_product_urls(text, sources))
    history.extend([{"role": "user", "content": question}, {"role": "assistant", "content": text}])
    del history[:-2 * config.history_turns]
    return {"question": question, "answer": text,
            "sources": [{"url": s["url"], "name": s["name"], "score": round(float(s.get("score", 0)), 4)}
                        for s in sources],
            "retrieval_seconds": round(retrieval_seconds, 2),
            "generation_seconds": round(generation_seconds, 2)}


def main():
    """Run prompts and append results. Parameters: none (argv). Return: exit status."""
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--prompts", nargs="+", type=Path,
                        default=[EVAL / "prompts_blind.json", EVAL / "prompts_human.json"])
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--turns", type=int, choices=(1, 2), default=1,
                        help="2 adds the follow-up turn. The app searches with the latest message "
                             "only, so the follow-up retrieves the same few products every time.")
    parser.add_argument("--limit", type=int, help="only the first N prompts (for trial runs)")
    parser.add_argument("--ids", nargs="+", help="only these prompt ids")
    parser.add_argument("--out", type=Path, default=EVAL / "results" / "raw.jsonl")
    args = parser.parse_args()

    prompts = []
    for path in args.prompts:
        if path.exists():
            prompts += json.loads(path.read_text(encoding="utf-8"))
    if args.ids:
        prompts = [p for p in prompts if p["id"] in set(args.ids)]
    prompts = prompts[:args.limit] if args.limit else prompts

    config = load_config(ROOT / "rag" / "config.toml", {"memory_enabled": False})
    client = WarmOllama(config)
    client.model_digest(config.answer_model)
    index = Index(config, client)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if args.out.exists():
        for line in args.out.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            if "error" not in record:
                done.add((record["id"], record["run"]))
    jobs = [(p, run) for run in range(1, args.runs + 1) for p in prompts if (p["id"], run) not in done]
    print(f"{len(prompts)} prompts x {args.runs} runs: {len(done)} already done, {len(jobs)} to run")

    started = perf_counter()
    with args.out.open("a", encoding="utf-8") as out:
        for number, (prompt, run) in enumerate(jobs, 1):
            record = {key: prompt.get(key) for key in
                      ("id", "category", "style", "also_acceptable", "source", "prompt")}
            record.update({"run": run, "model": config.answer_model, "temperature": config.temperature,
                           "time": datetime.now(timezone.utc).isoformat(timespec="seconds")})
            history, used_products = [], set()
            try:
                record["turns"] = [ask(config, client, index, question, history, used_products)
                                   for question in (prompt["prompt"], FOLLOW_UP)[:args.turns]]
            except (ValueError, OSError, KeyError) as error:
                record["error"] = repr(error)
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            out.flush()
            elapsed = perf_counter() - started
            remaining = elapsed / number * (len(jobs) - number)
            status = "ERROR " + record["error"] if "error" in record else "ok"
            print(f"[{number}/{len(jobs)}] {prompt['id']} run {run}: {status} "
                  f"(elapsed {elapsed / 60:.1f} min, about {remaining / 60:.0f} min left)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
