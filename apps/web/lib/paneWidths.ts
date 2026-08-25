export const MIN_SOURCES = 240;
export const MAX_SOURCES = 520;
export const MIN_STUDIO = 240;
export const MAX_STUDIO = 480;
export const MIN_CHAT = 360;
export const DEFAULT_SOURCES = MAX_SOURCES;
export const DEFAULT_STUDIO = MAX_STUDIO;

export function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export function parsePaneWidths(raw: string): { sources: number; studio: number } {
  if (!raw) return { sources: DEFAULT_SOURCES, studio: DEFAULT_STUDIO };
  if (raw === `${MIN_SOURCES},${MIN_STUDIO}`) {
    return { sources: DEFAULT_SOURCES, studio: DEFAULT_STUDIO };
  }
  const parts = raw.split(",");
  if (parts.length !== 2) return { sources: DEFAULT_SOURCES, studio: DEFAULT_STUDIO };
  const sources = Number(parts[0]);
  const studio = Number(parts[1]);
  if (!Number.isFinite(sources) || !Number.isFinite(studio)) {
    return { sources: DEFAULT_SOURCES, studio: DEFAULT_STUDIO };
  }
  return {
    sources: clamp(sources, MIN_SOURCES, MAX_SOURCES),
    studio: clamp(studio, MIN_STUDIO, MAX_STUDIO),
  };
}

export function formatPaneWidths(widths: { sources: number; studio: number }): string {
  return `${widths.sources},${widths.studio}`;
}

export function fitPaneWidths(
  inner: number,
  sources: number,
  studio: number,
): { sources: number; studio: number } {
  const sourcesMax = clamp(inner - studio - MIN_CHAT, MIN_SOURCES, MAX_SOURCES);
  const studioMax = clamp(inner - sources - MIN_CHAT, MIN_STUDIO, MAX_STUDIO);
  return {
    sources: clamp(sources, MIN_SOURCES, sourcesMax),
    studio: clamp(studio, MIN_STUDIO, studioMax),
  };
}

export function samePaneWidths(
  a: { sources: number; studio: number },
  b: { sources: number; studio: number },
): boolean {
  return a.sources === b.sources && a.studio === b.studio;
}
