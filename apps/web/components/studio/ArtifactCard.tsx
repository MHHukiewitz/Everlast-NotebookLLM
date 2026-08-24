"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { t } from "@/lib/i18n";
import type { Artifact } from "@/lib/types";
import { FlashcardsView } from "./FlashcardsView";
import { MindmapView } from "./MindmapView";
import { QuizView } from "./QuizView";
import { ReportView } from "./ReportView";
import { TableView } from "./TableView";

const EXPORTS: Record<string, string[]> = {
  note: ["md", "txt", "pdf", "json"],
  report: ["md", "pdf", "json"],
  mindmap: ["mmd", "pdf", "json"],
  quiz: ["md", "csv", "pdf", "json"],
  flashcards: ["md", "csv", "pdf", "json"],
  table: ["csv", "md", "pdf", "json"],
};

function preview(artifact: Artifact): string {
  if (artifact.type === "note") return artifact.payload.body || "";
  if (artifact.type === "report") return artifact.payload.body_md || "";
  if (artifact.type === "quiz") return `${artifact.payload.questions?.length || 0} Fragen`;
  if (artifact.type === "flashcards") return `${artifact.payload.cards?.length || 0} Karten`;
  if (artifact.type === "table") return `${artifact.payload.rows?.length || 0} Zeilen`;
  if (artifact.type === "mindmap") return artifact.payload.mermaid || "";
  return "";
}

export function ArtifactCard({ artifact, notebookId }: { artifact: Artifact; notebookId: string }) {
  const [open, setOpen] = useState(false);
  const formats = EXPORTS[artifact.type] || [];
  return (
    <li className="rounded-lg border border-line p-3">
      <button className="w-full text-left" onClick={() => setOpen((value) => !value)}>
        <div className="font-medium">{artifact.title}</div>
        <div className="text-[11px] uppercase tracking-wide text-neutral-400">{artifact.type}</div>
        {!open && <p className="mt-1 line-clamp-4 text-xs text-neutral-600">{preview(artifact)}</p>}
      </button>
      {open && (
        <div className="mt-2">
          {artifact.type === "note" && <p className="text-xs text-neutral-600">{artifact.payload.body}</p>}
          {artifact.type === "report" && <ReportView body={artifact.payload.body_md || ""} />}
          {artifact.type === "mindmap" && (
            <MindmapView source={artifact.payload.mermaid || ""} title={artifact.title} />
          )}
          {artifact.type === "quiz" && <QuizView questions={artifact.payload.questions || []} />}
          {artifact.type === "flashcards" && <FlashcardsView cards={artifact.payload.cards || []} />}
          {artifact.type === "table" && (
            <TableView columns={artifact.payload.columns || []} rows={artifact.payload.rows || []} />
          )}
          {formats.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1">
              <span className="text-[11px] text-neutral-400">{t.exportFile}</span>
              {formats.map((format) => (
                <a
                  key={format}
                  className="rounded border border-line px-1.5 py-0.5 text-[11px] uppercase hover:bg-mist"
                  href={api.artifactExportUrl(notebookId, artifact.id, format)}
                >
                  {format}
                </a>
              ))}
            </div>
          )}
        </div>
      )}
    </li>
  );
}
