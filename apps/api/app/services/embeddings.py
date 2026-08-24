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


def _ollama_embed(text: str) -> list[float]:
    if not host_open(settings.ollama_api_base):
        raise ValueError("Ollama ist nicht erreichbar. Embeddings brauchen ein lokales Modell.")
    result = litellm_embedding(
        model=f"ollama/{settings.embedding_model}",
        input=[text],
        api_base=settings.ollama_api_base,
    )
    vector = list(result.data[0]["embedding"])
    if len(vector) != settings.embedding_dim:
        raise ValueError(
            f"Embedding-Dimension {len(vector)} passt nicht zu EMBEDDING_DIM={settings.embedding_dim}."
        )
    return vector


def embed_text(text: str) -> list[float]:
    if settings.embedding_backend == "ollama":
        return _ollama_embed(text)
    return _hash_embed(text)


def embed_texts(texts: list[str]) -> list[list[float]]:
    return [embed_text(text) for text in texts]
