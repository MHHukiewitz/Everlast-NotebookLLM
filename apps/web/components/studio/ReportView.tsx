"use client";

import ReactMarkdown from "react-markdown";

export function ReportView({ body }: { body: string }) {
  return (
    <div className="prose-studio text-xs text-neutral-700">
      <ReactMarkdown>{body}</ReactMarkdown>
    </div>
  );
}
