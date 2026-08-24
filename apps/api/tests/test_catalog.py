from app.services.skills import REGISTRY, STUDIO_CATALOG

LOCKED = {"studio.audio", "studio.slides", "studio.video", "studio.infographic"}
AVAILABLE = {
    "notes.create",
    "studio.mindmap",
    "studio.report",
    "studio.quiz",
    "studio.flashcards",
    "studio.table",
}


def test_flashcards_and_table_are_available() -> None:
    cards = {card.id: card.status for card in STUDIO_CATALOG}
    assert cards["studio.flashcards"] == "available"
    assert cards["studio.table"] == "available"
    assert "studio.flashcards" in REGISTRY
    assert "studio.table" in REGISTRY


def test_media_skills_stay_locked() -> None:
    cards = {card.id: card.status for card in STUDIO_CATALOG}
    for skill_id in LOCKED:
        assert cards[skill_id] == "locked"
        assert skill_id not in REGISTRY


def test_available_studio_skills_have_handlers() -> None:
    cards = {card.id: card.status for card in STUDIO_CATALOG}
    for skill_id in AVAILABLE:
        assert cards[skill_id] == "available"
        assert REGISTRY[skill_id].handler is not None
