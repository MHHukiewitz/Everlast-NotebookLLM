export function normalizeMarkdown(text: string): string {
  if (!text) return "";
  let out = text.replace(/\r\n/g, "\n");
  if (!out.includes("\n") && out.includes("\\n")) {
    out = out.replace(/\\n/g, "\n");
  }
  out = unwrapOuterFence(out.trim());
  out = dedentIndentedDocument(out);
  return out.trim();
}

const GROUPED_CITE = /\[(\d+(?:\s*,\s*\d+)+)\]/g;
const GROUPED_PROTECTED = /⟦(\d+(?:\s*,\s*\d+)+)⟧/g;

export function unwrapCiteMarkdownLinks(text: string): string {
  return (text || "")
    .replace(/\[⟦(\d+)⟧\]\([^)\n]+\)/g, "[$1]")
    .replace(/\[\[(\d+)\]\]\([^)\n]+\)/g, "[$1]")
    .replace(/⟦(\d+)⟧\([^)\n]+\)/g, "[$1]");
}

export function expandGroupedCiteMarks(text: string): string {
  const expand = (nums: string, wrap: (n: string) => string) =>
    nums
      .split(/\s*,\s*/)
      .filter(Boolean)
      .map(wrap)
      .join("");
  return (text || "")
    .replace(GROUPED_CITE, (_all, nums: string) => expand(nums, (n) => `[${n}]`))
    .replace(GROUPED_PROTECTED, (_all, nums: string) => expand(nums, (n) => `⟦${n}⟧`));
}

export function protectCiteMarks(text: string): string {
  return expandGroupedCiteMarks(unwrapCiteMarkdownLinks(text || "")).replace(/\[(\d+)\]/g, "⟦$1⟧");
}

function unwrapOuterFence(text: string): string {
  const lines = text.split("\n");
  const first = lines[0]?.trim() ?? "";
  if (!first.startsWith("```")) {
    return text;
  }
  let close = -1;
  for (let i = lines.length - 1; i >= 1; i -= 1) {
    if (lines[i].trim().startsWith("```")) {
      close = i;
      break;
    }
  }
  if (close < 1) {
    return text;
  }
  const inner = lines.slice(1, close).join("\n").trim();
  const after = lines.slice(close + 1).join("\n").trim();
  return after ? `${inner}\n\n${after}` : inner;
}

function dedentIndentedDocument(text: string): string {
  const lines = text.split("\n");
  const indents = lines.filter((line) => line.trim()).map((line) => line.match(/^ */)?.[0].length ?? 0);
  const min = indents.length ? Math.min(...indents) : 0;
  if (min < 4) {
    return text;
  }
  return lines.map((line) => line.slice(min)).join("\n");
}
