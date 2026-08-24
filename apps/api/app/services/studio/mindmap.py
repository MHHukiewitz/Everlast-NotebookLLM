import re
from collections.abc import Callable
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
Baue einen flachen, buschigen Baum: 4 bis 8 Hauptgruppen direkt unter der Wurzel.
Viele ähnliche Blätter kommen unter eine gemeinsame Gruppe.
Ein Knoten hat höchstens 8 direkte Kinder.
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
    stack: list[tuple[int, MindNode]] = []
    root: MindNode | None = None
    for line in text.split("\n"):
        if not line.strip() or line.strip().lower() == "mindmap":
            continue
        indent = len(line) - len(line.lstrip(" "))
        node = MindNode(node_label(line.strip()))
        if root is None:
            root = node
            stack.append((indent, node))
            continue
        while stack and stack[-1][0] >= indent:
            stack.pop()
        parent = stack[-1][1] if stack else root
        parent.children.append(node)
        stack.append((indent, node))
    return root or MindNode("Mindmap")


WIDE_PANE = 560
_MAX_LABEL_CHARS = 22
_CHAR_W = 6.8
_LINE_H = 15
_PAD_X = 10
_PAD_Y = 6
_H_GAP = 16
_V_GAP = 8
_ROW_GAP = 14
_CANVAS_PAD = 16
_NODE_MIN_W = 44
_NODE_MAX_W = 156
_MAX_PER_COLUMN = 6
_MIN_CHILD_BUDGET = 72


class MindBox:
    def __init__(self, node_id: int, label: str, x: float, y: float, w: int, h: int, depth: int) -> None:
        self.id = node_id
        self.label = label
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.depth = depth


class MindEdge:
    def __init__(self, x1: float, y1: float, x2: float, y2: float) -> None:
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2


class MindLayout:
    def __init__(self, boxes: list[MindBox], edges: list[MindEdge], width: int, height: int) -> None:
        self.boxes = boxes
        self.edges = edges
        self.width = width
        self.height = height


class _Local(MindLayout):
    def __init__(self, boxes: list[MindBox], edges: list[MindEdge], width: int, height: int, root: MindBox) -> None:
        super().__init__(boxes, edges, width, height)
        self.root = root


def _wrap_words(label: str, max_chars: int = _MAX_LABEL_CHARS) -> list[str]:
    words = [part for part in (label or "").split() if part]
    if not words:
        return [""]
    lines: list[str] = []
    current = ""
    chunks: list[str] = []
    for word in words:
        if len(word) > max_chars:
            chunks.extend(word[i : i + max_chars] for i in range(0, len(word), max_chars))
        else:
            chunks.append(word)
    for chunk in chunks:
        trial = f"{current} {chunk}" if current else chunk
        if len(trial) <= max_chars:
            current = trial
        else:
            if current:
                lines.append(current)
            current = chunk
    if current:
        lines.append(current)
    return lines[:4]


def _approx_measure(label: str) -> tuple[int, int]:
    lines = _wrap_words(label)
    longest = max((len(line) for line in lines), default=1)
    width = min(_NODE_MAX_W, max(_NODE_MIN_W, round(longest * _CHAR_W + _PAD_X * 2)))
    height = len(lines) * _LINE_H + _PAD_Y * 2
    return width, height


def _subtree_weight(node: MindNode) -> int:
    if not node.children:
        return 1
    return sum(_subtree_weight(child) for child in node.children) + 1


def split_sides(children: list[MindNode]) -> tuple[list[MindNode], list[MindNode]]:
    order = {id(child): index for index, child in enumerate(children)}
    ranked = sorted(children, key=lambda child: (-_subtree_weight(child), order[id(child)]))
    left: list[MindNode] = []
    right: list[MindNode] = []
    left_w = 0
    right_w = 0
    for child in ranked:
        weight = _subtree_weight(child)
        if right_w <= left_w:
            right.append(child)
            right_w += weight
        else:
            left.append(child)
            left_w += weight
    left.sort(key=lambda child: order[id(child)])
    right.sort(key=lambda child: order[id(child)])
    return left, right


def _copy_box(box: MindBox, dx: float = 0, dy: float = 0) -> MindBox:
    return MindBox(box.id, box.label, box.x + dx, box.y + dy, box.w, box.h, box.depth)


def _shift(local: _Local, dx: float, dy: float) -> _Local:
    return _Local(
        [_copy_box(box, dx, dy) for box in local.boxes],
        [MindEdge(edge.x1 + dx, edge.y1 + dy, edge.x2 + dx, edge.y2 + dy) for edge in local.edges],
        local.width,
        local.height,
        _copy_box(local.root, dx, dy),
    )


def _mirror_x(local: _Local) -> _Local:
    flipped = _Local(
        [MindBox(box.id, box.label, -box.x - box.w, box.y, box.w, box.h, box.depth) for box in local.boxes],
        [MindEdge(-edge.x1, edge.y1, -edge.x2, edge.y2) for edge in local.edges],
        local.width,
        local.height,
        MindBox(
            local.root.id,
            local.root.label,
            -local.root.x - local.root.w,
            local.root.y,
            local.root.w,
            local.root.h,
            local.root.depth,
        ),
    )
    min_x = min([box.x for box in flipped.boxes] + [flipped.root.x])
    return _shift(flipped, -min_x, 0)


def _connect(parent: MindBox, child: MindBox, toward: str) -> MindEdge:
    if toward == "down":
        return MindEdge(parent.x + parent.w / 2, parent.y + parent.h, child.x + child.w / 2, child.y)
    if toward == "left":
        return MindEdge(parent.x, parent.y + parent.h / 2, child.x + child.w, child.y + child.h / 2)
    return MindEdge(parent.x + parent.w, parent.y + parent.h / 2, child.x, child.y + child.h / 2)


def _merge(parts: list[_Local]) -> tuple[list[MindBox], list[MindEdge]]:
    boxes = [box for part in parts for box in part.boxes]
    edges = [edge for part in parts for edge in part.edges]
    return boxes, edges


def _empty_local() -> _Local:
    empty = MindBox(0, "", 0, 0, 0, 0, 0)
    return _Local([], [], 0, 0, empty)


def _stack_vertical(layouts: list[_Local]) -> _Local:
    if not layouts:
        return _empty_local()
    y = 0.0
    width = 0
    placed: list[_Local] = []
    for layout in layouts:
        placed.append(_shift(layout, 0, y))
        y += layout.height + _ROW_GAP
        width = max(width, layout.width)
    boxes, edges = _merge(placed)
    return _Local(boxes, edges, width, int(y - _ROW_GAP), placed[0].root)


def _pack_columns(layouts: list[_Local], budget: int) -> _Local:
    col_w = max([item.width for item in layouts] + [_NODE_MIN_W])
    n_fit_natural = max(1, int((budget + _H_GAP) // (col_w + _H_GAP)))
    n_fit_min = max(1, int((budget + _H_GAP) // (_NODE_MIN_W + _H_GAP)))
    desired = max(1, -(-len(layouts) // _MAX_PER_COLUMN))
    n_cols = min(len(layouts), n_fit_min, max(desired, n_fit_natural))
    per_col = -(-len(layouts) // n_cols)
    col_heights = [0.0] * n_cols
    placed: list[_Local] = []
    for index, layout in enumerate(layouts):
        col = min(n_cols - 1, index // per_col)
        x = col * (col_w + _H_GAP)
        y = col_heights[col]
        col_heights[col] += layout.height + _V_GAP
        placed.append(_shift(layout, x, y))
    boxes, edges = _merge(placed)
    return _Local(
        boxes,
        edges,
        (n_cols - 1) * (col_w + _H_GAP) + col_w,
        int(max(col_heights + [_V_GAP]) - _V_GAP),
        placed[0].root,
    )


def _pack_rows(layouts: list[_Local], budget: int) -> _Local:
    x = 0.0
    y = 0.0
    row_h = 0.0
    width = 0.0
    placed: list[_Local] = []
    for layout in layouts:
        if x > 0 and x + layout.width > budget:
            y += row_h + _ROW_GAP
            x = 0
            row_h = 0
        placed.append(_shift(layout, x, y))
        x += layout.width + _H_GAP
        row_h = max(row_h, layout.height)
        width = max(width, x - _H_GAP)
    boxes, edges = _merge(placed)
    return _Local(boxes, edges, int(width), int(y + row_h), placed[0].root)


def _pack_children(layouts: list[_Local], budget: int) -> _Local:
    if not layouts:
        return _empty_local()
    if all(len(item.boxes) == 1 for item in layouts) and len(layouts) > 3:
        return _pack_columns(layouts, budget)
    return _pack_rows(layouts, budget)


def _remap(layouts: list[_Local], packed: _Local) -> list[_Local]:
    placed: list[_Local] = []
    for child in layouts:
        found = next((box for box in packed.boxes if box.id == child.root.id), None)
        dx = found.x - child.root.x if found else 0
        dy = found.y - child.root.y if found else 0
        placed.append(_shift(child, dx, dy))
    return placed


def _layout_node(
    node: MindNode,
    max_width: int,
    depth: int,
    next_id: Callable[[], int],
    measure: Callable[[str], tuple[int, int]],
) -> _Local:
    width, height = measure(node.label)
    self = MindBox(next_id(), node.label, 0, 0, width, height, depth)
    if not node.children:
        return _Local([self], [], width, height, self)
    width_budget = max(max_width, width)
    beside_budget = width_budget - width - _H_GAP
    beside = beside_budget >= _MIN_CHILD_BUDGET
    budget = beside_budget if beside else max(_MIN_CHILD_BUDGET, width_budget - 16)
    child_layouts = [_layout_node(child, budget, depth + 1, next_id, measure) for child in node.children]
    packed = _pack_children(child_layouts, budget)
    placed_children = _remap(child_layouts, packed)
    root_y = 0.0
    children_x = 0.0
    children_y = 0.0
    if beside:
        children_x = width + _H_GAP
        if packed.height > height:
            root_y = (packed.height - height) / 2
        else:
            children_y = (height - packed.height) / 2
    else:
        children_x = 12
        children_y = height + _V_GAP
    kids = [_shift(child, children_x, children_y) for child in placed_children]
    self.x = 0
    self.y = root_y
    boxes, edges = _merge(kids)
    toward = "right" if beside else "down"
    edges = [*edges, *[_connect(self, child.root, toward) for child in kids]]
    total_w = children_x + packed.width if beside else max(width, int(children_x + packed.width))
    total_h = max(root_y + height, children_y + packed.height)
    return _Local([self, *boxes], edges, int(total_w), int(total_h), self)


def _finish(local: _Local) -> MindLayout:
    min_x = min([box.x for box in local.boxes] + [0])
    min_y = min([box.y for box in local.boxes] + [0])
    shifted = _shift(local, _CANVAS_PAD - min_x, _CANVAS_PAD - min_y)
    max_x = max([box.x + box.w for box in shifted.boxes] + [_CANVAS_PAD])
    max_y = max([box.y + box.h for box in shifted.boxes] + [_CANVAS_PAD])
    return MindLayout(shifted.boxes, shifted.edges, int(max_x + _CANVAS_PAD), int(max_y + _CANVAS_PAD))


def _layout_stacked(
    root: MindNode,
    target_width: int,
    next_id: Callable[[], int],
    measure: Callable[[str], tuple[int, int]],
) -> MindLayout:
    width, height = measure(root.label)
    inner = max(_NODE_MIN_W, target_width - _CANVAS_PAD * 2)
    simple = all(
        len(child.children) <= _MAX_PER_COLUMN and all(not grand.children for grand in child.children)
        for child in root.children
    )
    cols = min(2, max(1, inner // 180)) if simple and len(root.children) >= 4 else 1
    child_budget = (inner - (cols - 1) * _H_GAP) // cols if cols > 1 else inner
    child_layouts = [_layout_node(child, child_budget, 1, next_id, measure) for child in root.children]
    packed = _pack_rows(child_layouts, inner) if cols > 1 else _stack_vertical(child_layouts)
    body = _shift(packed, _CANVAS_PAD, _CANVAS_PAD + height + _ROW_GAP)
    root_box = MindBox(
        next_id(),
        root.label,
        _CANVAS_PAD + max(0, (inner - width) / 2),
        _CANVAS_PAD,
        width,
        height,
        0,
    )
    kids = _remap(child_layouts, body)
    boxes, edges = _merge(kids)
    return _finish(
        _Local(
            [root_box, *boxes],
            [*edges, *[_connect(root_box, child.root, "down") for child in kids]],
            max(inner, body.width) + _CANVAS_PAD * 2,
            _CANVAS_PAD + height + _ROW_GAP + body.height + _CANVAS_PAD,
            root_box,
        )
    )


def _layout_balanced(
    root: MindNode,
    target_width: int,
    next_id: Callable[[], int],
    measure: Callable[[str], tuple[int, int]],
) -> MindLayout:
    width, height = measure(root.label)
    left, right = split_sides(root.children)
    side_budget = max(_MIN_CHILD_BUDGET, int((target_width - width - _H_GAP * 2 - _CANVAS_PAD * 2) / 2))
    left_layouts = [_mirror_x(_layout_node(child, side_budget, 1, next_id, measure)) for child in left]
    right_layouts = [_layout_node(child, side_budget, 1, next_id, measure) for child in right]
    left_pack = _stack_vertical(left_layouts)
    right_pack = _stack_vertical(right_layouts)
    mid_h = max(height, left_pack.height, right_pack.height)
    root_box = MindBox(
        next_id(),
        root.label,
        _CANVAS_PAD + left_pack.width + _H_GAP,
        _CANVAS_PAD + (mid_h - height) / 2,
        width,
        height,
        0,
    )
    left_placed = _shift(left_pack, _CANVAS_PAD, _CANVAS_PAD + (mid_h - left_pack.height) / 2)
    right_placed = _shift(right_pack, root_box.x + width + _H_GAP, _CANVAS_PAD + (mid_h - right_pack.height) / 2)
    left_kids = _remap(left_layouts, left_placed)
    right_kids = _remap(right_layouts, right_placed)
    boxes, edges = _merge([*left_kids, *right_kids])
    return _finish(
        _Local(
            [root_box, *boxes],
            [
                *edges,
                *[_connect(root_box, child.root, "left") for child in left_kids],
                *[_connect(root_box, child.root, "right") for child in right_kids],
            ],
            int(root_box.x + width + _H_GAP + right_pack.width + _CANVAS_PAD),
            _CANVAS_PAD * 2 + mid_h,
            root_box,
        )
    )


def layout_mindmap(
    root: MindNode,
    target_width: int,
    measure: Callable[[str], tuple[int, int]] | None = None,
    balanced: bool | None = None,
) -> MindLayout:
    measure_fn = measure or _approx_measure
    next_value = {"n": 0}

    def next_id() -> int:
        next_value["n"] += 1
        return next_value["n"]

    width = max(240, int(target_width))
    if not root.children:
        node_w, node_h = measure_fn(root.label)
        box = MindBox(next_id(), root.label, _CANVAS_PAD, _CANVAS_PAD, node_w, node_h, 0)
        return MindLayout([box], [], node_w + _CANVAS_PAD * 2, node_h + _CANVAS_PAD * 2)
    use_balanced = (len(root.children) >= 2 and width >= WIDE_PANE) if balanced is None else balanced
    if use_balanced:
        return _layout_balanced(root, width, next_id, measure_fn)
    return _layout_stacked(root, width, next_id, measure_fn)


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
