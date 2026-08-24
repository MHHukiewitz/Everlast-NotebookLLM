import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ModelCard(BaseModel):
    id: str
    label: str
    provider: str
    available: bool
    notice: str | None = None


class ProviderStatus(BaseModel):
    id: str
    label: str
    available: bool
    notice: str
    models: list[ModelCard]


class ModalitiesOut(BaseModel):
    llm: list[ProviderStatus]
    tts: list[ProviderStatus]
    image: list[ProviderStatus]


class NotebookOut(BaseModel):
    id: uuid.UUID
    title: str
    provider: str
    model_id: str
    tts_provider: str
    tts_model: str
    image_provider: str
    image_model: str
    eu_notice_accepted: bool
    openrouter_notice_accepted: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class NotebookUpdate(BaseModel):
    title: str | None = None
    provider: Literal["ollama", "eu", "openrouter"] | None = None
    model_id: str | None = None
    tts_provider: Literal["local", "eu", "openrouter"] | None = None
    tts_model: str | None = None
    image_provider: Literal["local", "eu", "openrouter"] | None = None
    image_model: str | None = None
    eu_notice_accepted: bool | None = None
    openrouter_notice_accepted: bool | None = None


class SourceOut(BaseModel):
    id: uuid.UUID
    type: str
    title: str
    status: str
    selected: bool
    origin_uri: str | None
    favicon_url: str | None = None
    content_md: str
    summary_md: str
    research_mode: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CitationOut(BaseModel):
    id: uuid.UUID
    url: str
    title: str
    quote: str
    cited_in_report: bool

    model_config = {"from_attributes": True}


class SourceDetail(SourceOut):
    citations: list[CitationOut] = Field(default_factory=list)


class AddUrlIn(BaseModel):
    url: str
    title: str | None = None


class AddTextIn(BaseModel):
    title: str
    text: str


class SelectSourceIn(BaseModel):
    selected: bool


class MessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    citations: list[Any]
    tool_calls: list[Any]
    model: str | None
    trace_id: str | None
    reasoning: list[Any] = Field(default_factory=list)
    created_at: datetime

    model_config = {"from_attributes": True}


class GenerationLogOut(BaseModel):
    id: uuid.UUID
    notebook_id: uuid.UUID
    message_id: uuid.UUID | None
    kind: str
    model: str
    prompt: str
    raw_output: str
    visible_output: str
    reasoning: list[Any]
    tool_calls: list[Any]
    extra: dict[str, Any]
    latency_ms: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatIn(BaseModel):
    content: str


class ChatResumeIn(BaseModel):
    job_id: uuid.UUID


class ArtifactOut(BaseModel):
    id: uuid.UUID
    skill_id: str
    type: str
    title: str
    payload: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class NoteIn(BaseModel):
    title: str = "Neue Notiz"
    body: str = ""
    message_id: uuid.UUID | None = None


class SkillCard(BaseModel):
    id: str
    title: str
    description: str
    status: Literal["available", "locked"]
    icon: str
    hint: str | None = None


class SkillRunIn(BaseModel):
    args: dict[str, Any] = Field(default_factory=dict)


class ResearchStartIn(BaseModel):
    query: str
    mode: Literal["fast", "deep"]


class ResearchJobOut(BaseModel):
    id: uuid.UUID
    query: str
    mode: str
    status: str
    progress: str
    report_md: str
    created_at: datetime
    candidates: list[CitationOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ResearchImportIn(BaseModel):
    citation_ids: list[uuid.UUID]
    import_report: bool = True


class RegisterIn(BaseModel):
    email: str
    password: str
    privacy_ack: bool


class LoginIn(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    is_demo: bool

    model_config = {"from_attributes": True}


class EvalStartIn(BaseModel):
    provider: Literal["ollama", "eu", "openrouter"] = "ollama"
    model_id: str = "llama3.2"


class HumanScoreIn(BaseModel):
    human_faithfulness: int | None = None
    human_usefulness: int | None = None
    human_citation: int | None = None
    human_pass: bool | None = None
    human_comment: str = ""
    reviewer: str = "reviewer"


class EvalItemOut(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    case_id: str
    task: str = "chat"
    question: str
    expected_answer: str
    expected_keywords: list[Any]
    must_refuse: bool
    answer: str
    citations: list[Any]
    retrieved: list[Any]
    latency_ms: int
    overlap_score: float
    keyword_hit_rate: float
    refuse_ok: bool
    human_faithfulness: int | None
    human_usefulness: int | None
    human_citation: int | None
    human_pass: bool | None
    human_comment: str
    reviewer: str
    reviewed_at: datetime | None

    model_config = {"from_attributes": True}


class EvalRunOut(BaseModel):
    id: uuid.UUID
    notebook_id: uuid.UUID
    provider: str
    model_id: str
    status: str
    metrics: dict[str, Any]
    created_at: datetime
    finished_at: datetime | None
    items: list[EvalItemOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}
