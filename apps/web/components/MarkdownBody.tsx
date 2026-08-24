"use client";

import { cloneElement, Fragment, isValidElement, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import { normalizeMarkdown } from "@/lib/markdown";
import type { MessageCitation } from "@/lib/types";

function replaceCiteMarks(
  text: string,
  citations: MessageCitation[],
  onCite: (cite: MessageCitation) => void,
): ReactNode {
  const parts = text.split(/(\[\d+\])/g);
  if (parts.length === 1) return text;
  return parts.map((part, index) => {
    const match = part.match(/^\[(\d+)\]$/);
    if (!match) return part;
    const n = Number(match[1]);
    const cite = citations.find((item) => item.n === n);
    if (!cite) return part;
    return (
      <button
        key={`${n}-${index}`}
        type="button"
        className="rounded bg-blue-50 px-1.5 text-xs text-accent"
        title={cite.quote}
        onClick={() => onCite(cite)}
      >
        [{n}]
      </button>
    );
  });
}

function injectCites(
  node: ReactNode,
  citations: MessageCitation[],
  onCite: (cite: MessageCitation) => void,
): ReactNode {
  if (typeof node === "string" || typeof node === "number") {
    return replaceCiteMarks(String(node), citations, onCite);
  }
  if (Array.isArray(node)) {
    return node.map((child, index) => (
      <Fragment key={index}>{injectCites(child, citations, onCite)}</Fragment>
    ));
  }
  if (isValidElement<{ children?: ReactNode }>(node) && node.props.children != null) {
    if (node.type === "a") return node;
    return cloneElement(node, undefined, injectCites(node.props.children, citations, onCite));
  }
  return node;
}

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
        {normalizeMarkdown(children)}
      </ReactMarkdown>
    </div>
  );
}
