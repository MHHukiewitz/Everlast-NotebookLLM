"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CitationChips } from "@/components/CitationChips";
import { MarkdownBody } from "@/components/MarkdownBody";
import { ToolCallCard } from "@/components/chat/ToolCallCard";
import { SiteFooter } from "@/components/SiteFooter";
import { ResizableStages } from "@/components/layout/ResizableStages";
import { NotebookBrowser } from "@/components/notebooks/NotebookBrowser";
import { ArtifactCard } from "@/components/studio/ArtifactCard";
import { StudioRunModal } from "@/components/studio/StudioRunModal";
import { StudioSkillButton } from "@/components/studio/StudioSkillButton";
import { ApiError, api, streamChat, streamChatResume, uploadFile } from "@/lib/api";
import {
  applyChatEvent,
  displayChatText,
  stepsFromReasoning,
  toolCallsFromMessage,
  bindChatCitations,
  type LivePart,
} from "@/lib/chatLive";
import { ThinkingTrace } from "@/components/chat/ThinkingTrace";
import { t } from "@/lib/i18n";
import { ACTIVE_NOTEBOOK_KEY, SOURCE_SORT_KEY } from "@/lib/notebook";
import { panelLocks } from "@/lib/panelLocks";
import { displayUrl, isHttpUrl, sourceFavicon } from "@/lib/source";
import { DEFAULT_SOURCE_SORT, formatSourceSort, parseSourceSort, sortSources, type SourceSort } from "@/lib/sourceSort";
import type {
  Artifact,
  AuthUser,
  Message,
  MessageCitation,
  Modalities,
  Notebook,
  Provider,
  ResearchJob,
  Skill,
  Source,
  SourceDetail,
} from "@/lib/types";

function pickLaneModel(lane: Provider | undefined, current: string) {
  if (lane?.models.some((model) => model.id === current)) return current;
  return lane?.models[0]?.id || current;
}

function SourceIcon({ origin, favicon }: { origin: string | null | undefined; favicon?: string | null }) {
  const [broken, setBroken] = useState(false);
  const src = broken ? "" : sourceFavicon(origin, favicon);
  if (!src) {
    return <span className="mt-0.5 h-8 w-8 shrink-0 rounded-lg bg-mist" aria-hidden />;
  }
  return (
    <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-mist">
      <img
        src={src}
        alt=""
        width={24}
        height={24}
        className="h-6 w-6"
        onError={() => setBroken(true)}
      />
    </span>
  );
}

export default function Page() {
  const [notebook, setNotebook] = useState<Notebook | null>(null);
  const [notebooks, setNotebooks] = useState<Notebook[]>([]);
  const [browseOpen, setBrowseOpen] = useState(false);
  const [sourceSort, setSourceSort] = useState<SourceSort>(DEFAULT_SOURCE_SORT);
  const [sources, setSources] = useState<Source[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [skills, setSkills] = useState<Skill[]>([]);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [studioError, setStudioError] = useState("");
  const [providers, setProviders] = useState<Provider[]>([]);
  const [modalities, setModalities] = useState<Modalities | null>(null);
  const [studioSkill, setStudioSkill] = useState<Skill | null>(null);
  const [pendingStudio, setPendingStudio] = useState<{ skillId: string; title: string; type: string } | null>(null);
  const studioListRef = useRef<HTMLDivElement>(null);
  const chatListRef = useRef<HTMLDivElement>(null);
  const pinChatToBottom = useRef(true);
  const chatSettingsSeq = useRef(0);
  const chatSettingsChoice = useRef<{ provider: string; model_id: string; openrouter_notice_accepted?: boolean } | null>(null);
  const chatSettingsTail = useRef(Promise.resolve());
  const [studioSourceIds, setStudioSourceIds] = useState<string[]>([]);
  const [studioPrompt, setStudioPrompt] = useState("");
  const [mediaFormat, setMediaFormat] = useState<"briefing" | "explainer">("briefing");
  const [mediaLanguage, setMediaLanguage] = useState("de");
  const [mediaStyle, setMediaStyle] = useState("auto");
  const [activeSource, setActiveSource] = useState<SourceDetail | null>(null);
  const [research, setResearch] = useState<ResearchJob | null>(null);
  const [selectedCites, setSelectedCites] = useState<string[]>([]);
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<"fast" | "deep">("fast");
  const [chatInput, setChatInput] = useState("");
  const [liveParts, setLiveParts] = useState<LivePart[]>([]);
  const [liveCitations, setLiveCitations] = useState<MessageCitation[]>([]);
  const [pendingResearchId, setPendingResearchId] = useState<string | null>(null);
  const [chatBusy, setChatBusy] = useState(false);
  const [studioBusy, setStudioBusy] = useState(false);
  const liveSeq = useRef(0);
  const resumeOnce = useRef("");
  const nextLiveId = useCallback(() => {
    liveSeq.current += 1;
    return `live_${liveSeq.current}`;
  }, []);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [noteOpen, setNoteOpen] = useState(false);
  const [noteBody, setNoteBody] = useState("");
  const [textTitle, setTextTitle] = useState("Textquelle");
  const [textBody, setTextBody] = useState("");
  const [urlValue, setUrlValue] = useState("");
  const [euOk, setEuOk] = useState(false);
  const [orOk, setOrOk] = useState(false);
  const [error, setError] = useState("");
  const [addError, setAddError] = useState("");
  const [addBusy, setAddBusy] = useState(false);
  const [researchError, setResearchError] = useState("");
  const [researchBusy, setResearchBusy] = useState(false);
  const [user, setUser] = useState<AuthUser | null>(null);

  const selectedReady = useMemo(
    () => sources.filter((item) => item.selected && item.status === "ready"),
    [sources],
  );
  const selectedCount = selectedReady.length;
  const sortedSources = useMemo(() => sortSources(sources, sourceSort), [sources, sourceSort]);
  const pendingMedia = useMemo(
    () => artifacts.some((artifact) => artifact.payload?.status === "pending"),
    [artifacts],
  );
  const locks = useMemo(
    () => panelLocks({ chatBusy, studioBusy, addBusy, researchBusy }),
    [chatBusy, studioBusy, addBusy, researchBusy],
  );

  const refresh = useCallback(async (id: string) => {
    const [src, msg, art] = await Promise.all([api.sources(id), api.messages(id), api.artifacts(id)]);
    setSources(src);
    setMessages(msg);
    setArtifacts(art);
  }, []);

  const syncNotebook = useCallback(async (id: string) => {
    const next = await api.notebook(id);
    setNotebook(next);
    setNotebooks((list) => {
      const others = list.filter((item) => item.id !== next.id);
      return [next, ...others];
    });
  }, []);

  useEffect(() => {
    let cancelled = false;
    api
      .me()
      .then(async (me) => {
        if (cancelled) return;
        setUser(me);
        const [nbs, sk, pv, md] = await Promise.all([api.notebooks(), api.skills(), api.providers(), api.modalities()]);
        if (cancelled) return;
        setSkills(sk);
        setProviders(pv);
        setModalities(md);
        setNotebooks(nbs);
        setSourceSort(parseSourceSort(window.localStorage.getItem(SOURCE_SORT_KEY)));
        const savedId = window.localStorage.getItem(ACTIVE_NOTEBOOK_KEY);
        const nb = nbs.find((item) => item.id === savedId) || nbs[0] || (await api.createNotebook());
        if (cancelled) return;
        if (!nbs.some((item) => item.id === nb.id)) {
          setNotebooks((list) => [nb, ...list]);
        }
        setNotebook(nb);
        window.localStorage.setItem(ACTIVE_NOTEBOOK_KEY, nb.id);
        setEuOk(nb.eu_notice_accepted);
        setOrOk(nb.openrouter_notice_accepted);
        await refresh(nb.id);
      })
      .catch((err: Error) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          window.location.replace("/login");
          return;
        }
        setError(err.message === "Failed to fetch" ? t.apiOffline : err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [refresh]);

  async function openNotebook(next: Notebook) {
    setNotebook(next);
    window.localStorage.setItem(ACTIVE_NOTEBOOK_KEY, next.id);
    setEuOk(next.eu_notice_accepted);
    setOrOk(next.openrouter_notice_accepted);
    setActiveSource(null);
    setResearch(null);
    setSelectedCites([]);
    setBrowseOpen(false);
    setStudioError("");
    await refresh(next.id);
  }

  async function onCreateNotebook() {
    const created = await api.createNotebook();
    setNotebooks((list) => [created, ...list]);
    await openNotebook(created);
  }

  async function onBrowse() {
    const list = await api.notebooks();
    setNotebooks(list);
    setBrowseOpen(true);
  }

  useEffect(() => {
    if (!notebook || !pendingMedia) return;
    const timer = window.setInterval(() => {
      refresh(notebook.id);
    }, 2500);
    return () => window.clearInterval(timer);
  }, [notebook, pendingMedia, refresh]);

  async function onAddUrl() {
    if (!notebook) return;
    const url = urlValue.trim();
    if (!url) {
      setAddError(t.urlRequired);
      return;
    }
    setAddBusy(true);
    setAddError("");
    const source = await api.addUrl(notebook.id, url).catch((err: Error) => {
      setAddError(err.message === "Failed to fetch" ? t.apiOffline : err.message);
      return null;
    });
    setAddBusy(false);
    if (!source) return;
    setUrlValue("");
    setAddOpen(false);
    await refresh(notebook.id);
    await syncNotebook(notebook.id);
  }

  async function onAddText() {
    if (!notebook) return;
    setAddBusy(true);
    setAddError("");
    const source = await api.addText(notebook.id, textTitle, textBody).catch((err: Error) => {
      setAddError(err.message === "Failed to fetch" ? t.apiOffline : err.message);
      return null;
    });
    setAddBusy(false);
    if (!source) return;
    setTextBody("");
    setAddOpen(false);
    await refresh(notebook.id);
    await syncNotebook(notebook.id);
  }

  async function onFiles(files: FileList | null) {
    if (!notebook || !files) return;
    setAddBusy(true);
    for (const file of Array.from(files)) {
      await uploadFile(notebook.id, file);
    }
    await refresh(notebook.id);
    await syncNotebook(notebook.id);
    setAddBusy(false);
  }

  const researchId = research?.id;
  const researchStatus = research?.status;
  const researchReportMd = research?.report_md ?? "";
  const reportPending = researchStatus === "ready" && !researchReportMd.trim();
  const shouldPollResearch =
    researchStatus === "queued" ||
    researchStatus === "running" ||
    researchStatus === "importing" ||
    reportPending;

  useEffect(() => {
    if (!notebook || !researchId || !shouldPollResearch) return;
    let ticks = 0;
    const timer = window.setInterval(() => {
      ticks += 1;
      if (ticks > 90) {
        if (researchStatus === "importing") {
          setResearchError(t.importTimeout);
          setResearchBusy(false);
        } else if (researchStatus === "queued" || researchStatus === "running") {
          setResearchError(t.searchTimeout);
          setResearchBusy(false);
          setPendingResearchId(null);
          setChatBusy(false);
        }
        window.clearInterval(timer);
        return;
      }
      api
        .researchJob(notebook.id, researchId)
        .then((next) => {
          setResearch(next);
          if (next.status === "ready") {
            setResearchError("");
            setSelectedCites((ids) => (ids.length ? ids : next.candidates.map((c) => c.id)));
            setResearchBusy(false);
            return;
          }
          if (next.status === "imported") {
            setResearch(null);
            setSelectedCites([]);
            setResearchBusy(false);
            void refresh(notebook.id);
            void syncNotebook(notebook.id);
            return;
          }
          if (next.status === "error") {
            setResearchError(next.progress || t.searchTimeout);
            setResearchBusy(false);
            setError(next.progress || t.searchTimeout);
            setPendingResearchId(null);
            setChatBusy(false);
          }
        })
        .catch((err: Error) => {
          setResearchError(err.message === "Failed to fetch" ? t.apiOffline : err.message);
          if (researchStatus === "queued" || researchStatus === "running") {
            setResearchBusy(false);
          }
        });
    }, 1000);
    return () => window.clearInterval(timer);
  }, [notebook, researchId, researchStatus, shouldPollResearch, refresh, syncNotebook]);

  async function onResearch() {
    if (!notebook || researchBusy) return;
    const q = query.trim();
    if (!q) {
      setResearchError(t.searchEmpty);
      return;
    }
    setResearchError("");
    setResearchBusy(true);
    setSelectedCites([]);
    setActiveSource(null);
    const job = await api.research(notebook.id, q, mode).catch((err: Error) => {
      setResearchError(err.message === "Failed to fetch" ? t.apiOffline : err.message);
      return null;
    });
    if (!job) {
      setResearchBusy(false);
      return;
    }
    setResearch(job);
    if (job.status === "ready") {
      setSelectedCites(job.candidates.map((c) => c.id));
      setResearchBusy(false);
    }
    if (job.status === "error") {
      setResearchError(job.progress || t.searchTimeout);
      setResearchBusy(false);
    }
    await syncNotebook(notebook.id);
  }

  function onCancelResearch() {
    setResearch(null);
    setSelectedCites([]);
    setResearchBusy(false);
    setResearchError("");
  }

  async function onDeleteSource(sourceId: string) {
    if (!notebook) return;
    await api.deleteSource(notebook.id, sourceId);
    if (activeSource?.id === sourceId) {
      setActiveSource(null);
    }
    await refresh(notebook.id);
  }

  async function onImport() {
    if (!notebook || !research || researchBusy) return;
    setResearchError("");
    setResearchBusy(true);
    const job = await api.importResearch(notebook.id, research.id, selectedCites, true).catch((err: Error) => {
      setResearchError(err.message === "Failed to fetch" ? t.apiOffline : err.message);
      return null;
    });
    if (!job) {
      setResearchBusy(false);
      return;
    }
    setResearch(job);
  }

  const researchReadyId = research?.status === "ready" ? research.id : "";

  useEffect(() => {
    if (!notebook || !pendingResearchId || !researchReadyId) return;
    if (researchReadyId !== pendingResearchId) return;
    if (resumeOnce.current === researchReadyId) return;
    resumeOnce.current = researchReadyId;
    streamChatResume(notebook.id, researchReadyId, (event) => {
      if (event.event === "warning") {
        setError(String(event.text || ""));
      }
      if ((event.event === "meta" || event.event === "done") && Array.isArray(event.citations)) {
        setLiveCitations(event.citations as MessageCitation[]);
      }
      setLiveParts((parts) => applyChatEvent(parts, event, nextLiveId));
    }).then(async () => {
      await refresh(notebook.id);
      await syncNotebook(notebook.id);
      setLiveParts([]);
      setLiveCitations([]);
      setPendingResearchId(null);
      setChatBusy(false);
    });
  }, [notebook, pendingResearchId, researchReadyId, nextLiveId, refresh, syncNotebook]);

  function onCancelChatResearch() {
    setPendingResearchId(null);
    setResearchBusy(false);
    setChatBusy(false);
    if (notebook) {
      void refresh(notebook.id);
    }
    setLiveParts([]);
    setLiveCitations([]);
  }

  function openCite(cite: MessageCitation) {
    if (!notebook) return;
    if (cite.source_id) {
      api.source(notebook.id, cite.source_id).then(setActiveSource);
      return;
    }
    if (cite.url) {
      window.open(cite.url, "_blank", "noopener,noreferrer");
    }
  }

  function scrollChatToBottom() {
    const scroller = chatListRef.current;
    if (!scroller || !pinChatToBottom.current) return;
    scroller.scrollTop = scroller.scrollHeight;
  }

  function onChatScroll() {
    const scroller = chatListRef.current;
    if (!scroller) return;
    pinChatToBottom.current = scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight <= 80;
  }

  useEffect(() => {
    if (!pinChatToBottom.current) return;
    scrollChatToBottom();
    const frame = window.requestAnimationFrame(scrollChatToBottom);
    return () => window.cancelAnimationFrame(frame);
  }, [messages, liveParts, chatBusy]);

  async function onSend(text?: string) {
    if (!notebook || chatBusy) return;
    const content = (text || chatInput).trim();
    if (!content) return;
    pinChatToBottom.current = true;
    setChatInput("");
    setLiveParts([]);
    setLiveCitations([]);
    setError("");
    setChatBusy(true);
    setMessages((prev) => [
      ...prev,
      { id: "tmp-user", role: "user", content, citations: [], tool_calls: [], model: null, created_at: new Date().toISOString() },
    ]);
    let waiting = false;
    await streamChat(notebook.id, content, (event) => {
      if (event.event === "warning") {
        setError(String(event.text || ""));
      }
      if ((event.event === "meta" || event.event === "done") && Array.isArray(event.citations)) {
        setLiveCitations(event.citations as MessageCitation[]);
      }
      setLiveParts((parts) => applyChatEvent(parts, event, nextLiveId));
      if (event.event === "research_pending" || event.research_pending) {
        waiting = true;
        const jobId = String(event.job_id || "");
        setPendingResearchId(jobId);
        setResearch({
          id: jobId,
          query: String(event.query || content),
          mode: String(event.mode || "fast"),
          status: "queued",
          progress: t.searching,
          report_md: "",
          candidates: [],
        });
        setResearchBusy(true);
        setSelectedCites([]);
        setActiveSource(null);
      }
    });
    if (waiting) return;
    await refresh(notebook.id);
    await syncNotebook(notebook.id);
    setLiveParts([]);
    setLiveCitations([]);
    setChatBusy(false);
  }

  const llmLanes = modalities?.llm || providers;
  const hetznerLane = llmLanes.find((lane) => lane.id === "hetzner");
  const openrouterLane = llmLanes.find((lane) => lane.id === "openrouter");
  const chatLane = llmLanes.find((lane) => lane.id === notebook?.provider);

  function providerLabel(id: string) {
    if (id === "ollama") return t.local;
    if (id === "hetzner") return t.hetzner;
    if (id === "eu") return t.eu;
    return t.openrouter;
  }

  function providerHint(id: string) {
    if (id === "hetzner") return t.hetznerHint;
    if (id === "openrouter") return t.openrouterHint;
    return undefined;
  }

  async function writeChatSettings(choice: { provider: string; model_id: string; openrouter_notice_accepted?: boolean }) {
    if (!notebook) return;
    chatSettingsChoice.current = choice;
    const seq = ++chatSettingsSeq.current;
    const notebookId = notebook.id;
    const previous = chatSettingsTail.current;
    let release = () => {};
    chatSettingsTail.current = new Promise<void>((resolve) => {
      release = resolve;
    });
    await previous;
    if (seq !== chatSettingsSeq.current) {
      release();
      return;
    }
    const latest = chatSettingsChoice.current || choice;
    const saved = await api.updateNotebook(notebookId, {
      provider: latest.provider,
      model_id: latest.model_id,
      openrouter_notice_accepted: latest.openrouter_notice_accepted,
    });
    if (seq === chatSettingsSeq.current) setNotebook(saved);
    release();
  }

  async function onChatModel(model: string) {
    if (!notebook) return;
    const currentModel = chatSettingsChoice.current?.model_id || notebook.model_id;
    if (currentModel === model) return;
    const provider = chatSettingsChoice.current?.provider || notebook.provider;
    setNotebook({ ...notebook, provider, model_id: model });
    await writeChatSettings({ provider, model_id: model });
  }

  async function onInference(provider: "ollama" | "hetzner" | "openrouter") {
    if (!notebook) return;
    const currentProvider = chatSettingsChoice.current?.provider || notebook.provider;
    if (currentProvider === provider) return;
    const lane = llmLanes.find((item) => item.id === provider);
    const model = pickLaneModel(lane, notebook.model_id);
    const next = {
      ...notebook,
      provider,
      model_id: model,
      openrouter_notice_accepted: provider === "openrouter" ? true : notebook.openrouter_notice_accepted,
    };
    if (provider === "openrouter") setOrOk(true);
    setNotebook(next);
    await writeChatSettings({
      provider,
      model_id: model,
      openrouter_notice_accepted: provider === "openrouter" ? true : undefined,
    });
  }

  async function saveSettings() {
    if (!notebook) return;
    const next = await api.updateNotebook(notebook.id, {
      provider: notebook.provider,
      model_id: notebook.model_id,
      tts_provider: notebook.tts_provider,
      tts_model: notebook.tts_model,
      image_provider: notebook.image_provider,
      image_model: notebook.image_model,
      title: notebook.title,
      eu_notice_accepted: euOk,
      openrouter_notice_accepted: orOk,
    });
    setNotebook(next);
    setSettingsOpen(false);
  }

  async function onRunSkill(skill: Skill) {
    if (studioBusy) return;
    if (skill.id === "notes.create") {
      setNoteOpen(true);
      return;
    }
    const ready = sources.filter((source) => source.status === "ready");
    if (ready.length === 0) {
      setStudioError(t.studioNoSources);
      return;
    }
    const selected = ready.filter((source) => source.selected).map((source) => source.id);
    setStudioSkill(skill);
    setStudioSourceIds(selected.length > 0 ? selected : ready.map((source) => source.id));
    setStudioPrompt("");
    setMediaFormat("briefing");
    setMediaLanguage("de");
    setMediaStyle("auto");
    setStudioError("");
  }

  async function onCreateStudio() {
    if (!notebook || !studioSkill || studioBusy) return;
    if (studioSourceIds.length === 0) {
      setStudioError(t.studioNoSources);
      return;
    }
    const skill = studioSkill;
    const args = {
      prompt: studioPrompt,
      source_ids: studioSourceIds,
      format: mediaFormat,
      language: mediaLanguage,
      style: mediaStyle,
    };
    setStudioSkill(null);
    setStudioError("");
    setStudioBusy(true);
    setPendingStudio({
      skillId: skill.id,
      title: skill.title,
      type: skill.id.startsWith("studio.") ? skill.id.slice(7) : skill.id,
    });
    studioListRef.current?.scrollTo({ top: 0 });
    const result = await api.runSkill(notebook.id, skill.id, args).catch((err: Error) => {
      setStudioError(err.message);
      return null;
    });
    if (result) {
      await refresh(notebook.id);
      await syncNotebook(notebook.id);
    }
    setPendingStudio(null);
    setStudioBusy(false);
  }

  if (!notebook) {
    return (
      <div className="p-8 text-sm text-neutral-600">
        <p>{error || t.loading}</p>
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col">
      <header className="flex items-center justify-between border-b border-line px-4 py-2">
        <div className="flex items-center gap-3">
          <button
            className="flex h-8 w-8 items-center justify-center rounded-full bg-ink text-sm text-white"
            title={t.browseNotebooks}
            onClick={onBrowse}
          >
            en
          </button>
          <input
            className="bg-transparent text-lg font-medium outline-none"
            value={notebook.title}
            onChange={(e) => setNotebook({ ...notebook, title: e.target.value })}
            onBlur={() => api.updateNotebook(notebook.id, { title: notebook.title })}
          />
        </div>
        <div className="flex items-center gap-2">
          <button className="rounded-full bg-ink px-3 py-1.5 text-sm text-white" onClick={onCreateNotebook}>
            + {t.createNotebook}
          </button>
          <button className="btn" onClick={onBrowse}>
            {t.notebooks}
          </button>
          <div className="flex items-center gap-2">
            <div className="flex rounded-full bg-mist p-0.5 text-xs" role="group" aria-label={t.chatModel}>
              <button
                type="button"
                className={`rounded-full px-2.5 py-1 ${notebook.provider === "ollama" ? "bg-white font-medium text-ink" : "text-neutral-500"}`}
                onClick={() => onInference("ollama")}
              >
                {t.local}
              </button>
              <button
                type="button"
                className={`rounded-full px-2.5 py-1 ${notebook.provider === "hetzner" ? "bg-white font-medium text-ink" : "text-neutral-500"}`}
                disabled={!hetznerLane?.available}
                title={hetznerLane?.notice || t.hetznerHint}
                onClick={() => onInference("hetzner")}
              >
                {t.hetzner}
              </button>
              <button
                type="button"
                className={`rounded-full px-2.5 py-1 ${notebook.provider === "openrouter" ? "bg-white font-medium text-ink" : "text-neutral-500"}`}
                disabled={!openrouterLane?.available}
                title={openrouterLane?.notice || t.openrouterHint}
                onClick={() => onInference("openrouter")}
              >
                {t.openrouter}
              </button>
            </div>
            <select
              className="max-w-48 rounded-full bg-mist px-3 py-1 text-xs"
              aria-label={t.modelSelect}
              title={providerHint(notebook.provider)}
              disabled={!chatLane?.available || chatLane.models.length === 0}
              value={pickLaneModel(chatLane, notebook.model_id)}
              onChange={(e) => onChatModel(e.target.value)}
            >
              {(chatLane?.models || []).map((model) => (
                <option key={model.id} value={model.id}>
                  {providerLabel(notebook.provider)} · {model.label}
                </option>
              ))}
            </select>
          </div>
          <a className="btn" href="/eval">
            Eval
          </a>
          <button className="btn" onClick={() => setSettingsOpen(true)}>
            {t.settings}
          </button>
          {user ? <span className="text-xs text-neutral-500">{user.email}</span> : null}
          <button
            className="btn"
            onClick={async () => {
              await api.logout();
              window.location.replace("/login");
            }}
          >
            {t.logout}
          </button>
        </div>
      </header>
      <p className="border-b border-line bg-mist px-4 py-1 text-xs text-neutral-600">{t.aiBanner}</p>

      <ResizableStages
        sources={
        <section className="panel">
          <div className="flex items-center justify-between gap-2 px-4 py-3">
            <h2 className="font-medium">{t.sources}</h2>
            {sources.length > 1 && (
              <div className="flex items-center gap-1">
                <label className="sr-only" htmlFor="source-sort">
                  {t.sortBy}
                </label>
                <select
                  id="source-sort"
                  className="max-w-[7.5rem] rounded-full border border-line bg-white px-2 py-1 text-xs"
                  value={sourceSort.key}
                  onChange={(e) => {
                    const key = e.target.value as SourceSort["key"];
                    const next = { ...sourceSort, key };
                    setSourceSort(next);
                    window.localStorage.setItem(SOURCE_SORT_KEY, formatSourceSort(next));
                  }}
                >
                  <option value="created">{t.sortCreated}</option>
                  <option value="title">{t.sortTitle}</option>
                  <option value="type">{t.sortType}</option>
                </select>
                <button
                  className="rounded-full border border-line px-2 py-1 text-xs"
                  title={sourceSort.dir === "asc" ? t.sortAsc : t.sortDesc}
                  onClick={() => {
                    const next = { ...sourceSort, dir: sourceSort.dir === "asc" ? "desc" : "asc" } as SourceSort;
                    setSourceSort(next);
                    window.localStorage.setItem(SOURCE_SORT_KEY, formatSourceSort(next));
                  }}
                >
                  {sourceSort.dir === "asc" ? "↑" : "↓"}
                </button>
              </div>
            )}
          </div>
          <div className="px-4">
            <button className="btn-primary w-full" onClick={() => setAddOpen(true)}>
              + {t.addSources}
            </button>
            <div className="mt-3 flex gap-2">
              <input
                className="w-full rounded-full border border-line px-3 py-2 text-sm"
                placeholder={t.searchWeb}
                value={query}
                disabled={locks.sourceResearchDisabled}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    onResearch();
                  }
                }}
              />
              <button className="btn" disabled={locks.sourceResearchDisabled} onClick={onResearch}>
                {researchBusy ? t.searching : t.searchStart}
              </button>
            </div>
            <div className="mt-2 flex gap-2 text-xs">
              <span className="chip">{t.web}</span>
              <select
                className="chip bg-white"
                value={mode}
                disabled={locks.sourceResearchDisabled}
                onChange={(e) => setMode(e.target.value as "fast" | "deep")}
              >
                <option value="fast">{t.fast}</option>
                <option value="deep">{t.deep}</option>
              </select>
            </div>
            {researchError && <p className="mt-2 text-xs text-red-600">{researchError}</p>}
            {researchBusy && <p className="mt-2 text-xs text-neutral-500">{research?.progress || t.searching}</p>}
          </div>
          <div
            className="mt-4 min-h-0 flex-1 overflow-auto px-4 pb-4"
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              onFiles(e.dataTransfer.files);
            }}
          >
            {research && (research.status === "queued" || research.status === "running") ? (
              <div className="flex h-full flex-col items-center justify-center text-center text-sm text-neutral-500">
                <p>{research.progress || t.searching}</p>
                <p className="mt-1">{research.query}</p>
                <button className="mt-4 text-xs text-accent" onClick={onCancelResearch}>
                  {t.cancelResearch}
                </button>
              </div>
            ) : research && (research.status === "ready" || research.status === "importing") ? (
              <div className="space-y-3 text-sm">
                <button className="text-xs text-accent" onClick={onCancelResearch}>
                  ← {t.cancelResearch}
                </button>
                {research.report_md.trim() ? (
                  <MarkdownBody>{research.report_md}</MarkdownBody>
                ) : (
                  <p className="text-xs text-neutral-500">{t.reportPending}</p>
                )}
                <p className="font-medium">{t.cited}</p>
                {research.candidates.filter((c) => c.cited_in_report).map((c) => (
                  <label key={c.id} className="flex items-start gap-2">
                    <input
                      type="checkbox"
                      className="mt-1"
                      checked={selectedCites.includes(c.id)}
                      disabled={locks.sourceResearchDisabled}
                      onChange={() =>
                        setSelectedCites((ids) => (ids.includes(c.id) ? ids.filter((x) => x !== c.id) : [...ids, c.id]))
                      }
                    />
                    <SourceIcon origin={c.url} />
                    <span>
                      <span className="block">{c.title}</span>
                      {isHttpUrl(c.url) && (
                        <span className="block break-all text-xs text-neutral-500">{displayUrl(c.url)}</span>
                      )}
                    </span>
                  </label>
                ))}
                <p className="font-medium">{t.notCited}</p>
                {research.candidates.filter((c) => !c.cited_in_report).map((c) => (
                  <label key={c.id} className="flex items-start gap-2">
                    <input
                      type="checkbox"
                      className="mt-1"
                      checked={selectedCites.includes(c.id)}
                      disabled={locks.sourceResearchDisabled}
                      onChange={() =>
                        setSelectedCites((ids) => (ids.includes(c.id) ? ids.filter((x) => x !== c.id) : [...ids, c.id]))
                      }
                    />
                    <SourceIcon origin={c.url} />
                    <span>
                      <span className="block">{c.title}</span>
                      {isHttpUrl(c.url) && (
                        <span className="block break-all text-xs text-neutral-500">{displayUrl(c.url)}</span>
                      )}
                    </span>
                  </label>
                ))}
                <button className="btn-primary" disabled={locks.sourceResearchDisabled} onClick={onImport}>
                  {researchBusy ? t.importing : t.import}
                </button>
              </div>
            ) : activeSource ? (
              <div className="space-y-3 text-sm">
                <button className="text-xs text-accent" onClick={() => setActiveSource(null)}>
                  ← {t.sources}
                </button>
                <div className="flex items-start gap-2">
                  <SourceIcon origin={activeSource.origin_uri} favicon={activeSource.favicon_url} />
                  <div>
                    <h3 className="font-medium">{activeSource.title}</h3>
                    {isHttpUrl(activeSource.origin_uri) && (
                      <a
                        className="break-all text-xs text-accent"
                        href={activeSource.origin_uri}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {displayUrl(activeSource.origin_uri)}
                      </a>
                    )}
                  </div>
                </div>
                <MarkdownBody>{activeSource.summary_md || activeSource.content_md}</MarkdownBody>
                <div className="flex flex-wrap gap-2">
                  <a className="btn-primary inline-block" href={api.pdfUrl(notebook.id, activeSource.id)}>
                    {t.downloadPdf}
                  </a>
                  <button className="btn" onClick={() => onDeleteSource(activeSource.id)}>
                    {t.removeSource}
                  </button>
                </div>
                <ul className="space-y-1 text-xs">
                  {activeSource.citations.map((c) => (
                    <li key={c.id}>
                      <a className="text-accent" href={c.url} target="_blank" rel="noreferrer">
                        {c.title || c.url}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            ) : sources.length === 0 ? (
              <div className="flex h-full flex-col items-center justify-center text-center text-sm text-neutral-500">
                <p>{t.emptySources}</p>
                <p className="mt-2">{t.emptySourcesHint}</p>
                <label className="mt-6 cursor-pointer text-accent">
                  {t.drop}
                  <input type="file" className="hidden" multiple accept={t.uploadAccept} onChange={(e) => onFiles(e.target.files)} />
                </label>
              </div>
            ) : (
              <ul className="space-y-2">
                {sortedSources.map((source) => (
                  <li key={source.id} className="flex items-start gap-2 rounded-lg border border-line p-2 text-sm">
                    <input
                      type="checkbox"
                      className="mt-1"
                      checked={source.selected}
                      onChange={() => api.selectSource(notebook.id, source.id, !source.selected).then(() => refresh(notebook.id))}
                    />
                    <SourceIcon origin={source.origin_uri} favicon={source.favicon_url} />
                    <button className="min-w-0 flex-1 text-left" onClick={() => api.source(notebook.id, source.id).then(setActiveSource)}>
                      <div className="font-medium">{source.title}</div>
                      {isHttpUrl(source.origin_uri) ? (
                        <div className="break-all text-xs text-neutral-500">{displayUrl(source.origin_uri)}</div>
                      ) : (
                        <div className="text-xs text-neutral-500">{source.type} · {source.status}</div>
                      )}
                      {source.created_at && (
                        <div className="text-[11px] text-neutral-400">
                          {new Date(source.created_at).toLocaleString("de-DE", {
                            day: "2-digit",
                            month: "2-digit",
                            year: "numeric",
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </div>
                      )}
                    </button>
                    <button
                      className="mt-0.5 shrink-0 px-1 text-neutral-400 hover:text-red-600"
                      title={t.removeSource}
                      onClick={() => onDeleteSource(source.id)}
                    >
                      ×
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>
        }
        chat={
        <section className="panel">
          <div className="flex items-center justify-between px-4 py-3">
            <h2 className="font-medium">{t.chat}</h2>
          </div>
          <div ref={chatListRef} className="min-h-0 flex-1 overflow-auto px-6" onScroll={onChatScroll}>
            {messages.length === 0 && liveParts.length === 0 ? (
              <div className="mx-auto max-w-xl pt-16 text-center">
                <h3 className="text-2xl font-medium">{t.setup}</h3>
                <p className="mt-2 text-sm text-neutral-500">{t.setupHint}</p>
                <div className="mt-6 flex flex-wrap justify-center gap-2">
                  <button className="chip" onClick={() => onSend(t.promptTopic)}>
                    {t.promptTopic}
                  </button>
                  <button className="chip" onClick={() => onSend(t.promptCreate)}>
                    {t.promptCreate}
                  </button>
                  <button className="chip" onClick={() => onSend(t.promptAdvance)}>
                    {t.promptAdvance}
                  </button>
                </div>
              </div>
            ) : (
              <div className="mx-auto max-w-2xl space-y-4 py-4">
                {messages.map((message) => (
                  <article key={message.id} className={message.role === "user" ? "text-right" : ""}>
                    <div className={`inline-block max-w-full rounded-2xl px-4 py-3 text-sm ${message.role === "user" ? "bg-mist" : "bg-white"}`}>
                      {message.role === "assistant" && (
                        <ThinkingTrace
                          steps={stepsFromReasoning(message.reasoning)}
                          tools={toolCallsFromMessage(message.tool_calls)}
                        />
                      )}
                      {message.role === "assistant" &&
                        toolCallsFromMessage(message.tool_calls)
                          .filter((tool) => !stepsFromReasoning(message.reasoning).some((step) => step.call_id === tool.call_id))
                          .map((tool) => <ToolCallCard key={tool.call_id} tool={tool} />)}
                      {message.content ? (
                        <MarkdownBody
                          citations={bindChatCitations(
                            displayChatText(message.content),
                            message.citations,
                            selectedReady,
                          )}
                          onCite={openCite}
                        >
                          {displayChatText(message.content)}
                        </MarkdownBody>
                      ) : null}
                      {message.role === "assistant" ? (
                        <CitationChips
                          citations={bindChatCitations(
                            displayChatText(message.content),
                            message.citations,
                            selectedReady,
                          )}
                          onCite={openCite}
                        />
                      ) : null}
                      {message.role === "assistant" && (
                        <button
                          className="mt-2 text-xs text-accent"
                          onClick={() =>
                            api.createNote(notebook.id, t.newNote, displayChatText(message.content), message.id).then(async () => {
                              await refresh(notebook.id);
                              await syncNotebook(notebook.id);
                            })
                          }
                        >
                          {t.saveNote}
                        </button>
                      )}
                    </div>
                  </article>
                ))}
                {(chatBusy || liveParts.length > 0) && (
                  <article>
                    <div className="rounded-2xl bg-white px-4 py-3 text-sm">
                      {pendingResearchId && <p className="mb-2 text-xs text-neutral-500">{t.researchWait}</p>}
                      {!liveParts.some((part) => part.kind === "step") && (
                        <div className="thinking" aria-label={t.thinking} role="status">
                          <span className="thinking-dot" />
                          <span className="thinking-dot" />
                          <span className="thinking-dot" />
                        </div>
                      )}
                      <ThinkingTrace
                        steps={liveParts.filter((part): part is Extract<LivePart, { kind: "step" }> => part.kind === "step").map((part) => part.step)}
                        tools={liveParts.filter((part): part is Extract<LivePart, { kind: "tool" }> => part.kind === "tool").map((part) => part.tool)}
                        think={liveParts
                          .filter((part): part is Extract<LivePart, { kind: "think" }> => part.kind === "think")
                          .map((part) => part.text)
                          .join("")}
                        busy={chatBusy}
                      />
                      {liveParts
                        .filter((part): part is Extract<LivePart, { kind: "text" }> => part.kind === "text")
                        .map((part) => {
                          const liveText = displayChatText(part.text);
                          return (
                            <MarkdownBody
                              key={part.id}
                              citations={bindChatCitations(liveText, liveCitations, selectedReady)}
                              onCite={openCite}
                            >
                              {liveText}
                            </MarkdownBody>
                          );
                        })}
                      <CitationChips
                        citations={bindChatCitations(
                          displayChatText(
                            liveParts
                              .filter((part): part is Extract<LivePart, { kind: "text" }> => part.kind === "text")
                              .map((part) => part.text)
                              .join(""),
                          ),
                          liveCitations,
                          selectedReady,
                        )}
                        onCite={openCite}
                      />
                    </div>
                  </article>
                )}
              </div>
            )}
          </div>
          <div className="border-t border-line p-4">
            {error && <p className="mb-2 text-xs text-red-600">{error}</p>}
            <div className="rounded-2xl border border-line p-3">
              <textarea
                className="h-16 w-full resize-none outline-none"
                placeholder={t.ask}
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    if (!locks.chatSendDisabled) onSend();
                  }
                }}
              />
              <div className="flex items-center justify-between">
                <label className="cursor-pointer text-neutral-400">
                  📎
                  <input type="file" className="hidden" accept={t.uploadAccept} onChange={(e) => onFiles(e.target.files)} />
                </label>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-neutral-500">{t.sourcesCount(selectedCount)}</span>
                  {pendingResearchId && (
                    <button className="btn" type="button" onClick={onCancelChatResearch}>
                      {t.cancelChat}
                    </button>
                  )}
                  <button className="btn-primary" disabled={locks.chatSendDisabled} onClick={() => onSend()}>
                    →
                  </button>
                </div>
              </div>
            </div>
          </div>
        </section>
        }
        studio={
        <section className="panel border-r-0">
          <div className="px-4 py-3">
            <h2 className="font-medium">{t.studio}</h2>
          </div>
          <div ref={studioListRef} className="min-h-0 flex-1 overflow-auto px-4 py-3 text-sm">
            <div className="studio-skills">
              {skills.map((skill) => (
                <StudioSkillButton
                  key={skill.id}
                  skill={skill}
                  busy={locks.studioSkillsDisabled}
                  active={
                    pendingStudio?.skillId === skill.id ||
                    (!pendingStudio && artifacts[0]?.skill_id === skill.id)
                  }
                  onRun={onRunSkill}
                />
              ))}
            </div>
            {studioError && <p className="mb-3 text-xs text-red-600">{studioError}</p>}
            {artifacts.length === 0 && !pendingStudio ? (
              <p className="text-neutral-500">
                {t.studioEmpty} {t.studioHint}
              </p>
            ) : (
              <ul className="space-y-2">
                {pendingStudio && (
                  <ArtifactCard
                    artifact={{
                      id: "pending-studio",
                      skill_id: pendingStudio.skillId,
                      type: pendingStudio.type,
                      title: pendingStudio.title,
                      payload: { status: "pending" },
                      created_at: "",
                    }}
                    notebookId={notebook.id}
                    loading
                  />
                )}
                {artifacts.map((artifact) => (
                  <ArtifactCard
                    key={artifact.id}
                    artifact={artifact}
                    notebookId={notebook.id}
                    sources={sources}
                    onCite={openCite}
                    onImported={async () => {
                      await refresh(notebook.id);
                      await syncNotebook(notebook.id);
                    }}
                    onDeleted={() => {
                      setArtifacts((list) => list.filter((item) => item.id !== artifact.id));
                    }}
                  />
                ))}
              </ul>
            )}
          </div>
          <div className="border-t border-line p-4">
            <button className="btn-primary w-full" onClick={() => setNoteOpen(true)}>
              + {t.addNote}
            </button>
          </div>
        </section>
        }
      />
      <SiteFooter extra={t.footer} />
      {browseOpen && (
        <NotebookBrowser
          notebooks={notebooks}
          activeId={notebook.id}
          onOpen={openNotebook}
          onCreate={onCreateNotebook}
          onClose={() => setBrowseOpen(false)}
        />
      )}

      {addOpen && (
        <Modal title={t.addSources} onClose={() => !locks.sourceAddDisabled && setAddOpen(false)}>
          {addError && <p className="mb-3 text-sm text-red-600">{addError}</p>}
          <label className="text-sm">{t.addUrl}</label>
          <input
            className="mt-1 w-full rounded border border-line px-2 py-1"
            value={urlValue}
            placeholder={t.urlPlaceholder}
            disabled={locks.sourceAddDisabled}
            onChange={(e) => setUrlValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                onAddUrl();
              }
            }}
          />
          <button className="btn-primary mt-2" disabled={locks.sourceAddDisabled} onClick={onAddUrl}>
            {addBusy ? t.addingUrl : t.addUrl}
          </button>
          <hr className="my-4" />
          <label className="text-sm">{t.pasteText}</label>
          <input className="mt-1 w-full rounded border border-line px-2 py-1" value={textTitle} disabled={locks.sourceAddDisabled} onChange={(e) => setTextTitle(e.target.value)} />
          <textarea className="mt-2 h-28 w-full rounded border border-line p-2" value={textBody} disabled={locks.sourceAddDisabled} onChange={(e) => setTextBody(e.target.value)} />
          <button className="btn-primary mt-2" disabled={locks.sourceAddDisabled} onClick={onAddText}>
            {addBusy ? t.addingText : t.pasteText}
          </button>
          <hr className="my-4" />
          <label className="btn cursor-pointer">
            {t.upload}
            <input type="file" className="hidden" multiple accept={t.uploadAccept} disabled={locks.sourceAddDisabled} onChange={(e) => onFiles(e.target.files).then(() => setAddOpen(false))} />
          </label>
          <p className="mt-2 text-xs text-neutral-500">{t.uploadHint}</p>
        </Modal>
      )}

      {studioSkill && (
        <StudioRunModal
          skill={studioSkill}
          sources={sources}
          sourceIds={studioSourceIds}
          prompt={studioPrompt}
          format={mediaFormat}
          language={mediaLanguage}
          style={mediaStyle}
          busy={locks.studioModalLocked}
          error={studioError}
          onClose={() => !locks.studioModalLocked && setStudioSkill(null)}
          onSourceIds={setStudioSourceIds}
          onPrompt={setStudioPrompt}
          onFormat={setMediaFormat}
          onLanguage={setMediaLanguage}
          onStyle={setMediaStyle}
          onCreate={onCreateStudio}
        />
      )}

      {noteOpen && (
        <Modal title={t.newNote} onClose={() => setNoteOpen(false)}>
          <textarea className="h-40 w-full rounded border border-line p-2" value={noteBody} onChange={(e) => setNoteBody(e.target.value)} />
          <button
            className="btn-primary mt-3"
            onClick={async () => {
              await api.createNote(notebook.id, t.newNote, noteBody);
              setNoteBody("");
              setNoteOpen(false);
              await refresh(notebook.id);
              await syncNotebook(notebook.id);
            }}
          >
            {t.addNote}
          </button>
        </Modal>
      )}

      {settingsOpen && (
        <Modal title={t.settings} onClose={() => setSettingsOpen(false)}>
          <div className="space-y-3 text-sm">
            <ModalityBlock
              title={t.chatModel}
              lanes={modalities?.llm || providers}
              provider={notebook.provider}
              modelId={notebook.model_id}
              name="llm"
              onProvider={(id, model) => setNotebook({ ...notebook, provider: id, model_id: model })}
              onModel={(model) => void onChatModel(model)}
            />
            <ModalityBlock
              title={t.speechModel}
              lanes={modalities?.tts || []}
              provider={notebook.tts_provider || "local"}
              modelId={notebook.tts_model || ""}
              name="tts"
              onProvider={(id, model) => setNotebook({ ...notebook, tts_provider: id, tts_model: model })}
              onModel={(model) => setNotebook({ ...notebook, tts_model: model })}
            />
            <ModalityBlock
              title={t.imageModel}
              lanes={modalities?.image || []}
              provider={notebook.image_provider || "local"}
              modelId={notebook.image_model || ""}
              name="image"
              onProvider={(id, model) => setNotebook({ ...notebook, image_provider: id, image_model: model })}
              onModel={(model) => setNotebook({ ...notebook, image_model: model })}
            />
            <label className="flex gap-2 text-xs">
              <input type="checkbox" checked={euOk} onChange={(e) => setEuOk(e.target.checked)} />
              {t.acceptEu}
            </label>
            <label className="flex gap-2 text-xs">
              <input type="checkbox" checked={orOk} onChange={(e) => setOrOk(e.target.checked)} />
              {t.acceptOr}
            </label>
            <button className="btn-primary" onClick={saveSettings}>
              {t.save}
            </button>
            <button
              className="btn"
              onClick={async () => {
                const data = await api.exportNotebook(notebook.id);
                const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
                const url = URL.createObjectURL(blob);
                const link = document.createElement("a");
                link.href = url;
                link.download = "notebook-export.json";
                link.click();
              }}
            >
              Export
            </button>
            <button
              className="btn"
              onClick={async () => {
                await api.eraseNotebook(notebook.id);
                const remaining = notebooks.filter((item) => item.id !== notebook.id);
                if (remaining[0]) {
                  setNotebooks(remaining);
                  await openNotebook(remaining[0]);
                } else {
                  const created = await api.createNotebook();
                  setNotebooks([created]);
                  await openNotebook(created);
                }
                setSettingsOpen(false);
              }}
            >
              Löschen
            </button>
            {user && !user.is_demo ? (
              <button
                className="btn"
                onClick={async () => {
                  await api.deleteAccount();
                  window.location.replace("/login");
                }}
              >
                {t.deleteAccount}
              </button>
            ) : null}
          </div>
        </Modal>
      )}
    </div>
  );
}

function ModalityBlock({
  title,
  lanes,
  provider,
  modelId,
  name,
  onProvider,
  onModel,
}: {
  title: string;
  lanes: Provider[];
  provider: string;
  modelId: string;
  name: string;
  onProvider: (id: string, model: string) => void;
  onModel: (model: string) => void;
}) {
  return (
    <div>
      <p className="mb-2 font-medium">{title}</p>
      <div className="space-y-2">
        {lanes.map((lane) => (
          <div key={`${name}-${lane.id}`} className="rounded-lg border border-line p-3">
            <label className="flex items-center gap-2 font-medium">
              <input
                type="radio"
                name={name}
                checked={provider === lane.id}
                disabled={!lane.available}
                onChange={() => onProvider(lane.id, pickLaneModel(lane, modelId))}
              />
              {lane.label}
            </label>
            <p className="mt-1 text-xs text-neutral-500">{lane.notice}</p>
            {provider === lane.id && (
              <select
                className="mt-2 w-full rounded border border-line p-1"
                aria-label={t.modelSelect}
                value={pickLaneModel(lane, modelId)}
                disabled={!lane.available || lane.models.length === 0}
                onChange={(e) => onModel(e.target.value)}
              >
                {lane.models.map((model) => (
                  <option key={model.id} value={model.id}>
                    {model.label}
                  </option>
                ))}
              </select>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-20 flex items-center justify-center bg-black/30 p-4">
      <div className="max-h-[80vh] w-full max-w-lg overflow-auto rounded-2xl bg-white p-5 shadow-xl">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="font-medium">{title}</h3>
          <button onClick={onClose}>{t.close}</button>
        </div>
        {children}
      </div>
    </div>
  );
}
