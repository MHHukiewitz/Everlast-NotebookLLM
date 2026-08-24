export type ToolCallView = {
  call_id: string;
  skill_id: string;
  name: string;
  arguments: string;
  result?: unknown;
  status: "waiting" | "running" | "done";
};

export type StepKind = "analyze" | "retrieve" | "tool" | "write" | "research";

export type StepView = {
  id: string;
  title: string;
  detail: string;
  kind: StepKind;
  status: "running" | "done";
  call_id?: string;
};

export type LivePart =
  | { kind: "text"; id: string; text: string }
  | { kind: "tool"; id: string; tool: ToolCallView }
  | { kind: "step"; id: string; step: StepView }
  | { kind: "think"; id: string; text: string };

export function applyChatEvent(parts: LivePart[], event: Record<string, unknown>, nextId: () => string): LivePart[] {
  const type = String(event.event || "");
  if (type === "token") {
    const text = String(event.text || "");
    if (!text) return parts;
    const last = parts[parts.length - 1];
    if (last && last.kind === "text") {
      return [...parts.slice(0, -1), { ...last, text: last.text + text }];
    }
    return [...parts, { kind: "text", id: nextId(), text }];
  }
  if (type === "tool_start") {
    const callId = String(event.call_id || nextId());
    if (parts.some((part) => part.kind === "tool" && part.tool.call_id === callId)) {
      return parts;
    }
    return [
      ...parts,
      {
        kind: "tool",
        id: callId,
        tool: { call_id: callId, skill_id: "", name: "", arguments: "", status: "waiting" },
      },
    ];
  }
  if (type === "tool_name") {
    const callId = String(event.call_id || "");
    return parts.map((part) =>
      part.kind === "tool" && part.tool.call_id === callId
        ? {
            ...part,
            tool: {
              ...part.tool,
              skill_id: String(event.skill_id || ""),
              name: String(event.name || event.skill_id || ""),
              status: "running",
            },
          }
        : part,
    );
  }
  if (type === "tool_args") {
    const callId = String(event.call_id || "");
    const delta = String(event.delta || "");
    return parts.map((part) =>
      part.kind === "tool" && part.tool.call_id === callId
        ? { ...part, tool: { ...part.tool, arguments: part.tool.arguments + delta } }
        : part,
    );
  }
  if (type === "tool_result") {
    const callId = String(event.call_id || "");
    return parts.map((part) =>
      part.kind === "tool" && part.tool.call_id === callId
        ? { ...part, tool: { ...part.tool, result: event.result, status: "done" } }
        : part,
    );
  }
  if (type === "step") {
    const id = String(event.id || event.call_id || nextId());
    const step: StepView = {
      id,
      title: String(event.title || ""),
      detail: String(event.detail || ""),
      kind: (["analyze", "retrieve", "tool", "write", "research"].includes(String(event.kind))
        ? event.kind
        : "analyze") as StepKind,
      status: event.status === "running" ? "running" : "done",
      call_id: event.call_id ? String(event.call_id) : undefined,
    };
    if (parts.some((part) => part.kind === "step" && part.step.id === id)) {
      return parts.map((part) => (part.kind === "step" && part.step.id === id ? { ...part, step } : part));
    }
    return [...parts, { kind: "step", id, step }];
  }
  if (type === "think") {
    const text = String(event.text || "");
    if (!text) return parts;
    const last = parts[parts.length - 1];
    if (last && last.kind === "think") {
      return [...parts.slice(0, -1), { ...last, text: last.text + text }];
    }
    return [...parts, { kind: "think", id: nextId(), text }];
  }
  return parts;
}

const TOOL_OBJECT_START = /\{\s*"(?:name|tool|function|parameters)"\s*:/;
const DUMP_LINE = /^\s*(?:\[\d+\]\s*)+$/;

function takeJsonObject(text: string, start: number): string {
  if (text[start] !== "{") return "";
  let depth = 0;
  let inStr = false;
  let escape = false;
  for (let index = start; index < text.length; index += 1) {
    const char = text[index];
    if (inStr) {
      if (escape) escape = false;
      else if (char === "\\") escape = true;
      else if (char === '"') inStr = false;
      continue;
    }
    if (char === '"') inStr = true;
    else if (char === "{") depth += 1;
    else if (char === "}") {
      depth -= 1;
      if (depth === 0) return text.slice(start, index + 1);
    }
  }
  return "";
}

function isToolishPrefix(rest: string): boolean {
  if (/^\{\s*$/.test(rest)) return true;
  const match = rest.match(/^\{\s*"([A-Za-z_]*)"?\s*:?/);
  if (!match) return false;
  const key = match[1].toLowerCase();
  return ["name", "tool", "function", "parameters"].some((candidate) => candidate.startsWith(key));
}

function splitIncompleteTool(text: string): [string, string] {
  let holdAt: number | null = null;
  const consider = (pos: number) => {
    if (holdAt === null || pos < holdAt) holdAt = pos;
  };
  const toolCall = /<tool_call>/gi;
  let found: RegExpExecArray | null;
  while ((found = toolCall.exec(text))) {
    if (!/<\/tool_call>/i.test(text.slice(found.index + found[0].length))) {
      consider(found.index);
    }
  }
  const fences = /```(?:json)?[ \t]*\n/gi;
  while ((found = fences.exec(text))) {
    if (!text.slice(found.index + found[0].length).includes("```")) {
      consider(found.index);
    }
  }
  const fenceTail = text.search(/```(?:json)?\s*$/i);
  if (fenceTail >= 0) consider(fenceTail);
  const objectStart = /\{\s*"(?:name|tool|function|parameters)"\s*:/g;
  while ((found = objectStart.exec(text))) {
    if (!takeJsonObject(text, found.index)) consider(found.index);
  }
  const trimmed = text.replace(/\s+$/, "");
  if (trimmed.endsWith("{")) {
    consider(trimmed.length - 1);
  } else {
    for (let index = 0; index < text.length; index += 1) {
      if (text[index] !== "{") continue;
      if (takeJsonObject(text, index)) continue;
      if (isToolishPrefix(text.slice(index))) {
        consider(index);
        break;
      }
    }
  }
  if (holdAt === null) return [text, ""];
  return [text.slice(0, holdAt), text.slice(holdAt)];
}

export function visibleChatText(text: string): string {
  if (!text) return "";
  let out = "";
  let index = 0;
  while (index < text.length) {
    const rest = text.slice(index);
    const xml = rest.search(/<tool_call>/i);
    const fence = rest.search(/```(?:json)?[ \t]*\n/i);
    const object = rest.search(TOOL_OBJECT_START);
    const starts = [xml, fence, object].filter((pos) => pos >= 0);
    if (starts.length === 0) {
      out += rest;
      break;
    }
    const rel = Math.min(...starts);
    out += rest.slice(0, rel);
    const abs = index + rel;
    if (xml === rel) {
      const close = rest.slice(rel).match(/<\/tool_call>/i);
      if (!close || close.index == null) {
        out += text.slice(abs);
        break;
      }
      index = abs + close.index + close[0].length;
      continue;
    }
    if (fence === rel) {
      const openLen = rest.slice(rel).match(/```(?:json)?[ \t]*\n/i)?.[0].length || 0;
      const closeAt = text.indexOf("```", abs + openLen);
      if (closeAt < 0) {
        out += text.slice(abs);
        break;
      }
      const inner = text.slice(abs + openLen, closeAt);
      if (TOOL_OBJECT_START.test(inner)) {
        index = closeAt + 3;
        continue;
      }
      out += text.slice(abs, closeAt + 3);
      index = closeAt + 3;
      continue;
    }
    const blob = takeJsonObject(text, abs);
    if (!blob) {
      out += text.slice(abs);
      break;
    }
    index = abs + blob.length;
  }
  out = out.replace(/```(?:json)?\s*```/gi, "").replace(/<\/?tool_call>/gi, "");
  const [visible] = splitIncompleteTool(out);
  return visible.replace(/\n{3,}/g, "\n\n").trim();
}

export function citationMarks(text: string): number[] {
  return [...(text || "").matchAll(/\[(\d+)\]/g)].map((match) => Number(match[1]));
}

export function stripCitationDump(text: string): string {
  const kept = (text || "").split("\n").filter((line) => !DUMP_LINE.test(line));
  return kept.join("\n").replace(/\n{3,}/g, "\n\n").trim();
}

export function usedCitations<T extends { n: number }>(text: string, citations: T[] | undefined): T[] {
  if (!citations?.length) return [];
  const used = new Set(citationMarks(text));
  return citations.filter((item) => used.has(item.n));
}

export function displayChatText(text: string): string {
  return stripCitationDump(visibleChatText(text));
}

export function stepsFromReasoning(raw: unknown[] | undefined): StepView[] {
  return (raw || [])
    .map((item, index) => {
      if (typeof item === "string") {
        return {
          id: `saved_step_${index}`,
          title: item,
          detail: "",
          kind: "analyze" as StepKind,
          status: "done" as const,
        };
      }
      const rec = (item || {}) as Record<string, unknown>;
      const kind = String(rec.kind || "");
      return {
        id: String(rec.id || `saved_step_${index}`),
        title: String(rec.title || ""),
        detail: String(rec.detail || ""),
        kind: (["analyze", "retrieve", "tool", "write", "research"].includes(kind) ? kind : "analyze") as StepKind,
        status: "done" as const,
        call_id: rec.call_id ? String(rec.call_id) : undefined,
      };
    })
    .filter((step) => step.title);
}

export function reasoningLabel(item: unknown): string {
  if (typeof item === "string") return item;
  if (item && typeof item === "object" && "title" in item) {
    return String((item as { title: unknown }).title || "");
  }
  return "";
}

export function toolCallsFromMessage(raw: unknown[] | undefined): ToolCallView[] {
  return (raw || []).map((item, index) => {
    const rec = (item || {}) as Record<string, unknown>;
    const args = rec.arguments ?? rec.args ?? {};
    return {
      call_id: String(rec.call_id || `saved_${index}`),
      skill_id: String(rec.skill_id || ""),
      name: String(rec.skill_id || ""),
      arguments: typeof args === "string" ? args : JSON.stringify(args, null, 2),
      result: rec.result,
      status: rec.status === "waiting" || rec.status === "running" ? rec.status : "done",
    };
  });
}
