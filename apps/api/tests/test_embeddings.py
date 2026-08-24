from types import SimpleNamespace

from app.config import settings
from app.services import embeddings


def test_embed_texts_batches_ollama(monkeypatch) -> None:
    calls: list[dict] = []

    def fake_embedding(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            data=[
                {"embedding": [0.1] * settings.embedding_dim, "index": 0},
                {"embedding": [0.2] * settings.embedding_dim, "index": 1},
            ]
        )

    monkeypatch.setattr(embeddings, "litellm_embedding", fake_embedding)
    monkeypatch.setattr(embeddings, "host_open", lambda _url: True)
    monkeypatch.setattr(embeddings.settings, "embedding_backend", "ollama")
    vectors = embeddings.embed_texts(["eins", "zwei"])
    assert len(calls) == 1
    assert calls[0]["input"] == ["eins", "zwei"]
    assert len(vectors) == 2
    assert vectors[0][0] == 0.1
    assert vectors[1][0] == 0.2


def test_embed_text_uses_one_item_batch(monkeypatch) -> None:
    calls: list[dict] = []

    def fake_embedding(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(data=[{"embedding": [0.3] * settings.embedding_dim, "index": 0}])

    monkeypatch.setattr(embeddings, "litellm_embedding", fake_embedding)
    monkeypatch.setattr(embeddings, "host_open", lambda _url: True)
    monkeypatch.setattr(embeddings.settings, "embedding_backend", "ollama")
    vector = embeddings.embed_text("allein")
    assert len(calls) == 1
    assert calls[0]["input"] == ["allein"]
    assert vector[0] == 0.3
