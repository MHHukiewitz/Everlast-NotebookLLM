export type AuthUser = {
  id: string;
  email: string;
  is_demo: boolean;
};

export type Provider = {
  id: string;
  label: string;
  available: boolean;
  notice: string;
  models: { id: string; label: string; provider: string; available: boolean }[];
};

export type Modalities = {
  llm: Provider[];
  tts: Provider[];
  image: Provider[];
};

export type Notebook = {
  id: string;
  title: string;
  provider: string;
  model_id: string;
  tts_provider: string;
  tts_model: string;
  image_provider: string;
  image_model: string;
  eu_notice_accepted: boolean;
  openrouter_notice_accepted: boolean;
  created_at?: string;
  updated_at?: string;
};

export type Source = {
  id: string;
  type: string;
  title: string;
  status: string;
  selected: boolean;
  origin_uri: string | null;
  favicon_url?: string | null;
  content_md: string;
  summary_md: string;
  research_mode: string | null;
  created_at: string;
};

export type Citation = {
  id: string;
  url: string;
  title: string;
  quote: string;
  cited_in_report: boolean;
};

export type SourceDetail = Source & { citations: Citation[] };

export type MessageCitation = {
  n: number;
  source_id?: string;
  chunk_id?: string;
  quote: string;
  url?: string;
  title?: string;
};

export type Message = {
  id: string;
  role: string;
  content: string;
  citations: MessageCitation[];
  tool_calls: unknown[];
  model: string | null;
  created_at: string;
  reasoning?: string[];
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

export type Slide = {
  heading: string;
  bullets: string[];
  notes?: string;
};

export type InfographicItem = {
  label: string;
  value: string;
  detail?: string;
  number?: string;
  suffix?: string;
  caption?: string;
};

export type InfographicPoint = {
  label: string;
  value: number;
};

export type InfographicChart = {
  type: "bar" | "hbar" | "pie" | string;
  title: string;
  unit?: string;
  cite?: string;
  points: InfographicPoint[];
};

export type AudioTurn = {
  speaker: string;
  text: string;
};

export type VideoScene = {
  heading: string;
  bullets: string[];
  narration?: string;
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
  slides?: Slide[];
  items?: InfographicItem[];
  charts?: InfographicChart[];
  turns?: AudioTurn[];
  scenes?: VideoScene[];
  status?: string;
  audio_path?: string;
  video_path?: string;
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
  hint?: string | null;
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
