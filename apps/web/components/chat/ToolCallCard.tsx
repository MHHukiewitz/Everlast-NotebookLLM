"use client";

import { t } from "@/lib/i18n";
import type { ToolCallView } from "@/lib/chatLive";

function formatResult(result: unknown): string {
  if (result == null) return "";
  if (typeof result === "string") return result;
  return JSON.stringify(result, null, 2);
}

export function ToolCallCard({ tool }: { tool: ToolCallView }) {
  const title = tool.name || t.toolCalling;
  const waiting = tool.status !== "done";
  return (
    <details className="tool-call my-2 rounded-xl border border-line bg-mist text-left text-xs">
      <summary className="cursor-pointer px-3 py-2 text-neutral-600">
        <span className="font-medium text-neutral-800">{title}</span>
        {waiting ? <span className="ml-2 text-neutral-400">{t.toolRunning}</span> : <span className="ml-2 text-neutral-400">{t.toolDone}</span>}
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
