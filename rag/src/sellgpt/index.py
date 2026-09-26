"""Persist embeddings and retrieve catalog chunks."""

from collections import Counter
import json
import os
import tempfile
import numpy as np

from .catalog import fingerprints, load_chunks


def normalize(vectors):
    """Normalize vectors. Parameter: numeric matrix. Return: unit-length float32 matrix."""
    matrix = np.asarray(vectors, dtype=np.float32)
    if matrix.ndim != 2 or not matrix.size or not np.isfinite(matrix).all():
        raise ValueError("Embedding response must be a finite, nonempty matrix")
    lengths = np.linalg.norm(matrix, axis=1, keepdims=True)
    if (lengths == 0).any():
        raise ValueError("Embedding response contains a zero-length vector")
    return matrix / lengths


def signature(config, client):
    """Describe index compatibility. Parameters: Config, Ollama. Return: dictionary."""
    return {"version": 1, "embedding_model": config.embedding_model,
            "digest": client.model_digest(config.embedding_model),
            "chunk_words": config.chunk_words, "chunk_overlap": config.chunk_overlap,
            "sources": fingerprints(config.catalog)}


def build_index(config, client, rebuild=False):
    """Build atomically. Parameters: Config, Ollama, rebuild flag. Return: chunk count."""
    if config.index.exists() and not rebuild:
        raise ValueError("An index already exists. Use 'sellgpt index --rebuild' to replace it.")
    metadata = signature(config, client)
    chunks = load_chunks(config)
    batches = []
    for start in range(0, len(chunks), config.embedding_batch_size):
        batch = chunks[start:start + config.embedding_batch_size]
        vectors = normalize(client.embed([chunk["text"] for chunk in batch]))
        if len(vectors) != len(batch):
            raise ValueError("Ollama returned the wrong number of embeddings")
        batches.append(vectors)
        print(f"Embedded {start + len(batch)}/{len(chunks)} chunks", flush=True)
    matrix = np.concatenate(batches)
    metadata["dimensions"] = matrix.shape[1]
    if metadata["sources"] != fingerprints(config.catalog):
        raise ValueError("Catalog changed during indexing; rebuild with unchanged source files")
    config.index.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=config.index.parent, suffix=".npz", delete=False) as file:
            temporary = file.name
            np.savez_compressed(file, vectors=matrix, metadata=json.dumps(metadata),
                                chunks=json.dumps(chunks, ensure_ascii=False))
        os.replace(temporary, config.index)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
    return len(chunks)


class Index:
    """An in-memory catalog index validated against the current configuration."""

    def __init__(self, config, client):
        """Load an index. Parameters: Config, Ollama. Return: None."""
        self.config, self.client = config, client
        if not config.index.is_file():
            raise ValueError("No index found. Run 'sellgpt index' first.")
        try:
            with np.load(config.index, allow_pickle=False) as stored:
                self.vectors = normalize(stored["vectors"])
                self.chunks = json.loads(str(stored["chunks"]))
                metadata = json.loads(str(stored["metadata"]))
            dimensions = metadata.pop("dimensions")
            if dimensions != self.vectors.shape[1] or len(self.chunks) != len(self.vectors):
                raise ValueError("Invalid index dimensions or chunk count")
        except (ValueError, KeyError, OSError) as error:
            raise ValueError("Cannot read the index. Run 'sellgpt index --rebuild'.") from error
        if metadata != signature(config, client):
            raise ValueError("Index settings, embedding model, or catalogs changed. "
                             "Run 'sellgpt index --rebuild'.")

    def search(self, question):
        """Retrieve chunks. Parameter: question string. Return: scored chunk dictionaries."""
        if not question.strip():
            raise ValueError("Question cannot be empty")
        vector = normalize(self.client.embed([question], query=True))
        if vector.shape != (1, self.vectors.shape[1]):
            raise ValueError("Embedding dimensions changed. Rebuild the index.")
        scores = self.vectors @ vector[0]
        results, counts = [], Counter()
        for position in np.argsort(-scores):
            chunk = self.chunks[int(position)]
            if counts[chunk["url"]] >= 2:
                continue
            counts[chunk["url"]] += 1
            results.append({**chunk, "score": float(scores[position])})
            if len(results) == self.config.top_k:
                break
        return results
