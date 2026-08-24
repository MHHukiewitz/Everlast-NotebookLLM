import argparse
import asyncio
import json

from app.config import settings
from app.db import SessionLocal
from app.services.eval_harness import run_eval


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run Everlast Notebook chat and source eval")
    parser.add_argument("--provider", default="ollama")
    parser.add_argument("--model", default="qwen2.5:7b")
    args = parser.parse_args()
    async with SessionLocal() as session:
        run = await run_eval(session, args.provider, args.model, settings.default_tenant_id)
        print(json.dumps({"id": str(run.id), "metrics": run.metrics}, indent=2))


asyncio.run(main())
