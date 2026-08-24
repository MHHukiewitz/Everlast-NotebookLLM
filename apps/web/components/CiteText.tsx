"use client";

import { cloneElement, Fragment, isValidElement, type ReactNode } from "react";
import { CitationChips } from "@/components/CitationChips";
import { usedCitations } from "@/lib/chatLive";
import { expandGroupedCiteMarks } from "@/lib/markdown";
import { uniqueSourceCitations } from "@/lib/studioCitations";
import type { MessageCitation } from "@/lib/types";

export function replaceCiteMarks(
  text: string,
  citations: MessageCitation[],
  onCite: (cite: MessageCitation) => void,
): ReactNode {
  const expanded = expandGroupedCiteMarks(text);
  const parts = expanded.split(/(⟦\d+⟧|\[\d+\])/g);
  if (parts.length === 1) return expanded;
  return parts.map((part, index) => {
    const match = part.match(/^(?:⟦(\d+)⟧|\[(\d+)\])$/);
    if (!match) return part;
    const n = Number(match[1] || match[2]);
    const cite = citations.find((item) => Number(item.n) === n);
    if (!cite) return `[${n}]`;
    return (
      <button
        key={`${n}-${index}`}
        type="button"
        className="rounded bg-blue-50 px-1.5 text-xs text-accent"
        title={cite.quote || cite.title || `[${n}]`}
        onClick={() => onCite(cite)}
      >
        [{n}]
      </button>
    );
  });
}

export function injectCites(
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
    if (node.type === "a") {
      const raw = node.props.children;
      const label = typeof raw === "string" || typeof raw === "number" ? String(raw) : "";
      const mark = label.match(/^(?:⟦(\d+)⟧|\[(\d+)\])$/);
      if (mark) return replaceCiteMarks(`[${mark[1] || mark[2]}]`, citations, onCite);
      return node;
    }
    return cloneElement(node, undefined, injectCites(node.props.children, citations, onCite));
  }
  return node;
}

export type StudioCiteProps = {
  citations?: MessageCitation[];
  onCite?: (cite: MessageCitation) => void;
};

export function CiteText({
  text,
  citations,
  onCite,
}: {
  text: string;
  citations?: MessageCitation[];
  onCite?: (cite: MessageCitation) => void;
}) {
  if (!text) return null;
  if (!citations?.length || !onCite) return <>{text}</>;
  return <>{replaceCiteMarks(text, citations, onCite)}</>;
}

export function StudioCiteLinks({
  text,
  citations,
  onCite,
  fallback = "none",
}: {
  text: string;
  citations?: MessageCitation[];
  onCite?: (cite: MessageCitation) => void;
  fallback?: "none" | "sources";
}) {
  if (!citations?.length || !onCite) return null;
  const used = usedCitations(text, citations);
  if (used.length) return <CitationChips citations={used} onCite={onCite} />;
  if (fallback !== "sources") return null;
  const unique = uniqueSourceCitations(citations);
  if (!unique.length) return null;
  return <CitationChips citations={unique} onCite={onCite} labels="title" />;
}
