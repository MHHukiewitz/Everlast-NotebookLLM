"use client";

import { StudioCiteLinks, type StudioCiteProps } from "@/components/CiteText";
import { MarkdownBody } from "@/components/MarkdownBody";

export function ReportView({
  body,
  citations,
  onCite,
}: { body: string } & StudioCiteProps) {
  return (
    <div className="prose-studio text-xs text-neutral-700">
      <MarkdownBody citations={citations} onCite={onCite}>
        {body}
      </MarkdownBody>
      <StudioCiteLinks text={body} citations={citations} onCite={onCite} fallback="sources" />
    </div>
  );
}
