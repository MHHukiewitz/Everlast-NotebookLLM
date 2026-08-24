import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notebook
from app.services.studio.generate import STUDIO_USER, generate_json, save_artifact, source_ids_from_args, topic_from_args

PLACEHOLDER_LABELS = {"aspekt", "thema", "detail", "kern", "zweig", "punkt"}

SKILL_GUIDE = """Mindmap nur aus den gewählten Quellen.
Die erste Zeile ist mindmap.
Die zweite Zeile ist die Wurzel.
Weitere Zeilen sind eingerückte Begriffe aus dem Quellenkontext.
Nutze nur Begriffe aus den Quellen.
"""

SYSTEM = f"""Du bist Everlast Notebook, ein KI-System. Sage das klar.
Folge dieser Fähigkeitsbeschreibung:
{SKILL_GUIDE}
Antworte nur mit einem JSON-Objekt.
Schema: {{"title": "string", "mermaid_lines": ["mindmap", "  root((...))", "    ..."]}}
Markiere den Titel als KI-generiert, indem du '(KI-generiert)' anhängst.
"""

_NODE_TOKEN = re.compile(
    r"root\(\([^)]*\)\)|"
    r"[^\s(]+\(\([^)]*\)\)|"
    r"[^\s(]+\([^)]*\)|"
    r"[^\s[]+\[[^\]]*\]|"
    r'"[^"]+"|'
    r"[^\s]+"
)
_SHAPE = re.compile(
    r"^(?:root)?"
    r"(?:"
    r"\(\((.*)\)\)|"
    r"\((.*)\)|"
    r"\[(.*)\]|"
    r"\"(.*)\"|"
    r"\)\)(.*)\(\("
    r")$"
)
_LIST_MARK = re.compile(r"^[-+*•–—]\s*")
_NAMED_SHAPE = re.compile(
    r"^[^\s(]+"
    r"(?:"
    r"\(\((.*)\)\)|"
    r"\((.*)\)|"
    r"\[(.*)\]"
    r")$"
)


class MindNode:
    def __init__(self, label: str) -> None:
        self.label = label
        self.children: list[MindNode] = []


def normalize_mermaid(source: str) -> str:
    text = (source or "").strip()
    if not text:
        return ""
    if "\n" not in text and "\\n" in text:
        text = text.replace("\\n", "\n")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n") if line.strip()]
    if len(lines) == 1:
        lines = _split_oneline(lines[0])
    if lines and lines[0].strip().lower() == "mindmap":
        lines = lines[1:]
    return "\n".join(["mindmap", *_unique_nodes(_indent_body(lines))])


def parse_mindmap(source: str) -> MindNode:
    text = normalize_mermaid(source)
    nodes: list[tuple[int, MindNode]] = []
    for line in text.split("\n"):
        if not line.strip() or line.strip().lower() == "mindmap":
            continue
        indent = len(line) - len(line.lstrip(" "))
        node = MindNode(node_label(line.strip()))
        while nodes and nodes[-1][0] >= indent:
            nodes.pop()
        if nodes:
            nodes[-1][1].children.append(node)
        nodes.append((indent, node))
    if not nodes:
        return MindNode("Mindmap")
    return nodes[0][1]


def mermaid_from_payload(payload: dict[str, Any]) -> str:
    mermaid = str(payload.get("mermaid") or "").strip()
    lines = payload.get("mermaid_lines")
    if isinstance(lines, list) and any(str(line).strip() for line in lines):
        joined = "\n".join(str(line) for line in lines)
        if joined.count("\n") >= mermaid.count("\n"):
            mermaid = joined
    return mermaid


def safe_label(label: str) -> str:
    text = _LIST_MARK.sub("", (label or "").strip())
    for char in "[](){}\n\t":
        text = text.replace(char, " ")
    return " ".join(text.split())[:72]


def check_mindmap(source: str) -> tuple[bool, str]:
    text = (source or "").strip()
    if not text.startswith("mindmap"):
        return False, "erste Zeile ist nicht mindmap"
    lines = [line for line in text.split("\n") if line.strip()]
    if len(lines) < 3:
        return False, "zu wenige Knoten"
    for line in lines[1:]:
        stripped = line.strip()
        if re.search(r"\[\s*[-+*]", stripped):
            return False, "Knotenlabel beginnt mit einem Listenzeichen"
        if stripped.count("[") != stripped.count("]"):
            return False, "eckige Klammern sind ungleich"
        if stripped.count("(") != stripped.count(")"):
            return False, "runde Klammern sind ungleich"
        label = safe_label(node_label(stripped))
        if not label:
            return False, "leerer Knoten"
        if label.casefold() in PLACEHOLDER_LABELS:
            return False, "Platzhalter-Knoten"
    return True, ""


def node_label(raw: str) -> str:
    text = re.sub(r"::icon\([^)]*\)", "", raw).strip()
    named = _NAMED_SHAPE.match(text)
    if named:
        return next(part for part in named.groups() if part is not None).strip() or text
    shaped = _SHAPE.match(text)
    if shaped:
        return next(part for part in shaped.groups() if part is not None).strip() or text
    return text


def _split_oneline(line: str) -> list[str]:
    text = line.strip()
    if text.lower().startswith("mindmap"):
        text = text[7:].strip()
    tokens = [token for token in _NODE_TOKEN.findall(text) if token and token.lower() != "mindmap"]
    if len(tokens) <= 1:
        return [line]
    return tokens


def _indent_body(lines: list[str]) -> list[str]:
    raw: list[tuple[int, str]] = []
    for line in lines:
        if not line.strip():
            continue
        expanded = line.replace("\t", "    ")
        indent = len(expanded) - len(expanded.lstrip(" "))
        raw.append((indent, expanded.strip()))
    if not raw:
        return ["  root((Mindmap))"]
    if max(item[0] for item in raw) == 0:
        out = [f"  {raw[0][1]}"]
        out.extend(f"    {label}" for _, label in raw[1:])
        return out
    base = min(item[0] for item in raw)
    return [f"  {' ' * (indent - base)}{label}" for indent, label in raw]


def _unique_nodes(lines: list[str]) -> list[str]:
    out: list[str] = []
    for index, line in enumerate(lines):
        pad = " " * (len(line) - len(line.lstrip(" ")))
        label = safe_label(node_label(line.strip()))
        if not label:
            continue
        if index == 0:
            out.append(f"{pad}root(({label}))")
            continue
        if " " in label:
            out.append(f"{pad}n{index}[{label}]")
        else:
            out.append(f"{pad}n{index}({label})")
    return out or ["  root((Mindmap))"]


def prepare_mindmap(payload: dict[str, Any]) -> tuple[bool, str]:
    mermaid = normalize_mermaid(mermaid_from_payload(payload))
    ok, reason = check_mindmap(mermaid)
    if ok:
        payload["mermaid"] = mermaid
    return ok, reason


async def create_mindmap(
    session: AsyncSession, notebook: Notebook, args: dict[str, Any]
) -> dict[str, Any]:
    payload = await generate_json(
        session,
        notebook,
        topic_from_args(args),
        SYSTEM,
        STUDIO_USER,
        source_ids_from_args(args),
        check=prepare_mindmap,
    )
    title = str(payload.get("title") or "Mindmap")
    return await save_artifact(session, notebook, "studio.mindmap", "mindmap", title, payload)
