from app.services.studio.audio import prepare_audio
from app.services.studio.flashcards import prepare_flashcards
from app.services.studio.generate import EVAL_MODE, RENDER_RETRIES
from app.services.studio.infographic import prepare_infographic
from app.services.studio.mindmap import prepare_mindmap
from app.services.studio.quiz import prepare_quiz
from app.services.studio.report import prepare_report
from app.services.studio.slides import prepare_slides
from app.services.studio.table import prepare_table
from app.services.studio.video import prepare_video


def test_render_retries_is_three() -> None:
    assert RENDER_RETRIES == 3


def test_prepare_quiz_needs_four_complete_questions() -> None:
    ok, reason = prepare_quiz({"questions": [{"question": "Q", "choices": ["A", "B", "C", "D"], "answer_index": 0}]})
    assert ok is False
    assert "vier" in reason
    payload = {
        "questions": [
            {"question": f"Q{index}", "choices": ["A", "B", "C", "D"], "answer_index": 1} for index in range(4)
        ]
    }
    assert prepare_quiz(payload) == (True, "")


def test_prepare_quiz_rejects_vier_schichten_in_eval() -> None:
    payload = {
        "questions": [
            {
                "question": "Welche vier Schichten hat das System?",
                "choices": ["A", "B", "C", "D"],
                "answer_index": 0,
            },
            {"question": "Q2", "choices": ["A", "B", "C", "D"], "answer_index": 1},
            {"question": "Q3", "choices": ["A", "B", "C", "D"], "answer_index": 1},
            {"question": "Q4", "choices": ["A", "B", "C", "D"], "answer_index": 1},
        ]
    }
    token = EVAL_MODE.set(True)
    ok, reason = prepare_quiz(payload)
    EVAL_MODE.reset(token)
    assert ok is False
    assert "Schichtenzahl" in reason
    assert prepare_quiz(payload) == (True, "")


def test_prepare_flashcards_needs_six_cards() -> None:
    assert prepare_flashcards({"cards": [{"front": "A", "back": "B"}]})[0] is False
    cards = [{"front": f"F{index}", "back": f"B{index}"} for index in range(6)]
    assert prepare_flashcards({"cards": cards}) == (True, "")


def test_prepare_slides_needs_four_slides() -> None:
    assert prepare_slides({"slides": [{"heading": "H", "bullets": ["a", "b", "c"]}]})[0] is False
    slides = [{"heading": f"H{index}", "bullets": ["a", "b", "c"]} for index in range(4)]
    assert prepare_slides({"slides": slides}) == (True, "")


def test_prepare_table_needs_shape() -> None:
    assert prepare_table({"columns": ["A"], "rows": [["1"], ["2"], ["3"]]})[0] is False
    assert prepare_table({"columns": ["A", "B"], "rows": [["1", "2"]]})[0] is False
    assert prepare_table({"columns": ["A", "B"], "rows": [["1", "2"], ["3", "4"], ["5", "6"]]}) == (True, "")


def test_prepare_report_needs_cite() -> None:
    assert prepare_report({"body_md": "Kurz"})[0] is False
    long_body = "Ingest holt Dokumente. Embeddings bleiben lokal. " * 3
    assert prepare_report({"body_md": long_body})[0] is False
    payload = {"body_md": long_body + " Siehe [1].", "citations": [{"n": 1, "source_id": "s1"}]}
    assert prepare_report(payload) == (True, "")
    assert payload["citations"][0]["n"] == 1


def test_prepare_audio_and_video() -> None:
    turns = [{"text": "Hallo"}, {"text": "Hi"}]
    assert prepare_audio({"turns": turns}, min_turns=6)[0] is False
    turns = [{"text": f"T{index}"} for index in range(6)]
    assert prepare_audio({"turns": turns}) == (True, "")
    one_voice = [{"speaker": "A", "text": f"T{index}"} for index in range(6)]
    assert prepare_audio({"turns": one_voice}) == (True, "")
    dialog = [{"speaker": "A" if index % 2 == 0 else "B", "text": f"T{index}"} for index in range(6)]
    ok, reason = prepare_audio({"turns": dialog})
    assert ok is False
    assert "Dialog" in reason
    scenes = [{"heading": "H", "bullets": ["a", "b", "c"], "narration": "N"}]
    assert prepare_video({"scenes": scenes})[0] is False
    scenes = [{"heading": f"H{index}", "bullets": ["a", "b", "c"], "narration": "N"} for index in range(4)]
    assert prepare_video({"scenes": scenes}) == (True, "")


def test_prepare_audio_and_video_reject_filler_in_eval() -> None:
    turns = [{"text": f"T{index}"} for index in range(5)]
    turns.append({"text": "Unser Ziel ist es, präzise Ergebnisse zu liefern."})
    scenes = [
        {"heading": f"H{index}", "bullets": ["a", "b", "c"], "narration": "N"} for index in range(3)
    ]
    scenes.append(
        {
            "heading": "H3",
            "bullets": ["a", "b", "c"],
            "narration": "Unser Ziel ist es, Daten zu sichern.",
        }
    )
    token = EVAL_MODE.set(True)
    audio_ok, audio_reason = prepare_audio({"turns": turns})
    video_ok, video_reason = prepare_video({"scenes": scenes})
    EVAL_MODE.reset(token)
    assert audio_ok is False
    assert "Floskel" in audio_reason
    assert video_ok is False
    assert "Floskel" in video_reason
    assert prepare_audio({"turns": turns}) == (True, "")
    assert prepare_video({"scenes": scenes}) == (True, "")


def test_prepare_infographic_needs_four_items() -> None:
    payload = {
        "items": [
            {"label": "A", "value": "Analysegespräch in 15 Minuten", "detail": "Kostenlos und ohne Druck."},
            {"label": "B", "value": "Implementierung von KI-Systemen", "detail": "Vom Gespräch bis zum Betrieb."},
            {"label": "C", "value": "Schulungen für Teams vor Ort", "detail": "Academy und Zertifizierung."},
            {"label": "D", "value": "Datenschutz nach der DSGVO", "detail": "Personenbezogene Daten in der EU."},
        ]
    }
    assert prepare_infographic(payload) == (True, "")
    assert prepare_infographic({"items": payload["items"][:2]})[0] is False


def test_prepare_mindmap_accepts_valid_tree() -> None:
    payload = {"mermaid_lines": ["mindmap", "  root((Ingest))", "    PDF", "    HTML"]}
    ok, reason = prepare_mindmap(payload)
    assert ok is True
    assert reason == ""
    assert payload["mermaid"].startswith("mindmap")


def test_prepare_mindmap_rejects_placeholder_nodes() -> None:
    payload = {"mermaid_lines": ["mindmap", "  root((Kern))", "    Zweig", "    Punkt"]}
    ok, reason = prepare_mindmap(payload)
    assert ok is False
    assert "Platzhalter" in reason
