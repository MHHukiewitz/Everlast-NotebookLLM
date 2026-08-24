"use client";

import { useState } from "react";
import { StudioCiteLinks } from "@/components/CiteText";
import { MarkdownBody } from "@/components/MarkdownBody";
import { api } from "@/lib/api";
import { t } from "@/lib/i18n";
import { artifactCitationMap } from "@/lib/studioCitations";
import type { Artifact, MessageCitation, Source } from "@/lib/types";
import { AudioView } from "./AudioView";
import { FlashcardsView } from "./FlashcardsView";
import { InfographicView } from "./InfographicView";
import { MindmapView } from "./MindmapView";
import { QuizView } from "./QuizView";
import { ReportView } from "./ReportView";
import { SlidesView } from "./SlidesView";
import { TableView } from "./TableView";
import { VideoView } from "./VideoView";

const EXPORTS: Record<string, string[]> = {
  note: ["md", "txt", "pdf", "json"],
  report: ["md", "pdf", "json"],
  mindmap: ["png", "mmd", "pdf", "json"],
  quiz: ["md", "csv", "pdf", "json"],
  flashcards: ["md", "csv", "pdf", "json"],
  table: ["csv", "md", "pdf", "json"],
  slides: ["md", "pptx", "html", "pdf", "txt", "json"],
  infographic: ["png", "svg", "md", "pdf", "json"],
  audio: ["mp3", "md", "json"],
  video: ["mp4", "md", "json"],
};

function preview(artifact: Artifact): string {
  if (artifact.type === "note") return artifact.payload.body || "";
  if (artifact.type === "report") return artifact.payload.body_md || "";
  if (artifact.type === "quiz") return `${artifact.payload.questions?.length || 0} Fragen`;
  if (artifact.type === "flashcards") return `${artifact.payload.cards?.length || 0} Karten`;
  if (artifact.type === "table") return `${artifact.payload.rows?.length || 0} Zeilen`;
  if (artifact.type === "mindmap") return "Mindmap";
  if (artifact.type === "slides") return `${artifact.payload.slides?.length || 0} Folien`;
  if (artifact.type === "infographic") return `${artifact.payload.items?.length || 0} Blöcke`;
  if (artifact.type === "audio") return `${artifact.payload.turns?.length || 0} Wechsel`;
  if (artifact.type === "video") return `${artifact.payload.scenes?.length || 0} Szenen`;
  return "";
}

export function ArtifactCard({
  artifact,
  notebookId,
  onImported,
  onDeleted,
  loading = false,
  sources,
  onCite,
}: {
  artifact: Artifact;
  notebookId: string;
  onImported?: () => void;
  onDeleted?: () => void;
  loading?: boolean;
  sources?: Source[];
  onCite?: (cite: MessageCitation) => void;
}) {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState("");
  const formats = EXPORTS[artifact.type] || [];
  const citations = artifactCitationMap(artifact.payload || {}, sources);
  if (loading) {
    return (
      <li className="rounded-lg border border-accent bg-mist p-3">
        <div className="font-medium">{artifact.title}</div>
        <div className="text-[11px] uppercase tracking-wide text-neutral-400">{artifact.type}</div>
        <div className="mt-3 flex items-center gap-2 text-sm text-neutral-700">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-neutral-300 border-t-accent" />
          {t.generating}
        </div>
        <div className="mt-3 space-y-2" aria-hidden>
          <div className="h-3 animate-pulse rounded bg-neutral-200" />
          <div className="h-3 w-4/5 animate-pulse rounded bg-neutral-200" />
          <div className="h-20 animate-pulse rounded bg-neutral-200" />
        </div>
      </li>
    );
  }

  async function addAsSource() {
    setSaving(true);
    setSaveError("");
    const source = await api.artifactToSource(notebookId, artifact.id).catch((err: Error) => {
      setSaveError(err.message);
      return null;
    });
    setSaving(false);
    if (source) {
      setSaved(true);
      onImported?.();
    }
  }

  async function remove() {
    await api.deleteArtifact(notebookId, artifact.id);
    onDeleted?.();
  }

  return (
    <li className="rounded-lg border border-line p-3">
      <div className="flex items-start gap-2">
        <button className="min-w-0 flex-1 text-left" onClick={() => setOpen((value) => !value)}>
          <div className="font-medium">{artifact.title}</div>
          <div className="text-[11px] uppercase tracking-wide text-neutral-400">{artifact.type}</div>
          {!open && <p className="mt-1 line-clamp-4 text-xs text-neutral-600">{preview(artifact)}</p>}
        </button>
        <button
          className="mt-0.5 shrink-0 px-1 text-neutral-400 hover:text-red-600"
          title={t.removeArtifact}
          type="button"
          onClick={remove}
        >
          ×
        </button>
      </div>
      {open && (
        <div className="mt-2">
          {artifact.type === "note" && (
            <div className="text-xs text-neutral-600">
              <MarkdownBody citations={citations} onCite={onCite}>
                {artifact.payload.body || ""}
              </MarkdownBody>
              <StudioCiteLinks
                text={artifact.payload.body || ""}
                citations={citations}
                onCite={onCite}
                fallback="sources"
              />
            </div>
          )}
          {artifact.type === "report" && (
            <ReportView body={artifact.payload.body_md || ""} citations={citations} onCite={onCite} />
          )}
          {artifact.type === "mindmap" && (
            <MindmapView
              source={artifact.payload.mermaid || ""}
              title={artifact.title}
              citations={citations}
              onCite={onCite}
            />
          )}
          {artifact.type === "quiz" && (
            <QuizView questions={artifact.payload.questions || []} citations={citations} onCite={onCite} />
          )}
          {artifact.type === "flashcards" && (
            <FlashcardsView cards={artifact.payload.cards || []} citations={citations} onCite={onCite} />
          )}
          {artifact.type === "table" && (
            <TableView
              columns={artifact.payload.columns || []}
              rows={artifact.payload.rows || []}
              citations={citations}
              onCite={onCite}
            />
          )}
          {artifact.type === "slides" && (
            <SlidesView slides={artifact.payload.slides || []} citations={citations} onCite={onCite} />
          )}
          {artifact.type === "infographic" && (
            <InfographicView
              title={artifact.title}
              items={artifact.payload.items || []}
              charts={artifact.payload.charts || []}
              citations={citations}
              onCite={onCite}
            />
          )}
          {artifact.type === "audio" && (
            <AudioView
              notebookId={notebookId}
              artifactId={artifact.id}
              turns={artifact.payload.turns || []}
              status={artifact.payload.status}
              citations={citations}
              onCite={onCite}
            />
          )}
          {artifact.type === "video" && (
            <VideoView
              notebookId={notebookId}
              artifactId={artifact.id}
              scenes={artifact.payload.scenes || []}
              status={artifact.payload.status}
              citations={citations}
              onCite={onCite}
            />
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
          <div className="mt-3">
            <button
              className="rounded border border-line px-1.5 py-0.5 text-[11px] hover:bg-mist disabled:opacity-60"
              disabled={saving || saved}
              onClick={addAsSource}
              type="button"
            >
              {saving ? t.savingSource : t.asSource}
            </button>
            {saved && <p className="mt-1 text-[11px] text-neutral-500">{t.sourceSaved}</p>}
            {saveError && <p className="mt-1 text-[11px] text-red-600">{saveError}</p>}
          </div>
        </div>
      )}
    </li>
  );
}
