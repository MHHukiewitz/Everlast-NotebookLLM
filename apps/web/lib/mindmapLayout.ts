export type MindNode = { label: string; children: MindNode[] };

export type PlacedBox = {
  id: number;
  label: string;
  lines: string[];
  x: number;
  y: number;
  w: number;
  h: number;
  depth: number;
};

export type EdgeToward = "left" | "right" | "down";

export type PlacedEdge = { x1: number; y1: number; x2: number; y2: number; toward: EdgeToward };

export type MindLayout = {
  boxes: PlacedBox[];
  edges: PlacedEdge[];
  width: number;
  height: number;
};

type LocalLayout = MindLayout & { root: PlacedBox };

export const MINDMAP_FONT = 12;
export const WIDE_PANE = 560;
const MAX_LABEL_CHARS = 20;
const CHAR_W = 7.2;
const LINE_H = 16;
const PAD_X = 12;
const PAD_Y = 8;
const H_GAP = 28;
const V_GAP = 12;
const ROW_GAP = 18;
const CANVAS_PAD = 20;
const NODE_MIN_W = 48;
const NODE_MAX_W = 168;
const MAX_PER_COLUMN = 5;
const MIN_CHILD_BUDGET = 80;

const NODE_TOKEN =
  /root\(\([^)]*\)\)|[^\s(]+\(\([^)]*\)\)|[^\s(]+\([^)]*\)|[^\s[]+\[[^\]]*\]|"[^"]+"|[^\s]+/g;

export function normalizeMermaid(source: string): string {
  let text = (source || "").trim();
  if (!text) return "";
  if (!text.includes("\n") && text.includes("\\n")) text = text.replace(/\\n/g, "\n");
  text = text.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  let lines = text.split("\n").map((line) => line.replace(/\s+$/, "")).filter((line) => line.trim());
  if (lines.length === 1) lines = splitOneline(lines[0]);
  if (lines[0]?.trim().toLowerCase() === "mindmap") lines = lines.slice(1);
  return ["mindmap", ...uniqueNodes(indentBody(lines))].join("\n");
}

function splitOneline(line: string): string[] {
  let text = line.trim();
  if (text.toLowerCase().startsWith("mindmap")) text = text.slice(7).trim();
  const tokens = text.match(NODE_TOKEN)?.filter((token) => token.toLowerCase() !== "mindmap") || [];
  return tokens.length > 1 ? tokens : [line];
}

function indentBody(lines: string[]): string[] {
  const raw = lines
    .filter((line) => line.trim())
    .map((line) => {
      const expanded = line.replace(/\t/g, "    ");
      return { indent: expanded.length - expanded.trimStart().length, label: expanded.trim() };
    });
  if (raw.length === 0) return ["  root((Mindmap))"];
  if (Math.max(...raw.map((item) => item.indent)) === 0) {
    return [`  ${raw[0].label}`, ...raw.slice(1).map((item) => `    ${item.label}`)];
  }
  const base = Math.min(...raw.map((item) => item.indent));
  return raw.map((item) => `  ${" ".repeat(item.indent - base)}${item.label}`);
}

function safeLabel(label: string): string {
  return label
    .replace(/^[-+*•–—]\s*/, "")
    .replace(/[\[\](){}]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 72);
}

function uniqueNodes(lines: string[]): string[] {
  const out: string[] = [];
  lines.forEach((line, index) => {
    const pad = " ".repeat(line.length - line.trimStart().length);
    const label = safeLabel(nodeLabel(line.trim()));
    if (!label) return;
    if (index === 0) {
      out.push(`${pad}root((${label}))`);
      return;
    }
    if (label.includes(" ")) out.push(`${pad}n${index}[${label}]`);
    else out.push(`${pad}n${index}(${label})`);
  });
  return out.length ? out : ["  root((Mindmap))"];
}

export function nodeLabel(raw: string): string {
  const text = raw.replace(/::icon\([^)]*\)/g, "").trim();
  const named = text.match(/^[^\s(]+(?:\(\((.*)\)\)|\((.*)\)|\[(.*)\])$/);
  if (named) return (named[1] || named[2] || named[3] || text).trim();
  const shaped = text.match(/^(?:root)?(?:\(\((.*)\)\)|\((.*)\)|\[(.*)\]|"(.*)")$/);
  if (shaped) return (shaped[1] || shaped[2] || shaped[3] || shaped[4] || text).trim();
  return text;
}

export function parseTree(source: string): MindNode {
  const stack: { indent: number; node: MindNode }[] = [];
  let root: MindNode | null = null;
  for (const line of source.split("\n")) {
    if (!line.trim() || line.trim().toLowerCase() === "mindmap") continue;
    const indent = line.length - line.trimStart().length;
    const node: MindNode = { label: nodeLabel(line.trim()), children: [] };
    if (!root) {
      root = node;
      stack.push({ indent, node });
      continue;
    }
    while (stack.length && stack[stack.length - 1].indent >= indent) stack.pop();
    const parent = stack.length ? stack[stack.length - 1].node : root;
    parent.children.push(node);
    stack.push({ indent, node });
  }
  return root ?? { label: "Mindmap", children: [] };
}

export function wrapLabel(label: string, maxChars = MAX_LABEL_CHARS): string[] {
  const words = (label || "").split(/\s+/).filter(Boolean);
  if (!words.length) return [""];
  const lines: string[] = [];
  let current = "";
  for (const word of words) {
    const chunks = word.length > maxChars ? chunkWord(word, maxChars) : [word];
    for (const chunk of chunks) {
      const trial = current ? `${current} ${chunk}` : chunk;
      if (trial.length <= maxChars) current = trial;
      else {
        if (current) lines.push(current);
        current = chunk;
      }
    }
  }
  if (current) lines.push(current);
  return lines.slice(0, 4);
}

function chunkWord(word: string, maxChars: number): string[] {
  const out: string[] = [];
  for (let i = 0; i < word.length; i += maxChars) out.push(word.slice(i, i + maxChars));
  return out;
}

export function measureLabel(label: string): { w: number; h: number; lines: string[] } {
  const lines = wrapLabel(label);
  const longest = Math.max(...lines.map((line) => line.length), 1);
  const w = Math.min(NODE_MAX_W, Math.max(NODE_MIN_W, Math.round(longest * CHAR_W + PAD_X * 2)));
  const h = lines.length * LINE_H + PAD_Y * 2;
  return { w, h, lines };
}

function subtreeWeight(node: MindNode): number {
  if (!node.children.length) return 1;
  return node.children.reduce((sum, child) => sum + subtreeWeight(child), 1);
}

export function splitSides(children: MindNode[]): { left: MindNode[]; right: MindNode[] } {
  const order = new Map(children.map((child, index) => [child, index]));
  const ranked = [...children].sort((a, b) => {
    const diff = subtreeWeight(b) - subtreeWeight(a);
    if (diff !== 0) return diff;
    return (order.get(a) || 0) - (order.get(b) || 0);
  });
  const left: MindNode[] = [];
  const right: MindNode[] = [];
  let leftW = 0;
  let rightW = 0;
  ranked.forEach((child) => {
    const weight = subtreeWeight(child);
    if (rightW <= leftW) {
      right.push(child);
      rightW += weight;
    } else {
      left.push(child);
      leftW += weight;
    }
  });
  left.sort((a, b) => (order.get(a) || 0) - (order.get(b) || 0));
  right.sort((a, b) => (order.get(a) || 0) - (order.get(b) || 0));
  return { left, right };
}

function nextIdFactory() {
  let n = 0;
  return () => {
    n += 1;
    return n;
  };
}

function shift(local: LocalLayout, dx: number, dy: number): LocalLayout {
  return {
    boxes: local.boxes.map((box) => ({ ...box, x: box.x + dx, y: box.y + dy })),
    edges: local.edges.map((edge) => ({
      x1: edge.x1 + dx,
      y1: edge.y1 + dy,
      x2: edge.x2 + dx,
      y2: edge.y2 + dy,
      toward: edge.toward,
    })),
    width: local.width,
    height: local.height,
    root: { ...local.root, x: local.root.x + dx, y: local.root.y + dy },
  };
}

function mirrorX(local: LocalLayout): LocalLayout {
  const flipped: LocalLayout = {
    boxes: local.boxes.map((box) => ({ ...box, x: -box.x - box.w })),
    edges: local.edges.map((edge) => ({
      x1: -edge.x1,
      y1: edge.y1,
      x2: -edge.x2,
      y2: edge.y2,
      toward: edge.toward === "left" ? "right" : edge.toward === "right" ? "left" : edge.toward,
    })),
    width: local.width,
    height: local.height,
    root: { ...local.root, x: -local.root.x - local.root.w },
  };
  const minX = Math.min(...flipped.boxes.map((box) => box.x), flipped.root.x);
  return shift(flipped, -minX, 0);
}

function connect(parent: PlacedBox, child: PlacedBox, toward: EdgeToward): PlacedEdge {
  if (toward === "down") {
    return {
      x1: parent.x + parent.w / 2,
      y1: parent.y + parent.h,
      x2: child.x + child.w / 2,
      y2: child.y,
      toward,
    };
  }
  if (toward === "left") {
    return {
      x1: parent.x,
      y1: parent.y + parent.h / 2,
      x2: child.x + child.w,
      y2: child.y + child.h / 2,
      toward,
    };
  }
  return {
    x1: parent.x + parent.w,
    y1: parent.y + parent.h / 2,
    x2: child.x,
    y2: child.y + child.h / 2,
    toward,
  };
}

function remapLayouts(layouts: LocalLayout[], packed: LocalLayout): LocalLayout[] {
  return layouts.map((child) => {
    const found = packed.boxes.find((box) => box.id === child.root.id);
    const dx = found ? found.x - child.root.x : 0;
    const dy = found ? found.y - child.root.y : 0;
    return shift(child, dx, dy);
  });
}

function mergeParts(parts: LocalLayout[]): { boxes: PlacedBox[]; edges: PlacedEdge[] } {
  return {
    boxes: parts.flatMap((part) => part.boxes),
    edges: parts.flatMap((part) => part.edges),
  };
}

function stackVertical(layouts: LocalLayout[]): LocalLayout {
  if (!layouts.length) {
    const empty = { id: 0, label: "", lines: [""], x: 0, y: 0, w: 0, h: 0, depth: 0 };
    return { boxes: [], edges: [], width: 0, height: 0, root: empty };
  }
  let y = 0;
  let width = 0;
  const placed = layouts.map((layout) => {
    const next = shift(layout, 0, y);
    y += layout.height + ROW_GAP;
    width = Math.max(width, layout.width);
    return next;
  });
  const merged = mergeParts(placed);
  return {
    ...merged,
    width,
    height: y - ROW_GAP,
    root: placed[0].root,
  };
}

function packColumns(layouts: LocalLayout[], budget: number): LocalLayout {
  const colW = Math.max(...layouts.map((item) => item.width), NODE_MIN_W);
  const nFitNatural = Math.max(1, Math.floor((budget + H_GAP) / (colW + H_GAP)));
  const nFitMin = Math.max(1, Math.floor((budget + H_GAP) / (NODE_MIN_W + H_GAP)));
  const desired = Math.max(1, Math.ceil(layouts.length / MAX_PER_COLUMN));
  const nCols = Math.min(layouts.length, nFitMin, Math.max(desired, nFitNatural));
  const perCol = Math.ceil(layouts.length / nCols);
  const colHeights = Array.from({ length: nCols }, () => 0);
  const placed = layouts.map((layout, index) => {
    const col = Math.min(nCols - 1, Math.floor(index / perCol));
    const x = col * (colW + H_GAP);
    const y = colHeights[col];
    colHeights[col] += layout.height + V_GAP;
    return shift(layout, x, y);
  });
  const merged = mergeParts(placed);
  return {
    ...merged,
    width: (nCols - 1) * (colW + H_GAP) + colW,
    height: Math.max(...colHeights, V_GAP) - V_GAP,
    root: placed[0].root,
  };
}

function packRows(layouts: LocalLayout[], budget: number): LocalLayout {
  let x = 0;
  let y = 0;
  let rowH = 0;
  let width = 0;
  const placed: LocalLayout[] = [];
  layouts.forEach((layout) => {
    if (x > 0 && x + layout.width > budget) {
      y += rowH + ROW_GAP;
      x = 0;
      rowH = 0;
    }
    placed.push(shift(layout, x, y));
    x += layout.width + H_GAP;
    rowH = Math.max(rowH, layout.height);
    width = Math.max(width, x - H_GAP);
  });
  const merged = mergeParts(placed);
  return {
    ...merged,
    width,
    height: y + rowH,
    root: placed[0]?.root || layouts[0].root,
  };
}

function packChildren(layouts: LocalLayout[], budget: number): LocalLayout {
  if (!layouts.length) {
    const empty = { id: 0, label: "", lines: [""], x: 0, y: 0, w: 0, h: 0, depth: 0 };
    return { boxes: [], edges: [], width: 0, height: 0, root: empty };
  }
  const allLeaves = layouts.every((item) => item.boxes.length === 1);
  if (allLeaves && layouts.length > 3) return packColumns(layouts, budget);
  if (allLeaves) return stackVertical(layouts);
  return packRows(layouts, budget);
}

function layoutNode(node: MindNode, maxWidth: number, depth: number, nextId: () => number): LocalLayout {
  const size = measureLabel(node.label);
  const self: PlacedBox = {
    id: nextId(),
    label: node.label,
    lines: size.lines,
    x: 0,
    y: 0,
    w: size.w,
    h: size.h,
    depth,
  };
  if (!node.children.length) {
    return { boxes: [self], edges: [], width: size.w, height: size.h, root: self };
  }
  const widthBudget = Math.max(maxWidth, size.w);
  const besideBudget = widthBudget - size.w - H_GAP;
  const leafKids = node.children.every((child) => child.children.length === 0);
  const manyLeaves = leafKids && node.children.length > 4;
  const beside = !manyLeaves;
  const budget = beside ? Math.max(MIN_CHILD_BUDGET, besideBudget) : Math.max(MIN_CHILD_BUDGET, widthBudget - 16);
  const childLayouts = node.children.map((child) => layoutNode(child, budget, depth + 1, nextId));
  const packed = packChildren(childLayouts, budget);
  const placedChildren = remapLayouts(childLayouts, packed);
  let rootX = 0;
  let rootY = 0;
  let childrenX = 0;
  let childrenY = 0;
  if (beside) {
    childrenX = size.w + H_GAP;
    if (packed.height > size.h) rootY = (packed.height - size.h) / 2;
    else childrenY = (size.h - packed.height) / 2;
  } else {
    childrenX = 12;
    childrenY = size.h + V_GAP;
  }
  const kids = placedChildren.map((child) => shift(child, childrenX, childrenY));
  self.x = rootX;
  self.y = rootY;
  const merged = mergeParts(kids);
  const toward = beside ? "right" : "down";
  const edges = [...merged.edges, ...kids.map((child) => connect(self, child.root, toward))];
  const width = beside
    ? childrenX + packed.width
    : Math.max(size.w, childrenX + packed.width);
  const height = Math.max(rootY + size.h, childrenY + packed.height);
  return { boxes: [self, ...merged.boxes], edges, width, height, root: self };
}

function finish(local: LocalLayout): MindLayout {
  const minX = Math.min(...local.boxes.map((box) => box.x), 0);
  const minY = Math.min(...local.boxes.map((box) => box.y), 0);
  const shifted = shift(local, CANVAS_PAD - minX, CANVAS_PAD - minY);
  const maxX = Math.max(...shifted.boxes.map((box) => box.x + box.w), CANVAS_PAD);
  const maxY = Math.max(...shifted.boxes.map((box) => box.y + box.h), CANVAS_PAD);
  return {
    boxes: shifted.boxes,
    edges: shifted.edges,
    width: Math.ceil(maxX + CANVAS_PAD),
    height: Math.ceil(maxY + CANVAS_PAD),
  };
}

function layoutStackedBranches(root: MindNode, targetWidth: number, nextId: () => number): MindLayout {
  const size = measureLabel(root.label);
  const inner = Math.max(NODE_MIN_W, targetWidth - CANVAS_PAD * 2);
  const childBudget = Math.max(MIN_CHILD_BUDGET, inner - size.w - H_GAP);
  const simple = root.children.every(
    (child) => child.children.length <= MAX_PER_COLUMN && child.children.every((grand) => grand.children.length === 0),
  );
  const childLayouts = root.children.map((child) => layoutNode(child, childBudget, 1, nextId));
  const packed =
    simple && root.children.length >= 4 ? packChildren(childLayouts, childBudget) : stackVertical(childLayouts);
  const rootY = CANVAS_PAD + Math.max(0, (packed.height - size.h) / 2);
  const kidsY = CANVAS_PAD + Math.max(0, (size.h - packed.height) / 2);
  const rootBox: PlacedBox = {
    id: nextId(),
    label: root.label,
    lines: size.lines,
    x: CANVAS_PAD,
    y: rootY,
    w: size.w,
    h: size.h,
    depth: 0,
  };
  const kids = remapLayouts(childLayouts, shift(packed, CANVAS_PAD + size.w + H_GAP, kidsY));
  const merged = mergeParts(kids);
  return finish({
    boxes: [rootBox, ...merged.boxes],
    edges: [...merged.edges, ...kids.map((child) => connect(rootBox, child.root, "right"))],
    width: CANVAS_PAD + size.w + H_GAP + packed.width + CANVAS_PAD,
    height: CANVAS_PAD * 2 + Math.max(size.h, packed.height),
    root: rootBox,
  });
}

function layoutBalanced(root: MindNode, targetWidth: number, nextId: () => number): MindLayout {
  const size = measureLabel(root.label);
  const { left, right } = splitSides(root.children);
  const sideBudget = Math.max(MIN_CHILD_BUDGET, (targetWidth - size.w - H_GAP * 2 - CANVAS_PAD * 2) / 2);
  const leftLayouts = left.map((child) => mirrorX(layoutNode(child, sideBudget, 1, nextId)));
  const rightLayouts = right.map((child) => layoutNode(child, sideBudget, 1, nextId));
  const leftPack = stackVertical(leftLayouts);
  const rightPack = stackVertical(rightLayouts);
  const midH = Math.max(size.h, leftPack.height, rightPack.height);
  const rootBox: PlacedBox = {
    id: nextId(),
    label: root.label,
    lines: size.lines,
    x: CANVAS_PAD + leftPack.width + H_GAP,
    y: CANVAS_PAD + (midH - size.h) / 2,
    w: size.w,
    h: size.h,
    depth: 0,
  };
  const leftPlaced = shift(leftPack, CANVAS_PAD, CANVAS_PAD + (midH - leftPack.height) / 2);
  const rightPlaced = shift(rightPack, rootBox.x + size.w + H_GAP, CANVAS_PAD + (midH - rightPack.height) / 2);
  const leftKids = remapLayouts(leftLayouts, leftPlaced);
  const rightKids = remapLayouts(rightLayouts, rightPlaced);
  const merged = mergeParts([...leftKids, ...rightKids]);
  return finish({
    boxes: [rootBox, ...merged.boxes],
    edges: [
      ...merged.edges,
      ...leftKids.map((child) => connect(rootBox, child.root, "left")),
      ...rightKids.map((child) => connect(rootBox, child.root, "right")),
    ],
    width: rootBox.x + size.w + H_GAP + rightPack.width + CANVAS_PAD,
    height: CANVAS_PAD * 2 + midH,
    root: rootBox,
  });
}

export function layoutMindmap(
  root: MindNode,
  targetWidth: number,
  options?: { balanced?: boolean },
): MindLayout {
  const nextId = nextIdFactory();
  const width = Math.max(240, Math.round(targetWidth));
  if (!root.children.length) {
    const size = measureLabel(root.label);
    const box: PlacedBox = {
      id: nextId(),
      label: root.label,
      lines: size.lines,
      x: CANVAS_PAD,
      y: CANVAS_PAD,
      w: size.w,
      h: size.h,
      depth: 0,
    };
    return { boxes: [box], edges: [], width: size.w + CANVAS_PAD * 2, height: size.h + CANVAS_PAD * 2 };
  }
  const useBalanced = options?.balanced ?? (root.children.length >= 2 && width >= WIDE_PANE);
  if (useBalanced) {
    return layoutBalanced(root, width, nextId);
  }
  return layoutStackedBranches(root, width, nextId);
}

function roundedElbow(x1: number, y1: number, midX: number, y2: number, x2: number): string {
  const radius = 8;
  const v = Math.abs(y2 - y1);
  const h1 = Math.abs(midX - x1);
  const h2 = Math.abs(x2 - midX);
  if (v < radius * 2 || h1 < radius || h2 < radius) {
    return `M ${x1} ${y1} H ${midX} V ${y2} H ${x2}`;
  }
  const sy = y2 >= y1 ? 1 : -1;
  const sxIn = midX >= x1 ? 1 : -1;
  const sxOut = x2 >= midX ? 1 : -1;
  return [
    `M ${x1} ${y1}`,
    `H ${midX - sxIn * radius}`,
    `Q ${midX} ${y1} ${midX} ${y1 + sy * radius}`,
    `V ${y2 - sy * radius}`,
    `Q ${midX} ${y2} ${midX + sxOut * radius} ${y2}`,
    `H ${x2}`,
  ].join(" ");
}

function roundedDown(x1: number, y1: number, midY: number, x2: number, y2: number): string {
  const radius = 8;
  const h = Math.abs(x2 - x1);
  const v1 = Math.abs(midY - y1);
  const v2 = Math.abs(y2 - midY);
  if (h < radius * 2 || v1 < radius || v2 < radius) {
    return `M ${x1} ${y1} V ${midY} H ${x2} V ${y2}`;
  }
  const sx = x2 >= x1 ? 1 : -1;
  const syIn = midY >= y1 ? 1 : -1;
  const syOut = y2 >= midY ? 1 : -1;
  return [
    `M ${x1} ${y1}`,
    `V ${midY - syIn * radius}`,
    `Q ${x1} ${midY} ${x1 + sx * radius} ${midY}`,
    `H ${x2 - sx * radius}`,
    `Q ${x2} ${midY} ${x2} ${midY + syOut * radius}`,
    `V ${y2}`,
  ].join(" ");
}

export function edgePath(edge: PlacedEdge): string {
  if (edge.toward === "down") {
    const midY = edge.y1 + Math.max(12, (edge.y2 - edge.y1) / 2);
    return roundedDown(edge.x1, edge.y1, midY, edge.x2, edge.y2);
  }
  const dir = edge.toward === "left" ? -1 : 1;
  const midX = edge.x1 + dir * Math.max(14, Math.abs(edge.x2 - edge.x1) / 2);
  return roundedElbow(edge.x1, edge.y1, midX, edge.y2, edge.x2);
}
