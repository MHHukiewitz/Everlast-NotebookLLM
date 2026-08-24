import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.models import EvalItem, EvalRun
from app.schemas import EvalItemOut, EvalRunOut, EvalStartIn, HumanScoreIn
from app.services.eval_harness import run_eval

api = APIRouter(prefix="/api/eval")


def _run_out(run: EvalRun, items: list[EvalItem]) -> EvalRunOut:
    return EvalRunOut.model_validate(run).model_copy(update={"items": items})


@api.get("/gold")
async def gold() -> list[dict]:
    from app.services.eval_harness import load_gold

    return load_gold()


@api.get("/runs", response_model=list[EvalRunOut])
async def list_runs(session: AsyncSession = Depends(get_session)) -> list[EvalRunOut]:
    runs = list(
        (
            await session.execute(
                select(EvalRun)
                .where(EvalRun.tenant_id == settings.default_tenant_id)
                .order_by(EvalRun.created_at.desc())
            )
        ).scalars()
    )
    out: list[EvalRunOut] = []
    for run in runs:
        items = list((await session.execute(select(EvalItem).where(EvalItem.run_id == run.id))).scalars())
        out.append(_run_out(run, items))
    return out


@api.get("/runs/{run_id}", response_model=EvalRunOut)
async def get_run(run_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> EvalRunOut:
    run = await session.get(EvalRun, run_id)
    if run is None:
        raise HTTPException(404, "Eval-Lauf nicht gefunden")
    items = list((await session.execute(select(EvalItem).where(EvalItem.run_id == run.id))).scalars())
    return _run_out(run, items)


@api.post("/runs", response_model=EvalRunOut)
async def start_run(body: EvalStartIn, session: AsyncSession = Depends(get_session)) -> EvalRunOut:
    run = await run_eval(session, body.provider, body.model_id)
    items = list((await session.execute(select(EvalItem).where(EvalItem.run_id == run.id))).scalars())
    return _run_out(run, items)


@api.patch("/items/{item_id}", response_model=EvalItemOut)
async def score_item(
    item_id: uuid.UUID, body: HumanScoreIn, session: AsyncSession = Depends(get_session)
) -> EvalItem:
    item = await session.get(EvalItem, item_id)
    if item is None:
        raise HTTPException(404, "Eval-Fall nicht gefunden")
    item.human_faithfulness = body.human_faithfulness
    item.human_usefulness = body.human_usefulness
    item.human_citation = body.human_citation
    item.human_pass = body.human_pass
    item.human_comment = body.human_comment
    item.reviewer = body.reviewer
    item.reviewed_at = datetime.now(timezone.utc)
    await session.commit()
    run = await session.get(EvalRun, item.run_id)
    if run:
        items = list((await session.execute(select(EvalItem).where(EvalItem.run_id == run.id))).scalars())
        reviewed = sum(1 for row in items if row.reviewed_at is not None)
        metrics = dict(run.metrics or {})
        metrics["human_reviewed"] = reviewed
        scored = [row for row in items if row.human_faithfulness is not None]
        if scored:
            metrics["avg_human_faithfulness"] = round(
                sum(row.human_faithfulness or 0 for row in scored) / len(scored), 2
            )
            metrics["human_pass_rate"] = round(
                sum(1 for row in items if row.human_pass) / len(items), 3
            )
        run.metrics = metrics
        await session.commit()
    await session.refresh(item)
    return item


@api.get("/compare")
async def compare(a: uuid.UUID, b: uuid.UUID, session: AsyncSession = Depends(get_session)) -> dict:
    left = await session.get(EvalRun, a)
    right = await session.get(EvalRun, b)
    if left is None or right is None:
        raise HTTPException(404, "Eval-Lauf nicht gefunden")
    left_items = {
        row.case_id: row
        for row in (await session.execute(select(EvalItem).where(EvalItem.run_id == a))).scalars()
    }
    right_items = {
        row.case_id: row
        for row in (await session.execute(select(EvalItem).where(EvalItem.run_id == b))).scalars()
    }
    cases = sorted(set(left_items) | set(right_items))
    rows = []
    for case_id in cases:
        l_item = left_items.get(case_id)
        r_item = right_items.get(case_id)
        rows.append(
            {
                "case_id": case_id,
                "question": (l_item or r_item).question if (l_item or r_item) else case_id,
                "a": EvalItemOut.model_validate(l_item) if l_item else None,
                "b": EvalItemOut.model_validate(r_item) if r_item else None,
            }
        )
    return {
        "a": _run_out(left, list(left_items.values())),
        "b": _run_out(right, list(right_items.values())),
        "rows": rows,
    }
