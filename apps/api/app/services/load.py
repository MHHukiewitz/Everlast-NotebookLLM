from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

_heavy = 0


def system_is_busy() -> bool:
    return _heavy > 0


@asynccontextmanager
async def heavy_job() -> AsyncIterator[None]:
    global _heavy
    _heavy += 1
    try:
        yield
    finally:
        _heavy -= 1
