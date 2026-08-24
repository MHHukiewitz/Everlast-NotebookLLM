from app.services.skills import REGISTRY, STUDIO_CATALOG

AVAILABLE = {
    "notes.create",
    "studio.audio",
    "studio.video",
    "studio.mindmap",
    "studio.report",
    "studio.quiz",
    "studio.flashcards",
    "studio.table",
    "studio.slides",
    "studio.infographic",
}


def test_slides_and_infographic_are_available() -> None:
    cards = {card.id: card.status for card in STUDIO_CATALOG}
    assert cards["studio.slides"] == "available"
    assert cards["studio.infographic"] == "available"
    assert "studio.slides" in REGISTRY
    assert "studio.infographic" in REGISTRY


def test_audio_and_video_are_available() -> None:
    cards = {card.id: card.status for card in STUDIO_CATALOG}
    assert cards["studio.audio"] == "available"
    assert cards["studio.video"] == "available"
    assert "studio.audio" in REGISTRY
    assert "studio.video" in REGISTRY


def test_available_studio_skills_have_handlers() -> None:
    cards = {card.id: card.status for card in STUDIO_CATALOG}
    for skill_id in AVAILABLE:
        assert cards[skill_id] == "available"
        assert REGISTRY[skill_id].handler is not None
