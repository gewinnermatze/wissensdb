import httpx

from wissensdb.config import Settings
from wissensdb.embeddings import OllamaEmbeddingProvider, build_embedding_provider


def test_builds_ollama_embedding_provider_from_settings():
    provider = build_embedding_provider(
        Settings(
            embedding_provider="ollama",
            ollama_url="http://ollama.local:11434",
            ollama_embedding_model="nomic-embed-text",
            embedding_dimension=768,
        )
    )

    assert isinstance(provider, OllamaEmbeddingProvider)
    assert provider.base_url == "http://ollama.local:11434"
    assert provider.model == "nomic-embed-text"
    assert provider.dimension == 768


def test_ollama_embedding_provider_calls_embeddings_endpoint(monkeypatch):
    requests = []

    def fake_post(url, json, timeout):
        requests.append({"url": url, "json": json, "timeout": timeout})
        return httpx.Response(
            200,
            json={"embedding": [0.1, 0.2, 0.3]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    provider = OllamaEmbeddingProvider(
        "http://ollama.local:11434/",
        "nomic-embed-text",
        768,
    )

    assert provider.embed("hello") == [0.1, 0.2, 0.3]
    assert provider.dimension == 3
    assert requests == [
        {
            "url": "http://ollama.local:11434/api/embeddings",
            "json": {"model": "nomic-embed-text", "prompt": "hello"},
            "timeout": 60,
        }
    ]
