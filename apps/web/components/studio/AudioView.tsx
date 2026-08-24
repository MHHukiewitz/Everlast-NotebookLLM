"use client";

import { useEffect, useState } from "react";
import { CiteText, StudioCiteLinks, type StudioCiteProps } from "@/components/CiteText";
import { api } from "@/lib/api";
import { t } from "@/lib/i18n";
import type { AudioTurn } from "@/lib/types";

export function AudioView({
  notebookId,
  artifactId,
  turns,
  status,
  citations,
  onCite,
}: {
  notebookId: string;
  artifactId: string;
  turns: AudioTurn[];
  status?: string;
} & StudioCiteProps) {
  const [src, setSrc] = useState("");
  useEffect(() => {
    if (status !== "ready") return;
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
      {status === "pending" && <p className="mb-2 text-neutral-500">{t.mediaPending}</p>}
      {src && <audio className="mb-2 w-full" controls src={src} />}
      <ol className="space-y-2 text-neutral-700">
        {turns.map((turn, index) => (
          <li key={`${turn.speaker}-${index}`}>
            <span className="font-medium">{turn.speaker}:</span>{" "}
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
