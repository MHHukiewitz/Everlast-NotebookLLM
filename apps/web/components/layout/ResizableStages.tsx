"use client";

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { t } from "@/lib/i18n";
import { PANE_WIDTHS_COOKIE, readCookie, writeCookie } from "@/lib/notebook";
import {
  DEFAULT_SOURCES,
  DEFAULT_STUDIO,
  MIN_SOURCES,
  MIN_STUDIO,
  fitPaneWidths,
  formatPaneWidths,
  parsePaneWidths,
  samePaneWidths,
} from "@/lib/paneWidths";

const HANDLE = 8;

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
  const desiredRef = useRef({ sources: DEFAULT_SOURCES, studio: DEFAULT_STUDIO });
  const [widths, setWidths] = useState({ sources: DEFAULT_SOURCES, studio: DEFAULT_STUDIO });

  const show = useCallback((nextSources: number, nextStudio: number) => {
    const box = boxRef.current;
    const inner = box && box.clientWidth > HANDLE * 2 ? box.clientWidth - HANDLE * 2 : 0;
    const next =
      inner > 0 ? fitPaneWidths(inner, nextSources, nextStudio) : { sources: nextSources, studio: nextStudio };
    setWidths((prev) => (samePaneWidths(prev, next) ? prev : next));
  }, []);

  useEffect(() => {
    const raw = readCookie(PANE_WIDTHS_COOKIE);
    const saved = parsePaneWidths(raw);
    desiredRef.current = saved;
    if (raw === `${MIN_SOURCES},${MIN_STUDIO}`) {
      writeCookie(PANE_WIDTHS_COOKIE, formatPaneWidths(saved));
    }
    show(saved.sources, saved.studio);
    const box = boxRef.current;
    if (!box) return;
    const observer = new ResizeObserver(() => {
      const desired = desiredRef.current;
      show(desired.sources, desired.studio);
    });
    observer.observe(box);
    return () => observer.disconnect();
  }, [show]);

  function startDrag(side: "sources" | "studio", event: React.PointerEvent<HTMLButtonElement>) {
    event.preventDefault();
    const originX = event.clientX;
    const origin = widths;
    const target = event.currentTarget;
    target.setPointerCapture(event.pointerId);

    function onMove(move: PointerEvent) {
      const delta = move.clientX - originX;
      const nextSources = side === "sources" ? origin.sources + delta : origin.sources;
      const nextStudio = side === "sources" ? origin.studio : origin.studio - delta;
      const box = boxRef.current;
      const inner = box && box.clientWidth > HANDLE * 2 ? box.clientWidth - HANDLE * 2 : 1600;
      const next = fitPaneWidths(inner, nextSources, nextStudio);
      desiredRef.current = next;
      setWidths(next);
    }

    function onUp() {
      writeCookie(PANE_WIDTHS_COOKIE, formatPaneWidths(desiredRef.current));
      target.releasePointerCapture(event.pointerId);
      target.removeEventListener("pointermove", onMove);
      target.removeEventListener("pointerup", onUp);
    }

    target.addEventListener("pointermove", onMove);
    target.addEventListener("pointerup", onUp);
  }

  function nudge(side: "sources" | "studio", step: number) {
    const nextSources = side === "sources" ? widths.sources + step : widths.sources;
    const nextStudio = side === "sources" ? widths.studio : widths.studio + step;
    const box = boxRef.current;
    const inner = box && box.clientWidth > HANDLE * 2 ? box.clientWidth - HANDLE * 2 : 1600;
    const next = fitPaneWidths(inner, nextSources, nextStudio);
    desiredRef.current = next;
    writeCookie(PANE_WIDTHS_COOKIE, formatPaneWidths(next));
    setWidths(next);
  }

  return (
    <main ref={boxRef} className="flex min-h-0 flex-1 flex-col lg:flex-row">
      <div
        className="min-h-0 min-w-0 flex-1 lg:w-[var(--pane-w)] lg:flex-none"
        style={{ ["--pane-w" as string]: `${widths.sources}px` }}
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
        className="min-h-0 min-w-0 flex-1 lg:w-[var(--pane-w)] lg:flex-none"
        style={{ ["--pane-w" as string]: `${widths.studio}px` }}
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
