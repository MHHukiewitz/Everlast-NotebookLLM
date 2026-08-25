import asyncio
import uuid

from app.services import ingest
from app.services.load import heavy_job, system_is_busy


def test_heavy_job_marks_busy() -> None:
    assert system_is_busy() is False

    async def run() -> None:
        async with heavy_job():
            assert system_is_busy() is True

    asyncio.run(run())
    assert system_is_busy() is False


def test_idle_summary_skips_when_busy(monkeypatch) -> None:
    monkeypatch.setattr(ingest, "system_is_busy", lambda: True)

    async def fail_claim() -> None:
        raise AssertionError("must not claim while busy")

    monkeypatch.setattr(ingest, "claim_pending_summary", fail_claim)
    assert asyncio.run(ingest.next_idle_summary()) is None


def test_idle_summary_claims_when_idle(monkeypatch) -> None:
    source_id = uuid.uuid4()
    monkeypatch.setattr(ingest, "system_is_busy", lambda: False)

    async def fake_claim() -> uuid.UUID:
        return source_id

    monkeypatch.setattr(ingest, "claim_pending_summary", fake_claim)
    assert asyncio.run(ingest.next_idle_summary()) == source_id


def test_claim_source_summary_only_takes_pending() -> None:
    class Session:
        def __init__(self, status: str, content: str) -> None:
            self.source = type("Source", (), {"summary_status": status, "content_md": content})()
            self.committed = False

        async def get(self, *_args, **_kwargs):
            return self.source

        async def commit(self) -> None:
            self.committed = True

    pending = Session("pending", "text")
    assert asyncio.run(ingest.claim_source_summary(pending, uuid.uuid4())) is True
    assert pending.source.summary_status == "running"
    assert pending.committed is True

    ready = Session("ready", "text")
    assert asyncio.run(ingest.claim_source_summary(ready, uuid.uuid4())) is False
    assert ready.committed is False


def test_import_still_avoids_inline_summary() -> None:
    import inspect

    from app.services import research

    src = inspect.getsource(research.import_research)
    assert "refresh_model_summary" not in src
    assert "create_task" not in inspect.getsource(research)
