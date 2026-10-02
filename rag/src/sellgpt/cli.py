"""Command-line entry point."""

import argparse
import json
import re
from pathlib import Path
import sys
from time import perf_counter
from tempfile import TemporaryDirectory

from .assistant import answer, introduce
from .config import load_config
from .index import Index, build_index
from .ollama import Ollama
from .memory import Memory, create_user_profile


def greet(config, client, history, memory):
    """Print a model-generated greeting, reporting failures without ending chat.

    Parameters: Config, Ollama client, history list, optional Memory. Return: None.
    """
    print("\nSellGPT: ", end="", flush=True)
    try:
        for fragment in introduce(config, client, history, memory):
            print(fragment, end="", flush=True)
        print()
    except (ValueError, TypeError, KeyError, OSError) as error:
        print(f"\nCould not introduce SellGPT: {error}", file=sys.stderr)


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
                "user_profile"):
        common.add_argument("--" + key.replace("_", "-"), default=argparse.SUPPRESS)
    for key in ("top_k", "context_length", "output_limit", "chunk_words", "chunk_overlap",
                "embedding_batch_size", "history_turns", "timeout"):
        common.add_argument("--" + key.replace("_", "-"), type=int, default=argparse.SUPPRESS)
    common.add_argument("--temperature", type=float, default=argparse.SUPPRESS)
    common.add_argument("--new-user-profile", metavar="NAME", default=argparse.SUPPRESS,
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
    new_user_profile = args.pop("new_user_profile", None)
    default_config = Path(__file__).resolve().parents[2] / "config.toml"
    config_path = args.pop("config", default_config)
    try:
        if new_user_profile is not None:
            if command not in ("ask", "chat"):
                raise ValueError("--new-user-profile is available only for ask and chat")
            if args.get("user_profile") or args.get("memory_enabled") is False:
                raise ValueError("--new-user-profile cannot be combined with --user-profile or --no-memory")
            if not new_user_profile.strip() or len(new_user_profile.strip()) > 80:
                raise ValueError("New user profile name must contain 1 to 80 characters")
            args["memory_enabled"] = True
            slug = re.sub(r"[^a-z0-9]+", "-", new_user_profile.lower()).strip("-") or "user-profile"
            args["user_profile"] = f"user_profiles/{slug}.json"
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
        if new_user_profile is not None:
            create_user_profile(config.user_profile, new_user_profile)
        if config.user_profile is not None and not config.user_profile.is_file():
            raise ValueError(f"User profile file does not exist: {config.user_profile}")
        memory = Memory(config.user_profile or anonymous_path) if config.user_profile or config.memory_enabled else None
        if memory is not None:
            if config.user_profile:
                print(f"User profile loaded ({'updates enabled' if config.memory_enabled else 'read only'}): {memory.path}")
            else:
                print("Session memory enabled; temporary profile deleted on exit.")
        if command == "ask":
            answer(config, client, index, question, [], memory)
            return 0
        history = []
        print("SellGPT commercial-steering demonstration. /reset clears history; /exit quits.")
        print("/memory shows the profile; /forget clears memory and conversation history.")
        greet(config, client, history, memory)
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
                greet(config, client, history, memory)
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
                        greet(config, client, history, memory)
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
