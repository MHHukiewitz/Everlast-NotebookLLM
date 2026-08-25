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

const FILLS = ["#1d4ed8", "#dbeafe", "#ede9fe", "#dcfce7", "#ffedd5"];
const STROKES = ["#1e3a8a", "#60a5fa", "#a78bfa", "#4ade80", "#fb923c"];
const TEXTS = ["#ffffff", "#1f2937", "#1f2937", "#1f2937", "#1f2937"];

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
        className="max-h-[min(70vh,36rem)] min-h-[16rem] overflow-auto rounded-lg bg-white p-2"
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
            className="h-auto w-full"
            fontFamily="Inter, ui-sans-serif, system-ui, sans-serif"
            fontSize={MINDMAP_FONT}
          >
            <rect width={layout.width} height={layout.height} fill="#ffffff" />
            {layout.edges.map((edge, index) => (
              <path
                key={`e-${index}`}
                d={edgePath(edge)}
                fill="none"
                stroke="#94a3b8"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            ))}
            {layout.boxes.map((box) => {
              const tone = Math.min(box.depth, FILLS.length - 1);
              const lineH = box.depth === 0 ? 16 : 15;
              return (
                <g key={box.id}>
                  <rect
                    x={box.x}
                    y={box.y}
                    width={box.w}
                    height={box.h}
                    rx={box.depth === 0 ? 14 : 10}
                    fill={FILLS[tone]}
                    stroke={STROKES[tone]}
                    strokeWidth={box.depth === 0 ? 0 : 1}
                  />
                  {box.lines.map((line, index) => (
                    <text
                      key={`${box.id}-${index}`}
                      x={box.x + box.w / 2}
                      y={box.y + box.h / 2 - ((box.lines.length - 1) * lineH) / 2 + index * lineH}
                      textAnchor="middle"
                      dominantBaseline="middle"
                      fill={TEXTS[tone]}
                      fontSize={box.depth === 0 ? 13 : MINDMAP_FONT}
                      fontWeight={box.depth === 0 ? 600 : 500}
                    >
                      {line}
                    </text>
                  ))}
                </g>
              );
            })}
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
