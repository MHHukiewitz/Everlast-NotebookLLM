from app.services.eval_harness import flatten_studio_payload, load_gold, score_studio_output


def test_load_gold_includes_studio_wave_two() -> None:
    cases = {case["id"]: case for case in load_gold()}
    assert "studio_flashcards" in cases
    assert "studio_table" in cases
    assert cases["studio_flashcards"]["skill_id"] == "studio.flashcards"
    assert cases["studio_table"]["skill_id"] == "studio.table"
    assert cases["studio_flashcards"]["min_cards"] == 6


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
