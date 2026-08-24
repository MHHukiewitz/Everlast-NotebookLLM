import assert from "node:assert/strict";
import {
  layoutMindmap,
  normalizeMermaid,
  parseTree,
  splitSides,
  WIDE_PANE,
  type MindNode,
} from "./mindmapLayout";

function leaf(label: string): MindNode {
  return { label, children: [] };
}

function branch(label: string, count: number): MindNode {
  return {
    label,
    children: Array.from({ length: count }, (_, index) => leaf(`${label}-${index + 1}`)),
  };
}

const skills: MindNode = {
  label: "Mike Hukiewitz Skills",
  children: [
    branch("Skills", 8),
    branch("Interests", 17),
    branch("Languages", 3),
    branch("Work", 5),
  ],
};

const narrow = layoutMindmap(skills, 440);
const interests = narrow.boxes.filter((box) => box.label.startsWith("Interests-"));
assert.equal(interests.length, 17);
assert.ok(narrow.width <= 520, `narrow width ${narrow.width}`);
assert.ok(narrow.width >= 300, `narrow width ${narrow.width} should use the pane`);
const interestXs = new Set(interests.map((box) => Math.round(box.x / 12)));
assert.ok(interestXs.size >= 3, "long sibling lists must wrap into several columns");
const interestSpan = Math.max(...interests.map((box) => box.y + box.h)) - Math.min(...interests.map((box) => box.y));
assert.ok(interestSpan < 8 * 36, `interests column span ${interestSpan} should wrap`);
assert.ok(narrow.height < 700, `narrow height ${narrow.height} should stay compact`);

const wide = layoutMindmap(skills, WIDE_PANE + 80);
const root = wide.boxes.find((box) => box.depth === 0);
assert.ok(root);
const leftBoxes = wide.boxes.filter((box) => box.depth > 0 && box.x + box.w <= root.x);
const rightBoxes = wide.boxes.filter((box) => box.depth > 0 && box.x >= root.x + root.w);
assert.ok(leftBoxes.length > 0, "wide layout must place branches left of the root");
assert.ok(rightBoxes.length > 0, "wide layout must place branches right of the root");

const sides = splitSides(skills.children);
assert.ok(sides.left.length >= 1);
assert.ok(sides.right.length >= 1);
assert.equal(sides.left.length + sides.right.length, 4);

const source = normalizeMermaid("mindmap\n  root((Ingest))\n    PDF\n      Text");
assert.equal(source.split("\n")[0], "mindmap");
const tree = parseTree(source);
assert.equal(tree.label, "Ingest");
assert.equal(tree.children[0].label, "PDF");
assert.equal(tree.children[0].children[0].label, "Text");

const layers: MindNode = {
  label: "Architektur",
  children: Array.from({ length: 6 }, (_, index) => branch(`Schicht ${index + 1}`, 2)),
};
const compact = layoutMindmap(layers, 440);
assert.ok(compact.height < 360, `short branches should share rows, height ${compact.height}`);
const layerParents = compact.boxes.filter((box) => box.label.startsWith("Schicht"));
const layerXs = new Set(layerParents.map((box) => Math.round(box.x / 40)));
assert.ok(layerXs.size >= 2, "several short branches should sit in more than one column");

const lonely = layoutMindmap(leaf("Solo"), 400);
assert.equal(lonely.boxes.length, 1);
assert.equal(lonely.edges.length, 0);

const brokenIndent = parseTree(normalizeMermaid(`mindmap
  root((KI-generiert Angebotspalette))
    n1[- Zertifizierung und Prüfung]
      n2[+ Offizielles Zertifikat]
    n3[- KI-Integration und -Implementierung]
      n4[+ Produktive Integration]
  n9[- Referenzen und Erfolgsgeschichten]
    n10[+ Dokumentierte Kundenprojekte]
  n11[- KI-Beratung und -Lösungen]
    n12[+ Persönliche Vor-Ort-Unterstützung]
`));
assert.equal(brokenIndent.label, "KI-generiert Angebotspalette");
const brokenLabels = brokenIndent.children.map((child) => child.label);
assert.ok(brokenLabels.includes("Zertifizierung und Prüfung"));
assert.ok(brokenLabels.includes("Referenzen und Erfolgsgeschichten"));
assert.ok(brokenLabels.includes("KI-Beratung und -Lösungen"));
assert.ok(brokenIndent.children.length >= 4);
