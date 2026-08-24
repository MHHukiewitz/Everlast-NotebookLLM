"use client";

import { ToolCallCard } from "@/components/chat/ToolCallCard";
import type { StepView, ToolCallView } from "@/lib/chatLive";
import { t } from "@/lib/i18n";

export function ThinkingTrace({
  steps,
  tools = [],
  think = "",
  busy = false,
}: {
  steps: StepView[];
  tools?: ToolCallView[];
  think?: string;
  busy?: boolean;
}) {
  if (steps.length === 0 && !think) {
    return null;
  }
  return (
    <div className="trace mb-3 text-left">
      <p className="trace-title">{busy ? t.traceBusy : t.thoughts}</p>
      <ol className="trace-list">
        {steps.map((step) => {
          const tool = step.call_id ? tools.find((item) => item.call_id === step.call_id) : undefined;
          return (
            <li key={step.id} className="trace-item">
              <span className={`trace-node${step.status === "running" ? " is-running" : ""}`} aria-hidden />
              <div className="min-w-0">
                <p className="font-medium text-neutral-700">{step.title}</p>
                {step.detail ? <p className="mt-0.5 text-xs text-neutral-500">{step.detail}</p> : null}
                {tool ? <ToolCallCard tool={tool} /> : null}
              </div>
            </li>
          );
        })}
      </ol>
      {think ? (
        <details className="trace-think" open={busy}>
          <summary>{t.traceThink}</summary>
          <p className="mt-1 whitespace-pre-wrap text-xs text-neutral-500">{think}</p>
        </details>
      ) : null}
    </div>
  );
}
