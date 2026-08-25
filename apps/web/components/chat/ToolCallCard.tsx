"use client";

import { t } from "@/lib/i18n";
import { toolArgumentPreview, type ToolCallView } from "@/lib/chatLive";

function formatResult(result: unknown): string {
  if (result == null) return "";
  if (typeof result === "string") return result;
  if (typeof result === "object" && result && "query" in result) {
    return String((result as { query?: unknown }).query || JSON.stringify(result, null, 2));
  }
  return JSON.stringify(result, null, 2);
}

export function ToolCallCard({ tool, featured = false }: { tool: ToolCallView; featured?: boolean }) {
  const title = tool.name || t.toolCalling;
  const waiting = tool.status !== "done";
  const preview = toolArgumentPreview(tool.arguments);
  return (
    <details
      className={`tool-call my-2 rounded-xl border text-left text-xs ${
        featured ? "border-accent bg-white" : "border-line bg-mist"
      }`}
      open={waiting || featured}
    >
      <summary className="cursor-pointer px-3 py-2 text-neutral-600">
        <span className="font-medium text-neutral-800">{title}</span>
        {waiting ? (
          <span className="ml-2 text-accent">{t.toolRunning}</span>
        ) : (
          <span className="ml-2 text-neutral-400">{t.toolDone}</span>
        )}
        {preview ? <span className="mt-1 block truncate text-neutral-700">{preview}</span> : null}
      </summary>
      <div className="space-y-2 border-t border-line px-3 py-2">
        <div>
          <p className="mb-1 text-[11px] uppercase tracking-wide text-neutral-400">{t.toolArgs}</p>
          <pre className="overflow-auto whitespace-pre-wrap text-[11px] text-neutral-700">{tool.arguments || "—"}</pre>
        </div>
        {tool.status === "done" && (
          <div>
            <p className="mb-1 text-[11px] uppercase tracking-wide text-neutral-400">{t.toolResult}</p>
            <pre className="overflow-auto whitespace-pre-wrap text-[11px] text-neutral-700">{formatResult(tool.result)}</pre>
          </div>
        )}
      </div>
    </details>
  );
}
