import io
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from app.services.pdf import AI_MARK
from app.services.studio.cites import footnote_line
from app.services.studio.mindmap import layout_mindmap, parse_mindmap

FILLS = ((239, 246, 255), (245, 243, 255), (240, 253, 244), (255, 247, 237))
MIND_FILLS = ((29, 78, 216), (219, 234, 254), (237, 233, 254), (220, 252, 231), (255, 237, 213))
MIND_STROKES = ((30, 58, 138), (96, 165, 250), (167, 139, 250), (74, 222, 128), (251, 146, 60))
MIND_TEXT = ((255, 255, 255), (31, 41, 55), (31, 41, 55), (31, 41, 55), (31, 41, 55))
CHART_COLORS = ((37, 99, 235), (124, 58, 237), (22, 163, 74), (217, 119, 6), (219, 39, 119), (8, 145, 178))
GAP = 16
PAGE_W = 960


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, width: int) -> list[str]:
    words = str(text or "").split()
    if not words:
        return []
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        if draw.textlength(trial, font=font) <= width:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines[:8]


def _png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _footnote_space(citations: list[dict[str, Any]] | None, line_h: int = 14) -> int:
    return line_h * len(citations) if citations else 0


def _draw_footnotes(
    canvas: ImageDraw.ImageDraw,
    citations: list[dict[str, Any]] | None,
    font: ImageFont.ImageFont,
    top: int,
    width: int,
) -> None:
    if not citations:
        return
    y = top
    for cite in citations:
        for line in _wrap(canvas, footnote_line(cite), font, width) or [footnote_line(cite)]:
            canvas.text((24, y), line, font=font, fill=(82, 82, 82))
            y += 14


def infographic_png(title: str, payload: dict[str, Any], citations: list[dict[str, Any]] | None = None) -> bytes:
    probe = Image.new("RGB", (10, 10), (255, 255, 255))
    draw = ImageDraw.Draw(probe)
    title_font = _font(22)
    label_font = _font(12)
    value_font = _font(16)
    number_font = _font(32)
    suffix_font = _font(20)
    body_font = _font(13)
    items = payload.get("items") or []
    charts = payload.get("charts") or []
    y = 56
    chart_h = 0
    for chart in charts:
        points = chart.get("points") or []
        if len(points) < 2:
            continue
        kind = str(chart.get("type") or "bar")
        if kind == "pie":
            chart_h += 200
        elif kind == "bar":
            chart_h += 170
        else:
            chart_h += len(points) * 28 + 40
    y += chart_h
    col_w = 448
    row_h = 0
    card_boxes: list[tuple[int, int, int, dict[str, Any]]] = []
    for index, item in enumerate(items):
        inner = col_w - 32
        caption_lines = _wrap(draw, str(item.get("caption") or ""), body_font, inner)
        value = str(item.get("value") or "")
        caption = str(item.get("caption") or "")
        detail = str(item.get("detail") or "")
        value_lines = _wrap(draw, value, value_font, inner) if value and value != caption else []
        detail_lines = _wrap(draw, detail, body_font, inner) if detail and detail != caption else []
        height = 56 + (40 if item.get("number") else 0)
        height += 18 * len(caption_lines) + 22 * len(value_lines) + 18 * len(detail_lines)
        col = index % 2
        if col == 0:
            row_h = height
        else:
            row_h = max(row_h, height)
        x = 24 + col * (col_w + GAP)
        card_boxes.append((x, y, height, item))
        if col == 1 or index == len(items) - 1:
            y += row_h + GAP
    note_h = _footnote_space(citations)
    total_h = max(y + 36 + note_h, 200)
    image = Image.new("RGB", (PAGE_W, total_h), (255, 255, 255))
    canvas = ImageDraw.Draw(image)
    canvas.text((24, 20), title, font=title_font, fill=(31, 31, 31))
    chart_y = 56
    for chart in charts:
        chart_y = _draw_chart(canvas, chart, 24, chart_y, PAGE_W - 48, label_font, value_font)
    for index, (x, top, height, item) in enumerate(card_boxes):
        fill = FILLS[index % len(FILLS)]
        canvas.rounded_rectangle((x, top, x + col_w, top + height), 10, fill=fill, outline=(229, 229, 229))
        cursor = top + 14
        canvas.text((x + 16, cursor), f"{index + 1} · {item.get('label') or ''}", font=label_font, fill=(115, 115, 115))
        cursor += 22
        if item.get("number"):
            canvas.text((x + 16, cursor), str(item.get("number")), font=number_font, fill=(31, 31, 31))
            if item.get("suffix"):
                num_w = canvas.textlength(str(item.get("number")), font=number_font)
                canvas.text((x + 20 + num_w, cursor + 10), str(item.get("suffix")), font=suffix_font, fill=(82, 82, 82))
            cursor += 40
        caption = str(item.get("caption") or "")
        value = str(item.get("value") or "")
        detail = str(item.get("detail") or "")
        for line in _wrap(canvas, caption, body_font, col_w - 32):
            canvas.text((x + 16, cursor), line, font=body_font, fill=(64, 64, 64))
            cursor += 18
        if value and value != caption:
            for line in _wrap(canvas, value, value_font, col_w - 32):
                canvas.text((x + 16, cursor), line, font=value_font, fill=(31, 31, 31))
                cursor += 22
        if detail and detail != caption:
            for line in _wrap(canvas, detail, body_font, col_w - 32):
                canvas.text((x + 16, cursor), line, font=body_font, fill=(82, 82, 82))
                cursor += 18
    _draw_footnotes(canvas, citations, label_font, total_h - 22 - note_h, PAGE_W - 48)
    canvas.text((24, total_h - 22), AI_MARK, font=label_font, fill=(115, 115, 115))
    return _png_bytes(image)


def _draw_chart(
    canvas: ImageDraw.ImageDraw,
    chart: dict[str, Any],
    x: int,
    y: int,
    width: int,
    label_font: ImageFont.ImageFont,
    value_font: ImageFont.ImageFont,
) -> int:
    points = [point for point in chart.get("points") or [] if isinstance(point, dict)]
    if len(points) < 2:
        return y
    canvas.text((x, y), str(chart.get("title") or "Diagramm"), font=value_font, fill=(31, 31, 31))
    y += 28
    values = [float(point.get("value") or 0) for point in points]
    peak = max(values) or 1
    kind = str(chart.get("type") or "bar")
    unit = str(chart.get("unit") or "")
    if kind == "pie":
        total = sum(values) or 1
        cx, cy, radius = x + 80, y + 70, 60
        start = -90
        for index, point in enumerate(points):
            sweep = 360 * values[index] / total
            color = CHART_COLORS[index % len(CHART_COLORS)]
            canvas.pieslice((cx - radius, cy - radius, cx + radius, cy + radius), start, start + sweep, fill=color)
            canvas.rectangle((x + 180, y + index * 22, x + 190, y + 10 + index * 22), fill=color)
            canvas.text(
                (x + 198, y + index * 22),
                f"{point.get('label') or ''} · {values[index]:g}{(' ' + unit) if unit else ''}",
                font=label_font,
                fill=(31, 31, 31),
            )
            start += sweep
        return y + 160
    if kind == "bar":
        bar_w = max(24, int((width - 20) / len(points)) - 8)
        for index, point in enumerate(points):
            bar_h = max(6, int(values[index] / peak * 110))
            left = x + index * (bar_w + 8)
            color = CHART_COLORS[index % len(CHART_COLORS)]
            canvas.rounded_rectangle((left, y + 120 - bar_h, left + bar_w, y + 120), 4, fill=color)
            canvas.text((left, y + 124), str(point.get("label") or "")[:12], font=label_font, fill=(82, 82, 82))
            canvas.text((left, y), f"{values[index]:g}", font=label_font, fill=(31, 31, 31))
        return y + 150
    for index, point in enumerate(points):
        bar_w = max(8, int(values[index] / peak * 360))
        color = CHART_COLORS[index % len(CHART_COLORS)]
        yy = y + index * 28
        canvas.text((x, yy), str(point.get("label") or ""), font=label_font, fill=(31, 31, 31))
        canvas.rounded_rectangle((x + 200, yy, x + 200 + bar_w, yy + 16), 4, fill=color)
        canvas.text((x + 208 + bar_w, yy), f"{values[index]:g}{(' ' + unit) if unit else ''}", font=label_font, fill=(31, 31, 31))
    return y + len(points) * 28 + 16


def mindmap_png(title: str, payload: dict[str, Any], citations: list[dict[str, Any]] | None = None) -> bytes:
    root = parse_mindmap(str(payload.get("mermaid") or ""))
    title_font = _font(22)
    node_font = _font(15)
    probe = Image.new("RGB", (10, 10), (255, 255, 255))
    draw = ImageDraw.Draw(probe)

    def measure(label: str) -> tuple[int, int]:
        lines = _wrap(draw, label, node_font, 200) or [label]
        return (int(max(draw.textlength(line, font=node_font) for line in lines)) + 28, 18 * len(lines) + 16)

    placed = layout_mindmap(root, PAGE_W - 48, measure, balanced=False)
    title_h = 48
    note_h = _footnote_space(citations)
    image = Image.new(
        "RGB",
        (max(placed.width + 24, 400), max(placed.height + title_h + 28 + note_h, 200)),
        (255, 255, 255),
    )
    canvas = ImageDraw.Draw(image)
    canvas.text((24, 16), title, font=title_font, fill=(31, 31, 31))
    for edge in placed.edges:
        x1, y1 = edge.x1 + 12, edge.y1 + title_h
        x2, y2 = edge.x2 + 12, edge.y2 + title_h
        if edge.toward == "down":
            mid_y = y1 + max(12, (y2 - y1) / 2)
            canvas.line((x1, y1, x1, mid_y, x2, mid_y, x2, y2), fill=(148, 163, 184), width=2)
        else:
            direction = -1 if edge.toward == "left" else 1
            mid_x = x1 + direction * max(14, abs(x2 - x1) / 2)
            canvas.line((x1, y1, mid_x, y1, mid_x, y2, x2, y2), fill=(148, 163, 184), width=2)
    for box in placed.boxes:
        x = int(box.x + 12)
        y = int(box.y + title_h)
        tone = min(box.depth, len(MIND_FILLS) - 1)
        canvas.rounded_rectangle(
            (x, y, x + box.w, y + box.h),
            14 if box.depth == 0 else 10,
            fill=MIND_FILLS[tone],
            outline=MIND_STROKES[tone],
        )
        lines = _wrap(canvas, box.label, node_font, max(box.w - 16, 40)) or [box.label]
        cursor = y + 8
        for line in lines:
            canvas.text((x + 12, cursor), line, font=node_font, fill=MIND_TEXT[tone])
            cursor += 18
    _draw_footnotes(canvas, citations, _font(11), image.height - 22 - note_h, max(placed.width, 360))
    canvas.text((24, image.height - 22), AI_MARK, font=_font(11), fill=(115, 115, 115))
    return _png_bytes(image)
