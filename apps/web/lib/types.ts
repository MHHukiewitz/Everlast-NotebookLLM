export type Provider = {
  id: string;
  label: string;
  available: boolean;
  notice: string;
  models: { id: string; label: string; provider: string; available: boolean }[];
};

export type Notebook = {
  id: string;
  title: string;
  provider: string;
  model_id: string;
  eu_notice_accepted: boolean;
  openrouter_notice_accepted: boolean;
};

export type Source = {
  id: string;
  type: string;
  title: string;
  status: string;
  selected: boolean;
  origin_uri: string | null;
  content_md: string;
  summary_md: string;
  research_mode: string | null;
};

export type Citation = {
  id: string;
  url: string;
  title: string;
  quote: string;
  cited_in_report: boolean;
};

export type SourceDetail = Source & { citations: Citation[] };

export type Message = {
  id: string;
  role: string;
  content: string;
  citations: { n: number; source_id: string; chunk_id: string; quote: string }[];
  tool_calls: unknown[];
  model: string | null;
  created_at: string;
};

export type ArtifactCitation = {
  n: number;
  source_id?: string;
  chunk_id?: string;
  quote?: string;
};

export type QuizQuestion = {
  question: string;
  choices: string[];
  answer_index: number;
  explanation: string;
};

export type Flashcard = {
  front: string;
  back: string;
  cite?: string;
};

export type ArtifactPayload = {
  body?: string;
  body_md?: string;
  mermaid?: string;
  citations?: ArtifactCitation[];
  questions?: QuizQuestion[];
  cards?: Flashcard[];
  columns?: string[];
  rows?: string[][];
};

export type Artifact = {
  id: string;
  skill_id: string;
  type: string;
  title: string;
  payload: ArtifactPayload;
  created_at: string;
};

export type Skill = {
  id: string;
  title: string;
  description: string;
  status: "available" | "locked";
  icon: string;
};

export type ResearchJob = {
  id: string;
  query: string;
  mode: string;
  status: string;
  progress: string;
  report_md: string;
  candidates: Citation[];
};
