"use client";

import { useEffect, useId, useRef } from "react";
import { t } from "@/lib/i18n";

export function MindmapView({ source, title }: { source: string; title?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const reactId = useId().replace(/:/g, "");

  useEffect(() => {
    if (!source.trim()) return;
    let cancelled = false;
    import("mermaid").then(({ default: mermaid }) => {
      if (cancelled) return;
      mermaid.initialize({ startOnLoad: false, theme: "neutral", securityLevel: "strict" });
      mermaid.render(`mindmap-${reactId}`, source).then(
        ({ svg }) => {
          if (!cancelled && ref.current) {
            ref.current.innerHTML = svg;
          }
        },
        () => {
          if (!cancelled && ref.current) {
            ref.current.textContent = source;
          }
        },
      );
    });
    return () => {
      cancelled = true;
    };
  }, [reactId, source]);

  function downloadSvg() {
    const svg = ref.current?.querySelector("svg");
    if (!svg) return;
    const blob = new Blob([svg.outerHTML], { type: "image/svg+xml" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${title || "mindmap"}.svg`;
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div>
      <div ref={ref} className="overflow-auto" />
      <button className="mt-2 text-xs text-accent" onClick={downloadSvg}>
        {t.downloadSvg}
      </button>
      <details className="mt-2 text-xs text-neutral-500">
        <summary>Mermaid</summary>
        <pre className="mt-1 whitespace-pre-wrap">{source}</pre>
      </details>
    </div>
  );
}
