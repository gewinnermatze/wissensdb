import hashlib
import math
import os
from typing import Protocol

import httpx

from wissensdb.config import Settings


class EmbeddingProvider(Protocol):
    dimension: int

    def embed(self, text: str) -> list[float]: ...


class HashEmbeddingProvider:
    """Deterministic local fallback for development and tests."""

    def __init__(self, dimension: int = 384) -> None:
        self.dimension = dimension

    def embed(self, text: str) -> list[float]:
        buckets = [0.0] * self.dimension
        words = text.lower().split()
        if not words:
            return buckets
        for word in words:
            digest = hashlib.sha256(word.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            buckets[idx] += sign
        norm = math.sqrt(sum(value * value for value in buckets)) or 1.0
        return [value / norm for value in buckets]


class OpenAIEmbeddingProvider:
    def __init__(self, model: str, dimension: int) -> None:
        self.model = model
        self.dimension = dimension
        self.api_key = os.environ.get("OPENAI_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required for openai embeddings")

    def embed(self, text: str) -> list[float]:
        response = httpx.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "input": text},
            timeout=30,
        )
        response.raise_for_status()
        vector = response.json()["data"][0]["embedding"]
        self.dimension = len(vector)
        return vector


def build_embedding_provider(settings: Settings) -> EmbeddingProvider:
    if settings.embedding_provider == "hash":
        return HashEmbeddingProvider(settings.embedding_dimension)
    if settings.embedding_provider == "openai":
        return OpenAIEmbeddingProvider(
            settings.openai_embedding_model, settings.embedding_dimension
        )
    raise ValueError(f"unsupported embedding provider: {settings.embedding_provider}")
