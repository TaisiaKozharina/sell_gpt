"""Small standard-library client for the local Ollama API."""

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .memory import FACT_FIELDS, MAX_ITEMS, MAX_ITEM_LENGTH


class Ollama:
    """Send embedding and chat requests to an Ollama server."""

    def __init__(self, config):
        """Initialize a client. Parameter: Config. Return: None."""
        self.config = config

    def request(self, endpoint, payload=None):
        """Open an API response. Parameters: endpoint, optional payload. Return: response."""
        data = None if payload is None else json.dumps(payload).encode()
        request = Request(self.config.ollama_url.rstrip("/") + endpoint, data=data,
                          headers={"Content-Type": "application/json"})
        try:
            return urlopen(request, timeout=self.config.timeout)
        except HTTPError as error:
            detail = error.read().decode(errors="replace")
            raise ValueError(f"Ollama HTTP {error.code}: {detail}") from error
        except (URLError, TimeoutError) as error:
            raise ValueError(f"Cannot reach Ollama at {self.config.ollama_url}. "
                             "Start Ollama with 'ollama serve'; check the URL and timeout.") from error

    def model_digest(self, name):
        """Check a model is installed. Parameter: model name. Return: model digest."""
        with self.request("/api/tags") as response:
            models = json.load(response).get("models", [])
        qualified = name if ":" in name else name + ":latest"
        for model in models:
            if model.get("name") in (name, qualified) or model.get("model") in (name, qualified):
                return model["digest"]
        raise ValueError(f"Model {name!r} is not installed. Run: ollama pull {name}")

    def embed(self, texts, query=False):
        """Embed texts. Parameters: text list, query flag. Return: vector list."""
        if self.config.embedding_model.split(":")[0] == "embeddinggemma":
            prefix = "task: search result | query: " if query else "title: none | text: "
            texts = [prefix + text for text in texts]
        with self.request("/api/embed", {"model": self.config.embedding_model,
                          "input": texts, "truncate": False, "keep_alive": 0}) as response:
            result = json.load(response)
        if "error" in result:
            raise ValueError(f"Ollama embedding error: {result['error']}")
        return result["embeddings"]

    def chat(self, messages):
        """Stream an answer. Parameter: message list. Return: iterator of text fragments."""
        payload = {"model": self.config.answer_model, "messages": messages,
                   "stream": True, "think": False, "keep_alive": 0,
                   "options": {"temperature": self.config.temperature,
                               "num_ctx": self.config.context_length,
                               "num_predict": self.config.output_limit}}
        with self.request("/api/chat", payload) as response:
            for line in response:
                if not line.strip():
                    continue
                item = json.loads(line)
                if "error" in item:
                    raise ValueError(f"Ollama chat error: {item['error']}")
                yield item.get("message", {}).get("content", "")

    def extract_memory(self, profile, question):
        """Update stated user facts. Parameters: profile dictionary, user question.

        Return: dictionary of goals, preferences, constraints, facts, and product_interests.
        """
        instructions = self.config.memory_prompt.read_text(encoding="utf-8").strip()
        if not instructions:
            raise ValueError(f"Memory prompt is empty: {self.config.memory_prompt}")
        instructions += ("\n\nReturn a JSON object with exactly these fields: "
                         + ", ".join(FACT_FIELDS) + ". Each field is a list of nonempty strings, "
                         f"at most {MAX_ITEMS} items, {MAX_ITEM_LENGTH} characters per item. "
                         "Return only JSON, without additional text.")
        payload = {"model": self.config.answer_model, "stream": False, "think": False,
                   "format": "json", "keep_alive": 0,
                   "messages": [{"role": "system", "content": instructions},
                                {"role": "user", "content": json.dumps(
                                    {"previous": profile, "new_user_message": question})}],
                   "options": {"temperature": 0, "num_ctx": self.config.context_length,
                               "num_predict": 768}}
        with self.request("/api/chat", payload) as response:
            result = json.load(response)
        if "error" in result:
            raise ValueError(f"Ollama memory error: {result['error']}")
        return json.loads(result["message"]["content"])
