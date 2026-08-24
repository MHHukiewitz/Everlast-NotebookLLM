"use client";

import { useEffect, useRef, useState } from "react";
import { StudioCiteLinks, type StudioCiteProps } from "@/components/CiteText";
import { t } from "@/lib/i18n";
import {
  edgePath,
  layoutMindmap,
  MINDMAP_FONT,
  normalizeMermaid,
  parseTree,
} from "@/lib/mindmapLayout";
import { downloadSvgAsPng, downloadSvgElement } from "@/lib/svgPng";

export { normalizeMermaid };

const FILLS = ["#eff6ff", "#f5f3ff", "#f0fdf4", "#fff7ed"];

export function MindmapView({
  source,
  title,
  citations,
  onCite,
}: { source: string; title?: string } & StudioCiteProps) {
  const paneRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const [paneWidth, setPaneWidth] = useState(400);
  const normalized = normalizeMermaid(source);
  const tree = parseTree(normalized);
  const layout = layoutMindmap(tree, Math.max(260, paneWidth - 8));

  useEffect(() => {
    const pane = paneRef.current;
    if (!pane) return;
    const sync = () => {
      const width = pane.clientWidth;
      if (width > 0) setPaneWidth(width);
    };
    sync();
    const observer = new ResizeObserver(sync);
    observer.observe(pane);
    return () => observer.disconnect();
  }, []);

  function currentSvg(): SVGSVGElement | null {
    return svgRef.current;
  }

  return (
    <div>
      <div
        ref={paneRef}
        className="max-h-[min(70vh,36rem)] min-h-[12rem] overflow-auto rounded-lg bg-mist p-2"
      >
        {normalized ? (
          <svg
            ref={svgRef}
            role="img"
            aria-label={title || tree.label}
            xmlns="http://www.w3.org/2000/svg"
            viewBox={`0 0 ${layout.width} ${layout.height}`}
            width={layout.width}
            height={layout.height}
            fontFamily="Inter, ui-sans-serif, system-ui, sans-serif"
            fontSize={MINDMAP_FONT}
          >
            <rect width={layout.width} height={layout.height} fill="#f6f7f8" />
            {layout.edges.map((edge, index) => (
              <path
                key={`e-${index}`}
                d={edgePath(edge)}
                fill="none"
                stroke="#a5b4c8"
                strokeWidth="1.6"
              />
            ))}
            {layout.boxes.map((box) => (
              <g key={box.id}>
                <rect
                  x={box.x}
                  y={box.y}
                  width={box.w}
                  height={box.h}
                  rx="8"
                  fill={box.depth === 0 ? "#dbeafe" : FILLS[box.depth % FILLS.length]}
                  stroke="#2563eb"
                  strokeWidth={box.depth === 0 ? 1.6 : 1}
                />
                {box.lines.map((line, index) => (
                  <text
                    key={`${box.id}-${index}`}
                    x={box.x + box.w / 2}
                    y={box.y + box.h / 2 - ((box.lines.length - 1) * 15) / 2 + index * 15}
                    textAnchor="middle"
                    dominantBaseline="middle"
                    fill="#1f1f1f"
                  >
                    {line}
                  </text>
                ))}
              </g>
            ))}
          </svg>
        ) : null}
      </div>
      <div className="mt-2 flex gap-3">
        <button
          className="text-xs text-accent"
          onClick={() => {
            const svg = currentSvg();
            if (svg) downloadSvgElement(svg, `${title || "mindmap"}.svg`);
          }}
        >
          {t.downloadSvg}
        </button>
        <button
          className="text-xs text-accent"
          onClick={() => {
            const svg = currentSvg();
            if (svg) downloadSvgAsPng(svg, `${title || "mindmap"}.png`);
          }}
        >
          {t.downloadPng}
        </button>
      </div>
      <details className="mt-2 text-xs text-neutral-500">
        <summary>Mermaid</summary>
        <pre className="mt-1 whitespace-pre-wrap">{normalized || source}</pre>
      </details>
      <StudioCiteLinks text={normalized || source} citations={citations} onCite={onCite} fallback="sources" />
    </div>
  );
}
