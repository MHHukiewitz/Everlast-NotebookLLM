import hashlib
import re

import numpy as np
from litellm import embedding as litellm_embedding

from app.config import settings
from app.services.net import host_open

_TOKEN = re.compile(r"[a-zA-ZäöüÄÖÜß0-9]{2,}")


def _hash_embed(text: str) -> list[float]:
    dim = settings.embedding_dim
    vec = np.zeros(dim, dtype=np.float32)
    tokens = _TOKEN.findall(text.lower())
    if not tokens:
        return vec.tolist()
    for index, token in enumerate(tokens):
        digest = hashlib.sha256(f"{token}:{index // 8}".encode()).digest()
        slot = int.from_bytes(digest[:4], "little") % dim
        vec[slot] += 1.0
        if index + 1 < len(tokens):
            bigram = f"{token}_{tokens[index + 1]}"
            digest_b = hashlib.sha256(bigram.encode()).digest()
            slot_b = int.from_bytes(digest_b[:4], "little") % dim
            vec[slot_b] += 0.6
    norm = float(np.linalg.norm(vec))
    if norm == 0:
        return vec.tolist()
    return (vec / norm).tolist()


def _embedding_vector(item: object) -> list[float]:
    raw = item["embedding"] if isinstance(item, dict) else item.embedding
    vector = list(raw)
    if len(vector) != settings.embedding_dim:
        raise ValueError(
            f"Embedding-Dimension {len(vector)} passt nicht zu EMBEDDING_DIM={settings.embedding_dim}."
        )
    return vector


def _embedding_index(item: object, fallback: int) -> int:
    if isinstance(item, dict):
        return int(item.get("index", fallback))
    return int(getattr(item, "index", fallback))


def _ollama_embed_many(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    if not host_open(settings.ollama_api_base):
        raise ValueError("Ollama ist nicht erreichbar. Embeddings brauchen ein lokales Modell.")
    result = litellm_embedding(
        model=f"ollama/{settings.embedding_model}",
        input=texts,
        api_base=settings.ollama_api_base,
    )
    items = sorted(enumerate(result.data), key=lambda pair: _embedding_index(pair[1], pair[0]))
    return [_embedding_vector(item) for _index, item in items]


def embed_text(text: str) -> list[float]:
    return embed_texts([text])[0]


def embed_texts(texts: list[str]) -> list[list[float]]:
    if settings.embedding_backend == "ollama":
        return _ollama_embed_many(texts)
    return [_hash_embed(text) for text in texts]
