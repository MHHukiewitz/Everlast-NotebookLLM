"use client";

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { t } from "@/lib/i18n";
import { PANE_WIDTHS_COOKIE, readCookie, writeCookie } from "@/lib/notebook";

const MIN_SOURCES = 240;
const MAX_SOURCES = 520;
const MIN_STUDIO = 240;
const MAX_STUDIO = 480;
const MIN_CHAT = 360;
const HANDLE = 8;
const DEFAULT_SOURCES = MAX_SOURCES;
const DEFAULT_STUDIO = MAX_STUDIO;

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function readWidths(): { sources: number; studio: number } {
  const raw = readCookie(PANE_WIDTHS_COOKIE);
  if (!raw) return { sources: DEFAULT_SOURCES, studio: DEFAULT_STUDIO };
  const parts = raw.split(",");
  if (parts.length !== 2) return { sources: DEFAULT_SOURCES, studio: DEFAULT_STUDIO };
  const sources = Number(parts[0]);
  const studio = Number(parts[1]);
  if (!Number.isFinite(sources) || !Number.isFinite(studio)) {
    return { sources: DEFAULT_SOURCES, studio: DEFAULT_STUDIO };
  }
  return { sources, studio };
}

export function ResizableStages({
  sources,
  chat,
  studio,
}: {
  sources: ReactNode;
  chat: ReactNode;
  studio: ReactNode;
}) {
  const boxRef = useRef<HTMLElement>(null);
  const [wide, setWide] = useState(false);
  const [ready, setReady] = useState(false);
  const [widths, setWidths] = useState({ sources: DEFAULT_SOURCES, studio: DEFAULT_STUDIO });

  const apply = useCallback((nextSources: number, nextStudio: number) => {
    const box = boxRef.current;
    const inner = box ? box.clientWidth - HANDLE * 2 : 1600;
    const sourcesMax = clamp(inner - nextStudio - MIN_CHAT, MIN_SOURCES, MAX_SOURCES);
    const studioMax = clamp(inner - nextSources - MIN_CHAT, MIN_STUDIO, MAX_STUDIO);
    setWidths({
      sources: clamp(nextSources, MIN_SOURCES, sourcesMax),
      studio: clamp(nextStudio, MIN_STUDIO, studioMax),
    });
  }, []);

  useEffect(() => {
    const media = window.matchMedia("(min-width: 1024px)");
    const sync = () => setWide(media.matches);
    sync();
    media.addEventListener("change", sync);
    const saved = readWidths();
    setWidths(saved);
    setReady(true);
    return () => media.removeEventListener("change", sync);
  }, []);

  useEffect(() => {
    if (!ready) return;
    apply(widths.sources, widths.studio);
  }, [apply, ready]);

  useEffect(() => {
    if (!ready) return;
    writeCookie(PANE_WIDTHS_COOKIE, `${widths.sources},${widths.studio}`);
  }, [ready, widths]);

  useEffect(() => {
    if (!ready) return;
    function onResize() {
      apply(widths.sources, widths.studio);
    }
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [apply, ready, widths]);

  function startDrag(side: "sources" | "studio", event: React.PointerEvent<HTMLButtonElement>) {
    event.preventDefault();
    const originX = event.clientX;
    const origin = widths;
    const target = event.currentTarget;
    target.setPointerCapture(event.pointerId);

    function onMove(move: PointerEvent) {
      const delta = move.clientX - originX;
      if (side === "sources") {
        apply(origin.sources + delta, origin.studio);
        return;
      }
      apply(origin.sources, origin.studio - delta);
    }

    function onUp() {
      target.releasePointerCapture(event.pointerId);
      target.removeEventListener("pointermove", onMove);
      target.removeEventListener("pointerup", onUp);
    }

    target.addEventListener("pointermove", onMove);
    target.addEventListener("pointerup", onUp);
  }

  function nudge(side: "sources" | "studio", step: number) {
    if (side === "sources") {
      apply(widths.sources + step, widths.studio);
      return;
    }
    apply(widths.sources, widths.studio + step);
  }

  return (
    <main ref={boxRef} className="flex min-h-0 flex-1 flex-col lg:flex-row">
      <div
        className="min-h-0 min-w-0 flex-1 lg:flex-none"
        style={wide ? { width: widths.sources } : undefined}
      >
        {sources}
      </div>
      <Handle
        label={t.resizeSources}
        onPointerDown={(event) => startDrag("sources", event)}
        onKeyDown={(event) => {
          if (event.key === "ArrowLeft") nudge("sources", -16);
          if (event.key === "ArrowRight") nudge("sources", 16);
        }}
      />
      <div className="min-h-0 min-w-0 flex-1">{chat}</div>
      <Handle
        label={t.resizeStudio}
        onPointerDown={(event) => startDrag("studio", event)}
        onKeyDown={(event) => {
          if (event.key === "ArrowLeft") nudge("studio", 16);
          if (event.key === "ArrowRight") nudge("studio", -16);
        }}
      />
      <div
        className="min-h-0 min-w-0 flex-1 lg:flex-none"
        style={wide ? { width: widths.studio } : undefined}
      >
        {studio}
      </div>
    </main>
  );
}

function Handle({
  label,
  onPointerDown,
  onKeyDown,
}: {
  label: string;
  onPointerDown: (event: React.PointerEvent<HTMLButtonElement>) => void;
  onKeyDown: (event: React.KeyboardEvent<HTMLButtonElement>) => void;
}) {
  return (
    <button
      type="button"
      role="separator"
      aria-orientation="vertical"
      aria-label={label}
      className="stage-handle hidden lg:block"
      onPointerDown={onPointerDown}
      onKeyDown={onKeyDown}
    />
  );
}
