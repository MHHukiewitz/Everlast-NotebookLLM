import { bindChatCitations, usedCitations } from "./chatLive";
import type { ArtifactCitation, ArtifactPayload, MessageCitation } from "./types";

type CiteSource = {
  id: string;
  title?: string;
  status?: string;
  origin_uri?: string | null;
};

export function artifactCiteText(payload: ArtifactPayload, type: string): string {
  const parts: string[] = [];
  if (payload.body) parts.push(payload.body);
  if (payload.body_md) parts.push(payload.body_md);
  if (payload.mermaid) parts.push(payload.mermaid);
  for (const card of payload.cards || []) {
    parts.push(card.front, card.back, card.cite || "");
  }
  for (const question of payload.questions || []) {
    parts.push(question.question, ...(question.choices || []), question.explanation || "");
  }
  for (const slide of payload.slides || []) {
    parts.push(slide.heading, ...(slide.bullets || []), slide.notes || "");
  }
  for (const row of payload.rows || []) {
    parts.push(...row);
  }
  for (const item of payload.items || []) {
    parts.push(item.label, item.value, item.detail || "", item.caption || "");
  }
  for (const chart of payload.charts || []) {
    parts.push(chart.title, chart.cite || "");
  }
  for (const turn of payload.turns || []) {
    parts.push(turn.text);
  }
  for (const scene of payload.scenes || []) {
    parts.push(scene.heading, ...(scene.bullets || []), scene.narration || "");
  }
  if (type === "table" && payload.columns) {
    parts.push(...payload.columns);
  }
  return parts.join("\n");
}

export function normalizeArtifactCitations(raw?: ArtifactCitation[]): MessageCitation[] {
  return (raw || []).map((item, index) => ({
    n: Number(item.n) || index + 1,
    source_id: item.source_id,
    chunk_id: item.chunk_id,
    quote: item.quote || "",
    title: item.source_title || item.title,
    url: item.url,
  }));
}

export function uniqueSourceCitations(citations: MessageCitation[]): MessageCitation[] {
  const seen = new Set<string>();
  const out: MessageCitation[] = [];
  for (const item of citations) {
    const key = item.source_id || item.url || `n:${item.n}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(item);
  }
  return out;
}

export function artifactCitationMap(payload: ArtifactPayload, sources?: CiteSource[]): MessageCitation[] {
  const mapped = normalizeArtifactCitations(payload.citations);
  const ready = (sources || []).filter((source) => !source.status || source.status === "ready");
  if (mapped.length) {
    return mapped.map((item) => {
      const source = ready.find((entry) => entry.id === item.source_id);
      return {
        ...item,
        title: item.title || source?.title,
        url: item.url || source?.origin_uri || undefined,
        quote: item.quote || source?.title || "",
      };
    });
  }
  return ready.map((source, index) => ({
    n: index + 1,
    source_id: source.id,
    quote: source.title || "",
    title: source.title,
    url: source.origin_uri || undefined,
  }));
}

export function bindArtifactCitations(
  payload: ArtifactPayload,
  type: string,
  sources?: CiteSource[],
): MessageCitation[] {
  const text = artifactCiteText(payload, type);
  const mapped = artifactCitationMap(payload, sources);
  const bound = bindChatCitations(
    text,
    mapped,
    sources?.filter((source) => !source.status || source.status === "ready"),
  );
  if (bound.length) return bound;
  if (payload.citations?.length) return uniqueSourceCitations(mapped);
  return [];
}

export function bindTextCitations(text: string, citations?: MessageCitation[]): MessageCitation[] {
  const used = usedCitations(text, citations);
  if (used.length) return used;
  return uniqueSourceCitations(citations || []);
}
