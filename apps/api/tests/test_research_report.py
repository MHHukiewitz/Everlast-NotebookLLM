import asyncio
import uuid
from types import SimpleNamespace

from app.models import Citation
from app.services import research


class _FakeResult:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    def scalars(self) -> list:
        return self._rows


class _FakeSession:
    def __init__(self, cites: list, notebook) -> None:
        self.cites = cites
        self.notebook = notebook
        self.added = []
        self.committed = False

    async def execute(self, *_args, **_kwargs):
        return _FakeResult(self.cites)

    async def get(self, _model, _id):
        return self.notebook

    def add(self, row) -> None:
        self.added.append(row)

    async def commit(self) -> None:
        self.committed = True


def test_fallback_report_lists_hits() -> None:
    text = research.fallback_report(
        "fast",
        [{"title": "Firma", "url": "https://x.example", "quote": "Seit 2010"}],
    )
    assert "Schnelle Recherche" in text
    assert "https://x.example" in text


def test_write_research_report_uses_model(monkeypatch) -> None:
    job = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id="default",
        notebook_id=uuid.uuid4(),
        query="Everlast Consulting GmbH",
        mode="fast",
        report_md="",
    )
    notebook = SimpleNamespace(id=job.notebook_id, provider="ollama", model_id="qwen2.5:7b")
    cite = SimpleNamespace(
        url="https://x.example",
        title="Everlast",
        quote="Die Firma sitzt in Deutschland.",
    )
    session = _FakeSession([cite], notebook)

    async def fake_complete(_provider, _model, _messages):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content="Everlast sitzt in Deutschland.\n\nDieser Bericht ist KI-generiert."
                    )
                )
            ]
        )

    async def fake_record(*_args, **_kwargs):
        return None

    monkeypatch.setattr(research, "host_open", lambda _url: True)
    monkeypatch.setattr(research.router, "complete", fake_complete)
    monkeypatch.setattr(research, "record_generation", fake_record)
    asyncio.run(research.write_research_report(session, job))
    assert "Everlast sitzt in Deutschland" in job.report_md
    assert job.report_md.strip()
    assert session.committed


def test_fast_research_ready_before_report(monkeypatch) -> None:
    job = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id="default",
        notebook_id=uuid.uuid4(),
        query="Everlast Consulting GmbH",
        mode="fast",
        status="queued",
        progress="",
        report_md="old",
    )
    session = _FakeSession([], None)
    queued: list[uuid.UUID] = []
    monkeypatch.setattr(research, "searx_reachable", lambda: True)
    monkeypatch.setattr(
        research,
        "searx_search",
        lambda _query, count=8: [
            {"url": "https://x.example", "title": "Everlast", "quote": "Beratung"},
        ],
    )
    monkeypatch.setattr(research, "queue_research_report", queued.append)
    asyncio.run(research.run_fast_research(session, job))
    assert job.status == "ready"
    assert job.report_md == ""
    assert queued == [job.id]
    assert any(isinstance(row, Citation) for row in session.added)
