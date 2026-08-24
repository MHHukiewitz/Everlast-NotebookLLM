import csv
import io
import json
from typing import Any

from app.services.pdf import AI_MARK, markdown_to_pdf

FORMATS: dict[str, tuple[str, ...]] = {
    "note": ("md", "txt", "pdf", "json"),
    "report": ("md", "pdf", "json"),
    "mindmap": ("mmd", "pdf", "json"),
    "quiz": ("md", "csv", "pdf", "json"),
    "flashcards": ("md", "csv", "pdf", "json"),
    "table": ("csv", "md", "pdf", "json"),
}

MEDIA: dict[str, str] = {
    "md": "text/markdown; charset=utf-8",
    "txt": "text/plain; charset=utf-8",
    "pdf": "application/pdf",
    "json": "application/json; charset=utf-8",
    "csv": "text/csv; charset=utf-8",
    "mmd": "text/plain; charset=utf-8",
}


def allowed_formats(artifact_type: str) -> tuple[str, ...]:
    return FORMATS.get(artifact_type, ())


def safe_name(title: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in "-_ " else "_" for char in title)
    return (cleaned.strip() or "studio")[:40]


def _text(value: str) -> bytes:
    return value.encode("utf-8")


def _json_bytes(artifact_type: str, title: str, payload: dict[str, Any]) -> bytes:
    body = {
        "ai_generated": True,
        "notice": AI_MARK,
        "type": artifact_type,
        "title": title,
        "payload": payload,
    }
    return json.dumps(body, ensure_ascii=False, indent=2).encode("utf-8")


def _csv_bytes(rows: list[list[str]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue().encode("utf-8")


def _note_md(title: str, payload: dict[str, Any]) -> str:
    return f"# {title}\n\n{payload.get('body') or ''}\n\n{AI_MARK}\n"


def _report_md(title: str, payload: dict[str, Any]) -> str:
    return f"# {title}\n\n{payload.get('body_md') or ''}\n\n{AI_MARK}\n"


def _mindmap_md(title: str, payload: dict[str, Any]) -> str:
    mermaid = payload.get("mermaid") or ""
    return f"# {title}\n\n```mermaid\n{mermaid}\n```\n\n{AI_MARK}\n"


def _quiz_md(title: str, payload: dict[str, Any]) -> str:
    parts = [f"# {title}", ""]
    for index, question in enumerate(payload.get("questions") or [], start=1):
        parts.append(f"## {index}. {question.get('question') or ''}")
        for choice in question.get("choices") or []:
            parts.append(f"- {choice}")
        answer_index = question.get("answer_index")
        choices = question.get("choices") or []
        if isinstance(answer_index, int) and 0 <= answer_index < len(choices):
            parts.append(f"Antwort: {choices[answer_index]}")
        if question.get("explanation"):
            parts.append(str(question.get("explanation")))
        parts.append("")
    parts.append(AI_MARK)
    return "\n".join(parts) + "\n"


def _quiz_csv(payload: dict[str, Any]) -> list[list[str]]:
    rows = [["front", "back"]]
    for question in payload.get("questions") or []:
        choices = question.get("choices") or []
        answer_index = question.get("answer_index")
        answer = ""
        if isinstance(answer_index, int) and 0 <= answer_index < len(choices):
            answer = str(choices[answer_index])
        rows.append([str(question.get("question") or ""), answer])
    rows.append(["(KI-generiert)", AI_MARK])
    return rows


def _flashcards_md(title: str, payload: dict[str, Any]) -> str:
    parts = [f"# {title}", ""]
    for card in payload.get("cards") or []:
        parts.append(f"## {card.get('front') or ''}")
        parts.append(str(card.get("back") or ""))
        if card.get("cite"):
            parts.append(str(card.get("cite")))
        parts.append("")
    parts.append(AI_MARK)
    return "\n".join(parts) + "\n"


def _flashcards_csv(payload: dict[str, Any]) -> list[list[str]]:
    rows = [["front", "back"]]
    for card in payload.get("cards") or []:
        back = str(card.get("back") or "")
        if card.get("cite"):
            back = f"{back} {card.get('cite')}"
        rows.append([str(card.get("front") or ""), back])
    rows.append(["(KI-generiert)", AI_MARK])
    return rows


def _table_md(title: str, payload: dict[str, Any]) -> str:
    columns = [str(column) for column in payload.get("columns") or []]
    rows = payload.get("rows") or []
    parts = [f"# {title}", ""]
    if columns:
        parts.append("| " + " | ".join(columns) + " |")
        parts.append("| " + " | ".join("---" for _ in columns) + " |")
        for row in rows:
            cells = [str(cell) for cell in row]
            while len(cells) < len(columns):
                cells.append("")
            parts.append("| " + " | ".join(cells[: len(columns)]) + " |")
    parts.append("")
    parts.append(AI_MARK)
    return "\n".join(parts) + "\n"


def _table_csv(payload: dict[str, Any]) -> list[list[str]]:
    columns = [str(column) for column in payload.get("columns") or []]
    rows = [columns]
    for row in payload.get("rows") or []:
        rows.append([str(cell) for cell in row])
    notice = [AI_MARK]
    notice.extend("" for _ in columns[1:])
    rows.append(notice)
    return rows


def export_artifact(
    artifact_type: str, title: str, payload: dict[str, Any], fmt: str
) -> tuple[bytes, str, str]:
    allowed = allowed_formats(artifact_type)
    if not allowed or fmt not in allowed:
        raise ValueError("Dieses Exportformat ist nicht verfügbar.")
    if fmt == "json":
        data = _json_bytes(artifact_type, title, payload)
    elif artifact_type == "note" and fmt == "md":
        data = _text(_note_md(title, payload))
    elif artifact_type == "note" and fmt == "txt":
        data = _text(f"{title}\n\n{payload.get('body') or ''}\n\n{AI_MARK}\n")
    elif artifact_type == "note" and fmt == "pdf":
        data = markdown_to_pdf(title, _note_md(title, payload))
    elif artifact_type == "report" and fmt == "md":
        data = _text(_report_md(title, payload))
    elif artifact_type == "report" and fmt == "pdf":
        data = markdown_to_pdf(title, _report_md(title, payload))
    elif artifact_type == "mindmap" and fmt == "mmd":
        data = _text(f"%% {AI_MARK}\n{payload.get('mermaid') or ''}\n")
    elif artifact_type == "mindmap" and fmt == "pdf":
        data = markdown_to_pdf(title, _mindmap_md(title, payload))
    elif artifact_type == "quiz" and fmt == "md":
        data = _text(_quiz_md(title, payload))
    elif artifact_type == "quiz" and fmt == "csv":
        data = _csv_bytes(_quiz_csv(payload))
    elif artifact_type == "quiz" and fmt == "pdf":
        data = markdown_to_pdf(title, _quiz_md(title, payload))
    elif artifact_type == "flashcards" and fmt == "md":
        data = _text(_flashcards_md(title, payload))
    elif artifact_type == "flashcards" and fmt == "csv":
        data = _csv_bytes(_flashcards_csv(payload))
    elif artifact_type == "flashcards" and fmt == "pdf":
        data = markdown_to_pdf(title, _flashcards_md(title, payload))
    elif artifact_type == "table" and fmt == "md":
        data = _text(_table_md(title, payload))
    elif artifact_type == "table" and fmt == "csv":
        data = _csv_bytes(_table_csv(payload))
    elif artifact_type == "table" and fmt == "pdf":
        data = markdown_to_pdf(title, _table_md(title, payload))
    else:
        raise ValueError("Dieses Exportformat ist nicht verfügbar.")
    filename = f"{safe_name(title)}.{fmt}"
    return data, MEDIA[fmt], filename
