import html
import re
from typing import Any
from urllib.parse import urlparse

CITE_MARK = re.compile(r"\[(\d+)\]")
_GROUPED_CITE = re.compile(r"\[(\d+(?:\s*,\s*\d+)+)\]")


def expand_grouped_cite_marks(text: str) -> str:
    def _expand(match: re.Match[str]) -> str:
        return "".join(f"[{part.strip()}]" for part in match.group(1).split(",") if part.strip())

    return _GROUPED_CITE.sub(_expand, text or "")


def citation_marks(text: str) -> set[int]:
    return {int(found.group(1)) for found in CITE_MARK.finditer(expand_grouped_cite_marks(text))}


def http_url(value: str | None) -> str:
    raw = (value or "").strip()
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return raw


def cite_title(cite: dict[str, Any]) -> str:
    return str(cite.get("title") or cite.get("source_title") or f"Quelle {cite.get('n')}").strip()


def cite_url(cite: dict[str, Any] | None) -> str:
    if not cite:
        return ""
    return http_url(str(cite.get("url") or ""))


def _field(source: Any, name: str) -> Any:
    if isinstance(source, dict):
        return source.get(name)
    return getattr(source, name, None)


def _source_id(source: Any) -> str:
    value = _field(source, "id")
    return str(value) if value is not None else ""


def _ready_sources(sources: list[Any]) -> list[Any]:
    ready: list[Any] = []
    for source in sources:
        status = str(_field(source, "status") or "ready")
        if status == "ready":
            ready.append(source)
    return ready


def _find_source(sources: list[Any], source_id: Any) -> Any | None:
    if not source_id:
        return None
    wanted = str(source_id)
    for source in sources:
        if _source_id(source) == wanted:
            return source
    return None


def resolve_citations(payload: dict[str, Any], sources: list[Any] | None = None) -> list[dict[str, Any]]:
    ready = _ready_sources(sources or [])
    raw = payload.get("citations") or []
    if raw:
        resolved: list[dict[str, Any]] = []
        for index, item in enumerate(raw):
            n = int(item.get("n") or index + 1)
            source = _find_source(ready, item.get("source_id"))
            title = item.get("source_title") or item.get("title") or _field(source, "title") or f"Quelle {n}"
            url = item.get("url") or _field(source, "origin_uri") or ""
            resolved.append(
                {
                    "n": n,
                    "source_id": str(item.get("source_id") or _source_id(source) or ""),
                    "title": str(title),
                    "url": str(url or ""),
                    "quote": str(item.get("quote") or ""),
                }
            )
        return resolved
    return [
        {
            "n": index + 1,
            "source_id": _source_id(source),
            "title": str(_field(source, "title") or f"Quelle {index + 1}"),
            "url": str(_field(source, "origin_uri") or ""),
            "quote": "",
        }
        for index, source in enumerate(ready)
    ]


def unique_citations(citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for item in citations:
        key = str(item.get("source_id") or item.get("url") or f"n:{item.get('n')}")
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def used_citations(text: str, citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    marks = citation_marks(text)
    return [item for item in citations if item.get("n") in marks]


def payload_cite_text(payload: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("body", "body_md", "mermaid"):
        if payload.get(key):
            parts.append(str(payload.get(key)))
    for card in payload.get("cards") or []:
        parts.extend([str(card.get("front") or ""), str(card.get("back") or ""), str(card.get("cite") or "")])
    for question in payload.get("questions") or []:
        parts.append(str(question.get("question") or ""))
        parts.extend(str(choice) for choice in question.get("choices") or [])
        parts.append(str(question.get("explanation") or ""))
    for slide in payload.get("slides") or []:
        parts.append(str(slide.get("heading") or ""))
        parts.extend(str(bullet) for bullet in slide.get("bullets") or [])
        parts.append(str(slide.get("notes") or ""))
    for row in payload.get("rows") or []:
        parts.extend(str(cell) for cell in row)
    for column in payload.get("columns") or []:
        parts.append(str(column))
    for item in payload.get("items") or []:
        parts.extend(
            [
                str(item.get("label") or ""),
                str(item.get("value") or ""),
                str(item.get("detail") or ""),
                str(item.get("caption") or ""),
            ]
        )
    for chart in payload.get("charts") or []:
        parts.extend([str(chart.get("title") or ""), str(chart.get("cite") or "")])
    for turn in payload.get("turns") or []:
        parts.append(str(turn.get("text") or ""))
    for scene in payload.get("scenes") or []:
        parts.append(str(scene.get("heading") or ""))
        parts.extend(str(bullet) for bullet in scene.get("bullets") or [])
        parts.append(str(scene.get("narration") or ""))
    return "\n".join(parts)


def citations_for_export(payload: dict[str, Any], sources: list[Any] | None = None) -> list[dict[str, Any]]:
    resolved = resolve_citations(payload, sources)
    used = used_citations(payload_cite_text(payload), resolved)
    if used:
        return used
    if payload.get("citations"):
        return unique_citations(resolved)
    return []


def footnote_line(cite: dict[str, Any]) -> str:
    title = cite_title(cite)
    url = cite_url(cite)
    if url:
        return f"[{cite['n']}] {title} — {url}"
    return f"[{cite['n']}] {title}"


def markdown_cite_text(text: str, citations: list[dict[str, Any]]) -> str:
    by_n = {int(item["n"]): item for item in citations}

    def _replace(match: re.Match[str]) -> str:
        n = int(match.group(1))
        url = cite_url(by_n.get(n))
        if url:
            return f"[[{n}]]({url})"
        return match.group(0)

    return CITE_MARK.sub(_replace, expand_grouped_cite_marks(text))


def markdown_quellen(citations: list[dict[str, Any]]) -> str:
    if not citations:
        return ""
    lines = ["## Quellen", ""]
    for cite in citations:
        title = cite_title(cite)
        url = cite_url(cite)
        if url:
            lines.append(f"- [{cite['n']}] [{title}]({url})")
        else:
            lines.append(f"- [{cite['n']}] {title}")
    return "\n".join(lines) + "\n"


def insert_before_mark(text: str, extra: str, mark: str) -> str:
    if not extra.strip():
        return text
    stripped = text.rstrip()
    block = extra.strip()
    if stripped.endswith(mark):
        return stripped[: -len(mark)].rstrip() + "\n\n" + block + "\n\n" + mark + "\n"
    return stripped + "\n\n" + block + "\n"


def finish_markdown(text: str, citations: list[dict[str, Any]], mark: str) -> str:
    linked = markdown_cite_text(text, citations)
    return insert_before_mark(linked, markdown_quellen(citations), mark)


def finish_plain(text: str, citations: list[dict[str, Any]], mark: str) -> str:
    body = expand_grouped_cite_marks(text)
    if not citations:
        return body if body.endswith("\n") else body + "\n"
    notes = "Quellen\n\n" + "\n".join(footnote_line(cite) for cite in citations) + "\n"
    return insert_before_mark(body, notes, mark)


def html_cite_text(text: str, citations: list[dict[str, Any]]) -> str:
    by_n = {int(item["n"]): item for item in citations}
    expanded = expand_grouped_cite_marks(str(text or ""))
    escaped = html.escape(expanded)

    def _replace(match: re.Match[str]) -> str:
        n = int(match.group(1))
        url = cite_url(by_n.get(n))
        mark = match.group(0)
        if url:
            return f'<a href="{html.escape(url, quote=True)}">{mark}</a>'
        return mark

    return CITE_MARK.sub(_replace, escaped)


def link_marks_in_svg(svg: str, citations: list[dict[str, Any]]) -> str:
    by_n = {int(item["n"]): item for item in citations}

    def _replace(match: re.Match[str]) -> str:
        n = int(match.group(1))
        url = cite_url(by_n.get(n))
        mark = match.group(0)
        if url:
            return f'<a href="{html.escape(url, quote=True)}">{mark}</a>'
        return mark

    return CITE_MARK.sub(_replace, expand_grouped_cite_marks(svg))


def csv_quellen_rows(citations: list[dict[str, Any]], width: int) -> list[list[str]]:
    if not citations:
        return []
    rows = [["Quellen"] + [""] * max(0, width - 1)]
    for cite in citations:
        url = cite_url(cite)
        row = [footnote_line(cite)]
        if width >= 2:
            row.append(url)
            row.extend("" for _ in range(width - 2))
        rows.append(row)
    return rows


def mermaid_quellen(text: str, citations: list[dict[str, Any]]) -> str:
    body = text.rstrip() + "\n"
    if not citations:
        return body
    lines = [body.rstrip(), "%% Quellen"]
    for cite in citations:
        lines.append(f"%% {footnote_line(cite)}")
    return "\n".join(lines) + "\n"


def json_references(citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "n": cite["n"],
            "title": cite_title(cite),
            "url": cite_url(cite) or None,
        }
        for cite in citations
    ]
