"use client";

import type { ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { injectCites } from "@/components/CiteText";
import { normalizeMarkdown, protectCiteMarks } from "@/lib/markdown";
import type { MessageCitation } from "@/lib/types";

export function MarkdownBody({
  children,
  citations,
  onCite,
}: {
  children: string;
  citations?: MessageCitation[];
  onCite?: (cite: MessageCitation) => void;
}) {
  const enable = Boolean(citations?.length && onCite);

  function withCites(body: ReactNode): ReactNode {
    return enable ? injectCites(body, citations || [], onCite!) : body;
  }

  return (
    <div className="md-body">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          table: ({ children: body }) => (
            <div className="md-table-wrap">
              <table>{body}</table>
            </div>
          ),
          p: ({ children: body }) => <p>{withCites(body)}</p>,
          li: ({ children: body }) => <li>{withCites(body)}</li>,
          td: ({ children: body, style }) => <td style={style}>{withCites(body)}</td>,
          th: ({ children: body, style }) => <th style={style}>{withCites(body)}</th>,
          h1: ({ children: body }) => <h1>{withCites(body)}</h1>,
          h2: ({ children: body }) => <h2>{withCites(body)}</h2>,
          h3: ({ children: body }) => <h3>{withCites(body)}</h3>,
          blockquote: ({ children: body }) => <blockquote>{withCites(body)}</blockquote>,
        }}
      >
        {protectCiteMarks(normalizeMarkdown(children))}
      </ReactMarkdown>
    </div>
  );
}
