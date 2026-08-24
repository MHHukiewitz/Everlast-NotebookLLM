"use client";

import ReactMarkdown from "react-markdown";
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
  return (
    <div className="md-body">
      <ReactMarkdown
        components={
          enable
            ? {
                p: ({ children: body }) => <p>{injectCites(body, citations || [], onCite!)}</p>,
                li: ({ children: body }) => <li>{injectCites(body, citations || [], onCite!)}</li>,
                td: ({ children: body }) => <td>{injectCites(body, citations || [], onCite!)}</td>,
                th: ({ children: body }) => <th>{injectCites(body, citations || [], onCite!)}</th>,
                h1: ({ children: body }) => <h1>{injectCites(body, citations || [], onCite!)}</h1>,
                h2: ({ children: body }) => <h2>{injectCites(body, citations || [], onCite!)}</h2>,
                h3: ({ children: body }) => <h3>{injectCites(body, citations || [], onCite!)}</h3>,
                blockquote: ({ children: body }) => (
                  <blockquote>{injectCites(body, citations || [], onCite!)}</blockquote>
                ),
              }
            : undefined
        }
      >
        {protectCiteMarks(normalizeMarkdown(children))}
      </ReactMarkdown>
    </div>
  );
}
