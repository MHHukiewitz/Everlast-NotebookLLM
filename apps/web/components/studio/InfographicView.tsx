"use client";

import { CiteText, StudioCiteLinks, type StudioCiteProps } from "@/components/CiteText";
import { t } from "@/lib/i18n";
import { downloadSvgAsPng, downloadSvgMarkup } from "@/lib/svgPng";
import type { InfographicChart, InfographicItem, InfographicPoint } from "@/lib/types";

const TINTS = ["bg-blue-50", "bg-purple-50", "bg-green-50", "bg-amber-50"];
const COLORS = ["#2563eb", "#7c3aed", "#16a34a", "#d97706", "#db2777", "#0891b2"];

function xmlEscape(value: string): string {
  return value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function wrapWords(text: string, width: number): string[] {
  const words = text.split(/\s+/).filter(Boolean);
  if (words.length === 0) return [""];
  const lines: string[] = [];
  let current = words[0];
  for (const word of words.slice(1)) {
    const trial = `${current} ${word}`;
    if (trial.length <= width) current = trial;
    else {
      lines.push(current);
      current = word;
    }
  }
  lines.push(current);
  return lines.slice(0, 6);
}

function ChartView({
  chart,
  citations,
  onCite,
}: { chart: InfographicChart } & StudioCiteProps) {
  const points = (chart.points || []).filter((point) => Number.isFinite(point.value));
  if (points.length < 2) return null;
  const peak = Math.max(...points.map((point) => point.value), 1);
  const unit = chart.unit ? ` ${chart.unit}` : "";
  return (
    <figure className="rounded-xl border border-line bg-white p-3">
      <figcaption className="text-xs font-medium text-neutral-800">{chart.title}</figcaption>
      {chart.type === "pie" ? <PieChart points={points} unit={unit} /> : null}
      {chart.type === "bar" ? <BarChart points={points} peak={peak} /> : null}
      {chart.type !== "pie" && chart.type !== "bar" ? <HBarChart points={points} peak={peak} unit={unit} /> : null}
      {chart.cite && (
        <p className="mt-2 text-[11px] text-neutral-400">
          <CiteText text={chart.cite} citations={citations} onCite={onCite} />
        </p>
      )}
    </figure>
  );
}

function BarChart({ points, peak }: { points: InfographicPoint[]; peak: number }) {
  return (
    <div className="mt-3 flex h-32 items-end gap-2">
      {points.map((point, index) => (
        <div key={point.label} className="flex min-w-0 flex-1 flex-col items-center">
          <span className="mb-1 text-[10px] text-neutral-500">{point.value}</span>
          <div
            className="w-full rounded-t"
            style={{ height: `${Math.max(8, (point.value / peak) * 100)}%`, background: COLORS[index % COLORS.length] }}
          />
          <span className="mt-1 w-full truncate text-center text-[10px] text-neutral-600">{point.label}</span>
        </div>
      ))}
    </div>
  );
}

function HBarChart({ points, peak, unit }: { points: InfographicPoint[]; peak: number; unit: string }) {
  return (
    <ul className="mt-3 space-y-2">
      {points.map((point, index) => (
        <li key={point.label} className="text-[11px]">
          <div className="mb-0.5 flex justify-between gap-2 text-neutral-700">
            <span>{point.label}</span>
            <span>
              {point.value}
              {unit}
            </span>
          </div>
          <div className="h-2 overflow-hidden rounded bg-mist">
            <div
              className="h-2 rounded"
              style={{ width: `${Math.max(6, (point.value / peak) * 100)}%`, background: COLORS[index % COLORS.length] }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}

function PieChart({ points, unit }: { points: InfographicPoint[]; unit: string }) {
  const total = points.reduce((sum, point) => sum + point.value, 0) || 1;
  let angle = -90;
  const slices = points.map((point, index) => {
    const sweep = (point.value / total) * 360;
    const start = angle;
    angle += sweep;
    return { point, color: COLORS[index % COLORS.length], start, sweep };
  });
  return (
    <div className="mt-3 flex items-center gap-3">
      <svg viewBox="0 0 120 120" className="h-28 w-28 shrink-0">
        {slices.map((slice) => (
          <path key={slice.point.label} d={pieSlice(60, 60, 52, slice.start, slice.sweep)} fill={slice.color} />
        ))}
      </svg>
      <ul className="space-y-1 text-[11px] text-neutral-700">
        {slices.map((slice) => (
          <li key={slice.point.label} className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-sm" style={{ background: slice.color }} />
            <span>
              {slice.point.label} · {slice.point.value}
              {unit}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function pieSlice(cx: number, cy: number, r: number, startDeg: number, sweepDeg: number): string {
  const start = (startDeg * Math.PI) / 180;
  const end = ((startDeg + sweepDeg) * Math.PI) / 180;
  const x1 = cx + r * Math.cos(start);
  const y1 = cy + r * Math.sin(start);
  const x2 = cx + r * Math.cos(end);
  const y2 = cy + r * Math.sin(end);
  const large = sweepDeg > 180 ? 1 : 0;
  return `M ${cx} ${cy} L ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2} Z`;
}

export function buildInfographicSvg(title: string, items: InfographicItem[], charts: InfographicChart[] = []): string {
  const fills = ["#eff6ff", "#f5f3ff", "#f0fdf4", "#fff7ed"];
  const colW = 300;
  const gap = 16;
  let y = 64;
  const cards: {
    x: number;
    y: number;
    h: number;
    item: InfographicItem;
    values: string[];
    captions: string[];
    details: string[];
  }[] = [];
  let rowH = 0;
  items.forEach((item, index) => {
    const captions = item.caption ? wrapWords(item.caption, 34) : [];
    const values = item.value && item.value !== item.caption ? wrapWords(item.value, 28) : [];
    const details = item.detail && item.detail !== item.caption ? wrapWords(item.detail, 34) : [];
    const numberH = item.number ? 36 : 0;
    const h = 56 + numberH + 16 * captions.length + 20 * values.length + 16 * details.length;
    const col = index % 2;
    if (col === 0) rowH = h;
    else rowH = Math.max(rowH, h);
    cards.push({ x: 16 + col * (colW + gap), y, h, item, values, captions, details });
    if (col === 1 || index === items.length - 1) y += rowH + gap;
  });
  const height = Math.max(y + 28, 160);
  const blocks = cards
    .map((card, index) => {
      let cursor = card.y + 22;
      let numberSvg = "";
      if (card.item.number) {
        cursor += 32;
        const suffix = card.item.suffix
          ? `<tspan font-size="20" font-weight="500" fill="#525252">${xmlEscape(card.item.suffix)}</tspan>`
          : "";
        numberSvg = `<text x="${card.x + 16}" y="${cursor}" font-size="28" font-weight="600" fill="#1f1f1f">${xmlEscape(card.item.number)}${suffix ? " " + suffix : ""}</text>`;
      }
      const captionSvg = card.captions
        .map((line) => {
          cursor += 16;
          return `<text x="${card.x + 16}" y="${cursor}" font-size="12" fill="#404040">${xmlEscape(line)}</text>`;
        })
        .join("");
      const valueSvg = card.values
        .map((line) => {
          cursor += 20;
          return `<text x="${card.x + 16}" y="${cursor}" font-size="15" font-weight="600" fill="#1f1f1f">${xmlEscape(line)}</text>`;
        })
        .join("");
      const detailSvg = card.details
        .map((line) => {
          cursor += 16;
          return `<text x="${card.x + 16}" y="${cursor}" font-size="11" fill="#525252">${xmlEscape(line)}</text>`;
        })
        .join("");
      return [
        `<rect x="${card.x}" y="${card.y}" width="${colW}" height="${card.h}" rx="10" fill="${fills[index % fills.length]}" stroke="#e5e5e5"/>`,
        `<text x="${card.x + 16}" y="${card.y + 22}" font-size="11" fill="#737373">${xmlEscape(`${index + 1} · ${card.item.label}`)}</text>`,
        numberSvg,
        captionSvg,
        valueSvg,
        detailSvg,
      ].join("");
    })
    .join("");
  const chartNote = charts
    .map((chart) => `${xmlEscape(chart.title)}: ${chart.points.map((point) => `${point.label} ${point.value}`).join(", ")}`)
    .join(" · ");
  return [
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 ${height}" width="640" height="${height}">`,
    `<rect width="640" height="${height}" fill="#ffffff"/>`,
    `<text x="16" y="36" font-size="18" font-weight="600" fill="#1f1f1f">${xmlEscape(title)}</text>`,
    chartNote ? `<text x="16" y="52" font-size="10" fill="#525252">${chartNote}</text>` : "",
    blocks,
    `</svg>`,
  ].join("");
}

export function InfographicView({
  title,
  items,
  charts = [],
  citations,
  onCite,
}: {
  title: string;
  items: InfographicItem[];
  charts?: InfographicChart[];
} & StudioCiteProps) {
  function downloadSvg() {
    downloadSvgMarkup(buildInfographicSvg(title, items, charts), `${title || "infografik"}.svg`);
  }

  function downloadPng() {
    downloadSvgAsPng(buildInfographicSvg(title, items, charts), `${title || "infografik"}.png`);
  }

  return (
    <div>
      {charts.length > 0 && (
        <div className="mb-3 space-y-2">
          {charts.map((chart, index) => (
            <ChartView key={`${chart.title}-${index}`} chart={chart} citations={citations} onCite={onCite} />
          ))}
        </div>
      )}
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {items.map((item, index) => (
          <article key={`${item.label}-${index}`} className={`rounded-xl border border-line p-3 ${TINTS[index % TINTS.length]}`}>
            <p className="text-[11px] uppercase tracking-wide text-neutral-500">
              {index + 1} · {item.label}
            </p>
            {item.number ? (
              <p className="mt-2 flex items-baseline gap-1 text-neutral-900">
                <span className="text-3xl font-semibold tabular-nums tracking-tight">{item.number}</span>
                {item.suffix ? <span className="text-xl font-medium text-neutral-600">{item.suffix}</span> : null}
              </p>
            ) : null}
            {item.caption ? (
              <p className="mt-1 text-sm text-neutral-700">
                <CiteText text={item.caption} citations={citations} onCite={onCite} />
              </p>
            ) : null}
            {item.value && item.value !== item.caption ? (
              <p className={`text-sm font-semibold text-neutral-900 ${item.number ? "mt-2" : "mt-1"}`}>
                <CiteText text={item.value} citations={citations} onCite={onCite} />
              </p>
            ) : null}
            {item.detail && item.detail !== item.caption ? (
              <p className="mt-1 text-xs leading-5 text-neutral-600">
                <CiteText text={item.detail} citations={citations} onCite={onCite} />
              </p>
            ) : null}
          </article>
        ))}
      </div>
      <div className="mt-2 flex gap-3">
        <button className="text-xs text-accent" onClick={downloadSvg}>
          {t.downloadSvg}
        </button>
        <button className="text-xs text-accent" onClick={downloadPng}>
          {t.downloadPng}
        </button>
      </div>
      <StudioCiteLinks
        text={[
          ...items.flatMap((item) => [item.label, item.value, item.detail || "", item.caption || ""]),
          ...charts.flatMap((chart) => [chart.title, chart.cite || ""]),
        ].join("\n")}
        citations={citations}
        onCite={onCite}
        fallback="sources"
      />
    </div>
  );
}
