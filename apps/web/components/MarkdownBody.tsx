"use client";

import ReactMarkdown from "react-markdown";
import { normalizeMarkdown } from "@/lib/markdown";

export function MarkdownBody({ children }: { children: string }) {
  return (
    <div className="md-body">
      <ReactMarkdown>{normalizeMarkdown(children)}</ReactMarkdown>
    </div>
  );
}
