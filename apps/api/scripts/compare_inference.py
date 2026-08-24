"""Compare local Ollama and Hetzner Inference on one short German prompt."""

import asyncio
import time

from app.config import settings
from app.services.connectors import router

PROMPT = (
    "Antworte auf Deutsch in genau zwei Sätzen. "
    "Erkläre Hybrid-Search. Nenne BM25 und Vektoren."
)
MESSAGES = [
    {"role": "system", "content": "Du bist Everlast Notebook. Antworte kurz und klar auf Deutsch."},
    {"role": "user", "content": PROMPT},
]


async def timed_complete(provider: str, model_id: str) -> dict[str, object]:
    started = time.perf_counter()
    first = 0.0
    text = ""
    async for chunk in router.stream_chat(provider, model_id, MESSAGES):
        delta = chunk.choices[0].delta
        if delta is None:
            continue
        piece = getattr(delta, "content", None) or ""
        think = getattr(delta, "reasoning_content", None) or getattr(delta, "thinking", None) or ""
        if (piece or think) and not first:
            first = time.perf_counter() - started
        if piece:
            text += str(piece)
    total = time.perf_counter() - started
    compact = " ".join(text.split())
    return {
        "provider": provider,
        "model": model_id,
        "first_token_s": round(first, 2) if first else None,
        "total_s": round(total, 2),
        "chars": len(compact),
        "has_bm25": "bm25" in compact.lower(),
        "has_vektor": "vektor" in compact.lower(),
        "german": any(word in compact.lower() for word in ("suche", "kombiniert", "verbindet", "nutzt")),
        "text": compact[:280],
    }


async def main() -> None:
    jobs = [("ollama", settings.default_model)]
    if settings.hetzner_api_key:
        for model_id in [item.strip() for item in settings.hetzner_models.split(",") if item.strip()]:
            jobs.append(("hetzner", model_id))
    rows = []
    for provider, model_id in jobs:
        print(f"RUN {provider}/{model_id}", flush=True)
        rows.append(await timed_complete(provider, model_id))
    for row in rows:
        print(
            f"{row['provider']}/{row['model']}: first={row['first_token_s']}s "
            f"total={row['total_s']}s chars={row['chars']} "
            f"bm25={row['has_bm25']} vektor={row['has_vektor']} de={row['german']}"
        )
        print(f"  {row['text']}")


if __name__ == "__main__":
    asyncio.run(main())
