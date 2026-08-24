import asyncio
import uuid
from types import SimpleNamespace

from app.config import settings
from app.models import Chunk
from app.services import ingest


class _FakeResult:
    def __init__(self, rows: list[Chunk]) -> None:
        self._rows = rows

    def scalars(self) -> list[Chunk]:
        return self._rows


class _FakeSession:
    def __init__(self, rows: list[Chunk] | None = None) -> None:
        self.added: list[Chunk] = []
        self.rows = rows or []
        self.committed = False

    async def execute(self, *_args, **_kwargs):
        return _FakeResult(self.rows)

    def add(self, row: Chunk) -> None:
        self.added.append(row)

    async def commit(self) -> None:
        self.committed = True


class _SessionCM:
    def __init__(self, session: _FakeSession) -> None:
        self.session = session

    async def __aenter__(self) -> _FakeSession:
        return self.session

    async def __aexit__(self, *_args) -> bool:
        return False


def test_write_chunks_without_vectors() -> None:
    source = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id="default",
        notebook_id=uuid.uuid4(),
    )
    session = _FakeSession()
    text = "Abschnitt eins. " * 80
    asyncio.run(ingest.write_chunks(session, source, text, embed=False))
    assert session.added
    assert all(chunk.embedding is None for chunk in session.added)


def test_embed_source_isolated_fills_vectors(monkeypatch) -> None:
    source_id = uuid.uuid4()
    chunk = Chunk(
        tenant_id="default",
        notebook_id=uuid.uuid4(),
        source_id=source_id,
        ordinal=0,
        text="Hallo Welt",
        embedding=None,
    )
    session = _FakeSession([chunk])
    monkeypatch.setattr(ingest, "SessionLocal", lambda: _SessionCM(session))
    monkeypatch.setattr(
        ingest,
        "embed_texts",
        lambda texts: [[0.4] * settings.embedding_dim for _text in texts],
    )
    asyncio.run(ingest.embed_source_isolated(source_id))
    assert chunk.embedding is not None
    assert chunk.embedding[0] == 0.4
    assert session.committed


def test_unwrap_markdown_fence_removes_wrapping_block() -> None:
    raw = "```markdown\n# Quellenbericht\n\n**Titel:** Test\n```\n"
    assert ingest.unwrap_markdown_fence(raw) == "# Quellenbericht\n\n**Titel:** Test"


def test_unwrap_markdown_fence_keeps_plain_markdown() -> None:
    raw = "# Quellenbericht\n\n**Titel:** Test"
    assert ingest.unwrap_markdown_fence(raw) == raw
