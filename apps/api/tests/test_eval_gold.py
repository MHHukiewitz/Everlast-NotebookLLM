from app.services.chat_agent import NO_ANSWER, SYSTEM
from app.services.eval_harness import flatten_studio_payload, load_gold, looks_like_refuse, score_studio_output


def test_looks_like_refuse_ceo_salary_wording() -> None:
    answer = (
        "Leider kann ich keine direkten Informationen über die Privatadresse "
        "der Geschäftsführung von Everlast Notebook finden."
    )
    assert looks_like_refuse(answer) is True


def test_looks_like_refuse_no_answer() -> None:
    assert looks_like_refuse(NO_ANSWER) is True
    assert NO_ANSWER in SYSTEM


def test_load_gold_includes_studio_wave_two() -> None:
    cases = {case["id"]: case for case in load_gold()}
    assert "studio_flashcards" in cases
    assert "studio_table" in cases
    assert "studio_slides" in cases
    assert "studio_infographic" in cases
    assert "studio_audio" in cases
    assert "studio_video" in cases
    assert cases["studio_flashcards"]["skill_id"] == "studio.flashcards"
    assert cases["studio_table"]["skill_id"] == "studio.table"
    assert cases["studio_slides"]["skill_id"] == "studio.slides"
    assert cases["studio_infographic"]["skill_id"] == "studio.infographic"
    assert cases["studio_flashcards"]["min_cards"] == 6
    assert cases["studio_slides"]["min_slides"] == 4
    assert cases["studio_audio"]["skill_id"] == "studio.audio"
    assert cases["studio_video"]["skill_id"] == "studio.video"
    assert cases["studio_audio"]["min_turns"] == 6
    assert cases["studio_video"]["min_scenes"] == 4
    assert "Aspekt" in cases["studio_mindmap"]["forbidden"]
    assert "Thema" in cases["studio_mindmap"]["forbidden"]
    assert "Kern" in cases["studio_mindmap"]["forbidden"]
    assert "Zweig" in cases["studio_mindmap"]["forbidden"]
    assert "Punkt" in cases["studio_mindmap"]["forbidden"]
    assert "sechs" in cases["studio_quiz"]["keywords"]
    assert "vier Schichten" in cases["studio_quiz"]["forbidden"]
    assert "Unser Ziel ist es" in cases["studio_audio"]["forbidden"]
    assert "Unser Ziel ist es" in cases["studio_video"]["forbidden"]


def test_flatten_flashcards_and_table() -> None:
    cards = flatten_studio_payload(
        {"title": "Karten", "cards": [{"front": "Ingest", "back": "Holt PDF", "cite": "[1]"}]},
        "flashcards",
    )
    assert "Ingest" in cards
    table = flatten_studio_payload(
        {"title": "Schichten", "columns": ["Name"], "rows": [["Embeddings"]]},
        "table",
    )
    assert "Embeddings" in table
    slides = flatten_studio_payload(
        {"title": "Deck", "slides": [{"heading": "Ingest", "bullets": ["Holt PDF"]}]},
        "slides",
    )
    assert "Ingest" in slides
    info = flatten_studio_payload(
        {"title": "Grafik", "items": [{"label": "Schicht", "value": "Retrieval", "detail": "BM25"}]},
        "infographic",
    )
    assert "Retrieval" in info
    audio = flatten_studio_payload(
        {"title": "Ton", "turns": [{"speaker": "A", "text": "Ingest"}]},
        "audio",
    )
    assert "Ingest" in audio
    video = flatten_studio_payload(
        {"title": "Film", "scenes": [{"heading": "Embeddings", "bullets": ["lokal"], "narration": "lokal"}]},
        "video",
    )
    assert "Embeddings" in video


def test_score_hits_keywords() -> None:
    case = {
        "id": "studio_keywords",
        "keywords": ["Ingest", "Embeddings"],
        "forbidden": ["Jahresumsatz"],
    }
    output = "Ingest holt Dateien. Embeddings bleiben lokal."
    scored = score_studio_output(case, output, {}, output, 10, [])
    assert scored["hit"] == 1.0
    assert scored["refuse_ok"] is True


def test_min_cards_halves_hit() -> None:
    case = {"id": "studio_cards", "keywords": ["Ingest"], "forbidden": [], "min_cards": 6}
    output = "Ingest"
    scored = score_studio_output(case, output, {"cards": [{"front": "Ingest", "back": "x"}]}, output, 10, [])
    assert scored["hit"] == 0.5


def test_min_questions_halves_hit() -> None:
    case = {"id": "studio_quiz", "keywords": ["Ingest"], "forbidden": [], "min_questions": 4}
    output = "Ingest"
    scored = score_studio_output(
        case, output, {"questions": [{"question": "Ingest?"}]}, output, 10, []
    )
    assert scored["hit"] == 0.5


def test_min_slides_halves_hit() -> None:
    case = {"id": "studio_slides", "keywords": ["Ingest"], "forbidden": [], "min_slides": 4}
    output = "Ingest"
    scored = score_studio_output(
        case, output, {"slides": [{"heading": "Ingest", "bullets": ["x"]}]}, output, 10, []
    )
    assert scored["hit"] == 0.5


def test_min_turns_halves_hit() -> None:
    case = {"id": "studio_audio", "keywords": ["Ingest"], "forbidden": [], "min_turns": 6}
    output = "Ingest"
    scored = score_studio_output(
        case, output, {"turns": [{"speaker": "A", "text": "Ingest"}]}, output, 10, []
    )
    assert scored["hit"] == 0.5


def test_min_scenes_halves_hit() -> None:
    case = {"id": "studio_video", "keywords": ["Ingest"], "forbidden": [], "min_scenes": 4}
    output = "Ingest"
    scored = score_studio_output(
        case, output, {"scenes": [{"heading": "Ingest", "bullets": ["x"]}]}, output, 10, []
    )
    assert scored["hit"] == 0.5
