"""Read configuration and resolve paths."""

from dataclasses import dataclass
from pathlib import Path
import tomllib


@dataclass
class Config:
    """Runtime settings. Paths are resolved relative to the configuration file."""

    catalog: Path
    index: Path
    prompt: Path
    memory_prompt: Path
    ollama_url: str = "http://127.0.0.1:11434"
    embedding_model: str = "embeddinggemma:300m"
    answer_model: str = "qwen3.5:2b"
    top_k: int = 5
    temperature: float = 0.7
    context_length: int = 4096
    output_limit: int = 512
    chunk_words: int = 250
    chunk_overlap: int = 40
    embedding_batch_size: int = 8
    history_turns: int = 4
    timeout: int = 180
    memory_enabled: bool = False
    persona: Path | None = None


def load_config(path, overrides):
    """Load TOML settings. Parameters: path, CLI overrides. Return: Config."""
    path = Path(path).expanduser().resolve()
    with path.open("rb") as source:
        settings = tomllib.load(source)
    settings.update({key: value for key, value in overrides.items() if value is not None})
    for key, default in (("catalog", "../site_catalog/site_catalog"),
                         ("index", ".data/index.npz"), ("prompt", "prompts/sellgpt.md"),
                         ("memory_prompt", "prompts/memory.md")):
        settings[key] = (path.parent / Path(settings.get(key, default)).expanduser()).resolve()
    if "memory_file" in settings:
        raise ValueError("memory_file is no longer supported. Select a persona for persistent memory; "
                         "memory without a persona lasts only for the session.")
    value = settings.get("persona")
    settings["persona"] = (path.parent / Path(value).expanduser()).resolve() if value else None
    config = Config(**settings)
    if type(config.memory_enabled) is not bool:
        raise ValueError("memory_enabled must be true or false")
    for key in ("top_k", "context_length", "output_limit", "chunk_words",
                "embedding_batch_size", "history_turns", "timeout"):
        value = getattr(config, key)
        if type(value) is not int or value <= 0:
            raise ValueError(f"{key} must be a positive integer")
    if not 0 <= config.chunk_overlap < config.chunk_words:
        raise ValueError("chunk_overlap must be between zero and chunk_words - 1")
    if config.context_length <= config.output_limit + 256:
        raise ValueError("context_length must exceed output_limit by more than 256")
    if not 0 <= config.temperature <= 2:
        raise ValueError("temperature must be between 0 and 2")
    return config
