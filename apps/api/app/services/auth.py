from app.config import settings


def normalize_email(email: str) -> str:
    return email.strip().lower()


def is_demo_email(email: str) -> bool:
    demo = normalize_email(settings.demo_email)
    return bool(demo) and normalize_email(email) == demo


def register_allowlist() -> set[str]:
    return {normalize_email(item) for item in settings.register_allowlist.split(",") if item.strip()}


def email_allowed_to_register(email: str) -> bool:
    allowed = register_allowlist()
    return normalize_email(email) in allowed
