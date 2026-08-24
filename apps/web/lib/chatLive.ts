export type ToolCallView = {
  call_id: string;
  skill_id: string;
  name: string;
  arguments: string;
  result?: unknown;
  status: "waiting" | "running" | "done";
};

export type LivePart =
  | { kind: "text"; id: string; text: string }
  | { kind: "tool"; id: string; tool: ToolCallView };

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
  return parts;
}

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

export function visibleChatText(text: string): string {
  if (!text) return "";
  let out = "";
  let index = 0;
  const startRe = /\{\s*"name"\s*:/;
  while (index < text.length) {
    const rest = text.slice(index);
    const match = rest.search(startRe);
    if (match < 0) {
      out += rest;
      break;
    }
    out += rest.slice(0, match);
    const abs = index + match;
    const blob = takeJsonObject(text, abs);
    if (!blob) {
      out += text.slice(abs);
      break;
    }
    index = abs + blob.length;
  }
  return out.replace(/\n{3,}/g, "\n\n").trim();
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
