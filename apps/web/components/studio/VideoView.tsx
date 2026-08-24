"use client";

import { useEffect, useState } from "react";
import { CiteText, StudioCiteLinks, type StudioCiteProps } from "@/components/CiteText";
import { api } from "@/lib/api";
import { t } from "@/lib/i18n";
import { mediaIsBusy, mediaIsFailed, mediaIsReady, mediaStatusLabel } from "@/lib/mediaStatus";
import type { VideoScene } from "@/lib/types";

export function VideoView({
  notebookId,
  artifactId,
  scenes,
  status,
  progress,
  citations,
  onCite,
}: {
  notebookId: string;
  artifactId: string;
  scenes: VideoScene[];
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
      {mediaIsReady(status) && src && <video className="mb-2 w-full rounded border border-line" controls src={src} />}
      <ol className="space-y-3 text-neutral-700">
        {scenes.map((scene, index) => (
          <li key={`${scene.heading}-${index}`}>
            <p className="font-medium">
              {index + 1}. <CiteText text={scene.heading} citations={citations} onCite={onCite} />
            </p>
            <ul className="mt-1 list-disc pl-4">
              {(scene.bullets || []).map((bullet) => (
                <li key={bullet}>
                  <CiteText text={bullet} citations={citations} onCite={onCite} />
                </li>
              ))}
            </ul>
            {scene.narration && (
              <p className="mt-1 text-neutral-500">
                <CiteText text={scene.narration} citations={citations} onCite={onCite} />
              </p>
            )}
          </li>
        ))}
      </ol>
      <StudioCiteLinks
        text={scenes
          .map((scene) => `${scene.heading}\n${(scene.bullets || []).join("\n")}\n${scene.narration || ""}`)
          .join("\n")}
        citations={citations}
        onCite={onCite}
        fallback="sources"
      />
      <p className="mt-2 text-[11px] text-neutral-400">{t.aiBanner}</p>
    </div>
  );
}
