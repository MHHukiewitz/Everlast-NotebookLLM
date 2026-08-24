import type { Artifact, AuthUser, Message, Notebook, Provider, ResearchJob, Skill, Source, SourceDetail } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL || "";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

function apiDetail(body: string, fallback: string): string {
  const prefix = '{"detail":"';
  if (body.startsWith(prefix) && body.endsWith('"}')) {
    return body.slice(prefix.length, -2).replace(/\\"/g, '"');
  }
  return body || fallback;
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (!headers.has("Content-Type") && init?.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    credentials: "include",
    headers,
  });
  if (!response.ok) {
    const body = await response.text();
    throw new ApiError(apiDetail(body, response.statusText), response.status);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export const api = {
  me: () => req<AuthUser>("/api/auth/me"),
  login: (email: string, password: string) =>
    req<AuthUser>("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  register: (email: string, password: string, privacyAck: boolean) =>
    req<AuthUser>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, privacy_ack: privacyAck }),
    }),
  logout: () => req<{ status: string }>("/api/auth/logout", { method: "POST" }),
  deleteAccount: () => req<{ status: string }>("/api/auth/me", { method: "DELETE" }),
  providers: () => req<Provider[]>("/api/providers"),
  notebooks: () => req<Notebook[]>("/api/notebooks"),
  createNotebook: () => req<Notebook>("/api/notebooks", { method: "POST" }),
  notebook: (id: string) => req<Notebook>(`/api/notebooks/${id}`),
  updateNotebook: (id: string, body: Partial<Notebook> & { eu_notice_accepted?: boolean; openrouter_notice_accepted?: boolean }) =>
    req<Notebook>(`/api/notebooks/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  sources: (id: string) => req<Source[]>(`/api/notebooks/${id}/sources`),
  source: (notebookId: string, sourceId: string) => req<SourceDetail>(`/api/notebooks/${notebookId}/sources/${sourceId}`),
  addUrl: (id: string, url: string) =>
    req<Source>(`/api/notebooks/${id}/sources/url`, { method: "POST", body: JSON.stringify({ url }) }),
  addText: (id: string, title: string, text: string) =>
    req<Source>(`/api/notebooks/${id}/sources/text`, { method: "POST", body: JSON.stringify({ title, text }) }),
  selectSource: (notebookId: string, sourceId: string, selected: boolean) =>
    req<Source>(`/api/notebooks/${notebookId}/sources/${sourceId}`, {
      method: "PATCH",
      body: JSON.stringify({ selected }),
    }),
  deleteSource: (notebookId: string, sourceId: string) =>
    req(`/api/notebooks/${notebookId}/sources/${sourceId}`, { method: "DELETE" }),
  pdfUrl: (notebookId: string, sourceId: string) => `${BASE}/api/notebooks/${notebookId}/sources/${sourceId}/pdf`,
  messages: (id: string) => req<Message[]>(`/api/notebooks/${id}/messages`),
  skills: () => req<Skill[]>("/api/skills"),
  artifacts: (id: string) => req<Artifact[]>(`/api/notebooks/${id}/artifacts`),
  artifactExportUrl: (notebookId: string, artifactId: string, format: string) =>
    `${BASE}/api/notebooks/${notebookId}/artifacts/${artifactId}/export?format=${format}`,
  createNote: (id: string, title: string, body: string, messageId?: string) =>
    req<Artifact>(`/api/notebooks/${id}/notes`, {
      method: "POST",
      body: JSON.stringify({ title, body, message_id: messageId || null }),
    }),
  runSkill: (notebookId: string, skillId: string, args: Record<string, unknown> = {}) =>
    req<{ artifact_id: string; title: string }>(`/api/skills/${skillId}/run?notebook_id=${notebookId}`, {
      method: "POST",
      body: JSON.stringify({ args }),
    }),
  research: (id: string, query: string, mode: "fast" | "deep") =>
    req<ResearchJob>(`/api/notebooks/${id}/research`, { method: "POST", body: JSON.stringify({ query, mode }) }),
  researchJob: (notebookId: string, jobId: string) =>
    req<ResearchJob>(`/api/notebooks/${notebookId}/research/${jobId}`),
  importResearch: (notebookId: string, jobId: string, citationIds: string[], importReport: boolean) =>
    req<Source[]>(`/api/notebooks/${notebookId}/research/${jobId}/import`, {
      method: "POST",
      body: JSON.stringify({ citation_ids: citationIds, import_report: importReport }),
    }),
  compliance: () => req<Record<string, unknown>>("/api/compliance"),
  exportNotebook: (id: string) => req<Record<string, unknown>>(`/api/notebooks/${id}/export`),
  eraseNotebook: (id: string) => req<{ status: string }>(`/api/notebooks/${id}`, { method: "DELETE" }),
  evalRuns: () => req<EvalRun[]>("/api/eval/runs"),
  evalRun: (id: string) => req<EvalRun>(`/api/eval/runs/${id}`),
  startEval: (provider: string, model_id: string) =>
    req<EvalRun>("/api/eval/runs", { method: "POST", body: JSON.stringify({ provider, model_id }) }),
  scoreEvalItem: (id: string, body: HumanScore) =>
    req<EvalItem>(`/api/eval/items/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  compareEval: (a: string, b: string) => req<EvalCompare>(`/api/eval/compare?a=${a}&b=${b}`),
  generations: () => req<GenerationLog[]>("/api/eval/generations"),
};

export type GenerationLog = {
  id: string;
  notebook_id: string;
  message_id: string | null;
  kind: string;
  model: string;
  prompt: string;
  raw_output: string;
  visible_output: string;
  reasoning: string[];
  tool_calls: unknown[];
  extra: Record<string, unknown>;
  latency_ms: number;
  created_at: string;
};

export type HumanScore = {
  human_faithfulness: number | null;
  human_usefulness: number | null;
  human_citation: number | null;
  human_pass: boolean | null;
  human_comment: string;
  reviewer: string;
};

export type EvalItem = {
  id: string;
  run_id: string;
  case_id: string;
  task: string;
  question: string;
  expected_answer: string;
  expected_keywords: string[];
  must_refuse: boolean;
  answer: string;
  citations: { n: number; quote: string }[];
  retrieved: { source_title?: string; text?: string }[];
  latency_ms: number;
  overlap_score: number;
  keyword_hit_rate: number;
  refuse_ok: boolean;
  human_faithfulness: number | null;
  human_usefulness: number | null;
  human_citation: number | null;
  human_pass: boolean | null;
  human_comment: string;
  reviewer: string;
  reviewed_at: string | null;
};

export type EvalRun = {
  id: string;
  provider: string;
  model_id: string;
  status: string;
  metrics: Record<string, number>;
  created_at: string;
  finished_at: string | null;
  items: EvalItem[];
};

export type EvalCompare = {
  a: EvalRun;
  b: EvalRun;
  rows: { case_id: string; question: string; a: EvalItem | null; b: EvalItem | null }[];
};

export async function uploadFile(notebookId: string, file: File): Promise<Source> {
  const data = new FormData();
  data.append("upload", file);
  const response = await fetch(`${BASE}/api/notebooks/${notebookId}/sources/file`, {
    method: "POST",
    body: data,
    credentials: "include",
  });
  if (!response.ok) {
    throw new ApiError(await response.text(), response.status);
  }
  return response.json();
}

export async function streamChat(
  notebookId: string,
  content: string,
  onEvent: (event: Record<string, unknown>) => void,
): Promise<void> {
  const response = await fetch(`${BASE}/api/notebooks/${notebookId}/chat`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  if (!response.ok || !response.body) {
    throw new ApiError(await response.text(), response.status);
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";
    for (const part of parts) {
      const line = part.replace(/^data: /, "");
      if (!line) continue;
      onEvent(JSON.parse(line));
    }
  }
}
