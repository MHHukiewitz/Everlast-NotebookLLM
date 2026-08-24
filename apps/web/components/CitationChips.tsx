"use client";

import type { MessageCitation } from "@/lib/types";

export function CitationChips({
  citations,
  onCite,
  labels = "marks",
}: {
  citations: MessageCitation[];
  onCite: (cite: MessageCitation) => void;
  labels?: "marks" | "title";
}) {
  if (!citations.length) return null;
  return (
    <div className="mt-2 flex flex-wrap gap-1">
      {citations.map((cite) => (
        <button
          key={`${cite.n}-${cite.chunk_id || cite.source_id || cite.url || cite.title}`}
          type="button"
          className="rounded bg-blue-50 px-1.5 text-xs text-accent"
          title={cite.quote || cite.title || `[${cite.n}]`}
          onClick={() => onCite(cite)}
        >
          {labels === "title" ? cite.title || cite.quote || `[${cite.n}]` : `[${cite.n}]`}
        </button>
      ))}
    </div>
  );
}
