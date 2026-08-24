from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.db import Base, SessionLocal, engine
from app.routers import auth, chat, compliance, eval as eval_router, notebooks, research, skills, sources
from app.services.ingest import rebuild_embeddings
from app.services.tenancy import seed_demo_user


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            text("ALTER TABLE eval_items ADD COLUMN IF NOT EXISTS task VARCHAR(32) DEFAULT 'chat'")
        )
        await conn.execute(text("ALTER TABLE sources ADD COLUMN IF NOT EXISTS favicon_url TEXT"))
        await conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS raw_output TEXT DEFAULT ''"))
        await conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS reasoning JSONB DEFAULT '[]'::jsonb"))
        await conn.execute(text("ALTER TABLE notebooks ADD COLUMN IF NOT EXISTS tts_provider VARCHAR(32) DEFAULT 'local'"))
        await conn.execute(text("ALTER TABLE notebooks ADD COLUMN IF NOT EXISTS tts_model VARCHAR(255) DEFAULT 'piper'"))
        await conn.execute(text("ALTER TABLE notebooks ALTER COLUMN tts_provider SET DEFAULT 'local'"))
        await conn.execute(text("ALTER TABLE notebooks ALTER COLUMN tts_model SET DEFAULT 'piper'"))
        await conn.execute(text("ALTER TABLE notebooks ADD COLUMN IF NOT EXISTS image_provider VARCHAR(32) DEFAULT 'local'"))
        await conn.execute(text("ALTER TABLE notebooks ADD COLUMN IF NOT EXISTS image_model VARCHAR(255) DEFAULT 'flux'"))
    async with SessionLocal() as session:
        await seed_demo_user(session)
        if settings.embedding_backend == "ollama":
            await rebuild_embeddings(session)
    yield
    await engine.dispose()


app = FastAPI(title="Everlast Notebook", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    session_cookie="session",
    same_site="lax",
    https_only=settings.session_https,
    max_age=60 * 60 * 24 * 14,
)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.api)
app.include_router(notebooks.api)
app.include_router(sources.api)
app.include_router(chat.api)
app.include_router(skills.api)
app.include_router(research.api)
app.include_router(compliance.api)
app.include_router(eval_router.api)


@app.exception_handler(ValueError)
async def value_error_handler(_: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=400)


@app.exception_handler(Exception)
async def any_error_handler(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=500)
