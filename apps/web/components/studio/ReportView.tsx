"use client";

import { MarkdownBody } from "@/components/MarkdownBody";

export function ReportView({ body }: { body: string }) {
  return (
    <div className="prose-studio text-xs text-neutral-700">
      <MarkdownBody>{body}</MarkdownBody>
    </div>
  );
}
