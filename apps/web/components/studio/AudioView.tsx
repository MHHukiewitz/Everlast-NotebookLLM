"use client";

import { useEffect, useState } from "react";
import { CiteText, StudioCiteLinks, type StudioCiteProps } from "@/components/CiteText";
import { api } from "@/lib/api";
import { t } from "@/lib/i18n";
import { mediaIsBusy, mediaIsFailed, mediaIsReady, mediaStatusLabel } from "@/lib/mediaStatus";
import type { AudioTurn } from "@/lib/types";

export function AudioView({
  notebookId,
  artifactId,
  turns,
  status,
  progress,
  citations,
  onCite,
}: {
  notebookId: string;
  artifactId: string;
  turns: AudioTurn[];
  status?: string;
  progress?: string;
} & StudioCiteProps) {
  const [src, setSrc] = useState("");
  useEffect(() => {
    if (!mediaIsReady(status)) return;
    let objectUrl = "";
    let cancelled = false;
    fetch(api.artifactMediaUrl(notebookId, artifactId), { credentials: "include" })
      .then(async (response) => {
        if (!response.ok || cancelled) return;
        const blob = await response.blob();
        objectUrl = URL.createObjectURL(blob);
        if (!cancelled) setSrc(objectUrl);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [artifactId, notebookId, status]);
  return (
    <div className="text-xs">
      {(mediaIsBusy(status) || mediaIsFailed(status)) && (
        <p className={`mb-2 ${mediaIsFailed(status) ? "text-red-600" : "text-neutral-500"}`}>
          {mediaStatusLabel(status, progress, t.mediaPending, t.mediaFailed)}
        </p>
      )}
      {mediaIsReady(status) && src && <audio className="mb-2 w-full" controls src={src} />}
      <ol className="space-y-2 text-neutral-700">
        {turns.map((turn, index) => (
          <li key={index}>
            <CiteText text={turn.text} citations={citations} onCite={onCite} />
          </li>
        ))}
      </ol>
      <StudioCiteLinks
        text={turns.map((turn) => turn.text).join("\n")}
        citations={citations}
        onCite={onCite}
        fallback="sources"
      />
      <p className="mt-2 text-[11px] text-neutral-400">{t.aiBanner}</p>
    </div>
  );
}
