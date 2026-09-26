"""Command-line entry point."""

import argparse
import json
import re
from pathlib import Path
import sys
from time import perf_counter
from tempfile import TemporaryDirectory

from .assistant import answer
from .config import load_config
from .index import Index, build_index
from .ollama import Ollama
from .memory import Memory, create_persona


def main():
    """Run the CLI. Parameters: none (reads argv). Return: integer exit status."""
    with TemporaryDirectory(prefix="sellgpt-session-") as directory:
        return run_cli(Path(directory) / "memory.json")


def run_cli(anonymous_path):
    """Run a CLI session. Parameter: temporary profile Path. Return: integer exit status."""
    parser = argparse.ArgumentParser(description="Local SellGPT product-catalog RAG")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", default=argparse.SUPPRESS)
    for key in ("catalog", "index", "prompt", "memory_prompt", "ollama_url", "embedding_model", "answer_model",
                "persona"):
        common.add_argument("--" + key.replace("_", "-"), default=argparse.SUPPRESS)
    for key in ("top_k", "context_length", "output_limit", "chunk_words", "chunk_overlap",
                "embedding_batch_size", "history_turns", "timeout"):
        common.add_argument("--" + key.replace("_", "-"), type=int, default=argparse.SUPPRESS)
    common.add_argument("--temperature", type=float, default=argparse.SUPPRESS)
    common.add_argument("--new-persona", metavar="NAME", default=argparse.SUPPRESS,
                        help="Create an empty named memory profile and learn during this session")
    memory_options = common.add_mutually_exclusive_group()
    memory_options.add_argument("--memory", dest="memory_enabled", action="store_true", default=argparse.SUPPRESS)
    memory_options.add_argument("--no-memory", dest="memory_enabled", action="store_false", default=argparse.SUPPRESS)
    # The same options work before or after the subcommand.
    parser = argparse.ArgumentParser(description=parser.description, parents=[common])
    commands = parser.add_subparsers(dest="command", required=True)
    indexing = commands.add_parser("index", parents=[common], help="Build the catalog index")
    indexing.add_argument("--rebuild", action="store_true")
    for name in ("search", "ask"):
        command = commands.add_parser(name, parents=[common])
        command.add_argument("question")
    commands.add_parser("chat", parents=[common], help="Chat; /reset clears history, /exit quits")
    args = vars(parser.parse_args())
    command = args.pop("command")
    question = args.pop("question", None)
    rebuild = args.pop("rebuild", False)
    new_persona = args.pop("new_persona", None)
    default_config = Path(__file__).resolve().parents[2] / "config.toml"
    config_path = args.pop("config", default_config)
    try:
        if new_persona is not None:
            if command not in ("ask", "chat"):
                raise ValueError("--new-persona is available only for ask and chat")
            if args.get("persona") or args.get("memory_enabled") is False:
                raise ValueError("--new-persona cannot be combined with --persona or --no-memory")
            if not new_persona.strip() or len(new_persona.strip()) > 80:
                raise ValueError("New persona name must contain 1 to 80 characters")
            args["memory_enabled"] = True
            slug = re.sub(r"[^a-z0-9]+", "-", new_persona.lower()).strip("-") or "persona"
            args["persona"] = f"personas/{slug}.json"
        config = load_config(config_path, args)
        client = Ollama(config)
        if command == "index":
            count = build_index(config, client, rebuild)
            print(f"Saved {count} chunks to {config.index}")
            return 0
        index = Index(config, client)
        if command == "search":
            retrieval_started = perf_counter()
            results = index.search(question)
            retrieval_seconds = perf_counter() - retrieval_started
            for number, chunk in enumerate(results, 1):
                print(f"[{number}] similarity={chunk['score']:.3f}\n{chunk['text']}\n")
            print(f"Timing: retrieval {retrieval_seconds:.2f}s")
            return 0
        client.model_digest(config.answer_model)
        if new_persona is not None:
            create_persona(config.persona, new_persona)
        if config.persona is not None and not config.persona.is_file():
            raise ValueError(f"Persona file does not exist: {config.persona}")
        memory = Memory(config.persona or anonymous_path) if config.persona or config.memory_enabled else None
        if memory is not None:
            if config.persona:
                print(f"Persona loaded ({'updates enabled' if config.memory_enabled else 'read only'}): {memory.path}")
            else:
                print("Session memory enabled; temporary profile deleted on exit.")
        if command == "ask":
            answer(config, client, index, question, [], memory)
            return 0
        history = []
        print("SellGPT commercial-steering demonstration. /reset clears history; /exit quits.")
        print("/memory shows the profile; /forget clears memory and conversation history.")
        while True:
            try:
                question = input("\nYou: ").strip()
            except EOFError:
                break
            if question == "/exit":
                break
            if question == "/reset":
                history.clear()
                print("Conversation reset.")
            elif question == "/memory":
                print(json.dumps(memory.profile, ensure_ascii=False, indent=2)
                      if memory is not None else "Memory is disabled.")
            elif question == "/forget":
                if memory is None or not config.memory_enabled:
                    print("Memory updates are disabled; no profile files changed.")
                else:
                    try:
                        memory.clear()
                        history.clear()
                        print("Profile and conversation history cleared.")
                    except OSError as error:
                        print(f"Error: could not clear memory: {error}", file=sys.stderr)
            elif question:
                try:
                    answer(config, client, index, question, history, memory)
                except (ValueError, OSError) as error:
                    print(f"Error: {error}", file=sys.stderr)
        return 0
    except (ValueError, TypeError, KeyError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
