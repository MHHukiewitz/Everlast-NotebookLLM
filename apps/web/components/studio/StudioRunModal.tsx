"use client";

import { StudioNotifyToggle } from "@/components/studio/StudioNotifyToggle";
import { t } from "@/lib/i18n";
import type { Skill, Source } from "@/lib/types";

export function StudioRunModal({
  skill,
  sources,
  sourceIds,
  prompt,
  format,
  language,
  style,
  busy,
  error,
  onClose,
  onSourceIds,
  onPrompt,
  onFormat,
  onLanguage,
  onStyle,
  onCreate,
}: {
  skill: Skill;
  sources: Source[];
  sourceIds: string[];
  prompt: string;
  format: "briefing" | "explainer";
  language: string;
  style: string;
  busy: boolean;
  error: string;
  onClose: () => void;
  onSourceIds: (ids: string[]) => void;
  onPrompt: (value: string) => void;
  onFormat: (value: "briefing" | "explainer") => void;
  onLanguage: (value: string) => void;
  onStyle: (value: string) => void;
  onCreate: () => void;
}) {
  const ready = sources.filter((source) => source.status === "ready");
  const media = skill.id === "studio.audio" || skill.id === "studio.video";

  function toggle(id: string) {
    if (sourceIds.includes(id)) {
      onSourceIds(sourceIds.filter((item) => item !== id));
      return;
    }
    onSourceIds([...sourceIds, id]);
  }

  return (
    <div className="fixed inset-0 z-20 flex items-center justify-center bg-black/30 p-4">
      <div className="max-h-[80vh] w-full max-w-lg overflow-auto rounded-2xl bg-white p-5 shadow-xl">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="font-medium">
            {skill.title} {t.studioAdjust}
          </h3>
          <button disabled={busy} onClick={onClose}>
            {t.close}
          </button>
        </div>
        <div className="space-y-3 text-sm">
          <div>
            <div className="mb-1 flex items-center justify-between">
              <p className="font-medium">{t.studioPickSources}</p>
              <div className="flex gap-2 text-xs">
                <button type="button" className="text-accent" onClick={() => onSourceIds(ready.map((source) => source.id))}>
                  {t.studioAllSources}
                </button>
                <button type="button" className="text-neutral-500" onClick={() => onSourceIds([])}>
                  {t.studioNoSourcePick}
                </button>
              </div>
            </div>
            <ul className="max-h-40 space-y-1 overflow-auto rounded-lg border border-line p-2">
              {ready.map((source) => (
                <li key={source.id}>
                  <label className="flex items-start gap-2 text-xs">
                    <input
                      type="checkbox"
                      checked={sourceIds.includes(source.id)}
                      onChange={() => toggle(source.id)}
                    />
                    <span>{source.title}</span>
                  </label>
                </li>
              ))}
            </ul>
            <p className="mt-1 text-xs text-neutral-500">{t.sourcesCount(sourceIds.length)}</p>
          </div>
          {media && (
            <>
              <p className="font-medium">{t.mediaFormat}</p>
              <label className="flex items-start gap-2 rounded-lg border border-line p-2">
                <input
                  type="radio"
                  name="studio-format"
                  checked={format === "explainer"}
                  onChange={() => onFormat("explainer")}
                />
                <span>
                  <span className="font-medium">
                    {skill.id === "studio.video" ? t.mediaExplainer : t.mediaExplainerAudio}
                  </span>
                  <span className="mt-0.5 block text-xs text-neutral-500">{t.mediaExplainerHint}</span>
                </span>
              </label>
              <label className="flex items-start gap-2 rounded-lg border border-line p-2">
                <input
                  type="radio"
                  name="studio-format"
                  checked={format === "briefing"}
                  onChange={() => onFormat("briefing")}
                />
                <span>
                  <span className="font-medium">{t.mediaBriefing}</span>
                  <span className="mt-0.5 block text-xs text-neutral-500">{t.mediaBriefingHint}</span>
                </span>
              </label>
              <label className="block">
                {t.mediaLanguage}
                <select
                  className="mt-1 w-full rounded border border-line p-1"
                  value={language}
                  onChange={(e) => onLanguage(e.target.value)}
                >
                  <option value="de">{t.mediaGerman}</option>
                  <option value="en">{t.mediaEnglish}</option>
                </select>
              </label>
            </>
          )}
          {skill.id === "studio.video" && (
            <div>
              <p className="font-medium">{t.mediaStyle}</p>
              <div className="mt-2 grid grid-cols-2 gap-2">
                {[
                  ["auto", t.styleAuto],
                  ["classic", t.styleClassic],
                  ["whiteboard", t.styleWhiteboard],
                  ["kawaii", t.styleKawaii],
                ].map(([id, label]) => (
                  <button
                    key={id}
                    type="button"
                    className={`rounded-lg border px-2 py-2 text-left text-xs ${style === id ? "border-accent bg-mist" : "border-line"}`}
                    onClick={() => onStyle(id)}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
          )}
          <label className="block">
            {t.studioPrompt}
            <span className="mt-0.5 block text-xs font-normal text-neutral-500">{t.studioPromptHint}</span>
            {skill.hint ? (
              <span className="mt-1 block whitespace-pre-line text-xs font-normal text-neutral-500">{skill.hint}</span>
            ) : null}
            <textarea
              className="mt-1 h-28 w-full rounded border border-line p-2"
              value={prompt}
              onChange={(e) => onPrompt(e.target.value)}
              placeholder={skill.description}
            />
          </label>
          {error && <p className="text-xs text-red-600">{error}</p>}
          <StudioNotifyToggle hint={t.notifyStudioHint} />
          <button className="btn-primary w-full" disabled={busy} onClick={onCreate}>
            {busy ? t.generating : t.mediaCreate}
          </button>
        </div>
      </div>
    </div>
  );
}
