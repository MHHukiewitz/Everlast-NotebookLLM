from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import current_user
from app.models import User
from app.schemas import LoginIn, RegisterIn, UserOut
from app.services.auth import email_allowed_to_register, normalize_email
from app.services.passwords import hash_password, verify_password
from app.services.tenancy import erase_tenant, ensure_notebook, user_is_demo

api = APIRouter(prefix="/api/auth")


def _user_out(user: User) -> UserOut:
    return UserOut(id=user.id, email=user.email, is_demo=user_is_demo(user))


@api.post("/register", response_model=UserOut)
async def register(body: RegisterIn, request: Request, session: AsyncSession = Depends(get_session)) -> UserOut:
    if not body.privacy_ack:
        raise HTTPException(status_code=400, detail="Bitte die Datenschutzerklärung bestätigen.")
    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="Das Passwort muss mindestens 8 Zeichen haben.")
    email = normalize_email(body.email)
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        raise HTTPException(status_code=400, detail="Bitte eine gültige E-Mail angeben.")
    if not email_allowed_to_register(email):
        raise HTTPException(status_code=403, detail="Diese E-Mail ist nicht zur Registrierung freigegeben.")
    existing = await session.scalar(select(User.id).where(User.email == email))
    if existing is not None:
        raise HTTPException(status_code=409, detail="Diese E-Mail ist bereits registriert.")
    user = User(email=email, password_hash=hash_password(body.password))
    session.add(user)
    await session.flush()
    await ensure_notebook(session, str(user.id))
    await session.commit()
    await session.refresh(user)
    request.session["user_id"] = str(user.id)
    return _user_out(user)


@api.post("/login", response_model=UserOut)
async def login(body: LoginIn, request: Request, session: AsyncSession = Depends(get_session)) -> UserOut:
    email = normalize_email(body.email)
    user = await session.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="E-Mail oder Passwort ist falsch.")
    await ensure_notebook(session, str(user.id))
    await session.commit()
    request.session["user_id"] = str(user.id)
    return _user_out(user)


@api.post("/logout")
async def logout(request: Request) -> dict[str, str]:
    request.session.clear()
    return {"status": "ok"}


@api.get("/me", response_model=UserOut)
async def me(user: User = Depends(current_user)) -> UserOut:
    return _user_out(user)


@api.delete("/me")
async def delete_me(
    request: Request, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
) -> dict[str, str]:
    if user_is_demo(user):
        raise HTTPException(status_code=403, detail="Das Demo-Konto kann nicht gelöscht werden.")
    tenant_id = str(user.id)
    await erase_tenant(session, tenant_id)
    await session.delete(user)
    await session.commit()
    request.session.clear()
    return {"status": "deleted"}
