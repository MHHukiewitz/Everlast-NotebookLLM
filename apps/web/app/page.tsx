"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import { SiteFooter } from "@/components/SiteFooter";
import { ArtifactCard } from "@/components/studio/ArtifactCard";
import { ApiError, api, streamChat, uploadFile } from "@/lib/api";
import { t } from "@/lib/i18n";
import type { Artifact, AuthUser, Message, Notebook, Provider, ResearchJob, Skill, Source, SourceDetail } from "@/lib/types";

export default function Page() {
  const [notebook, setNotebook] = useState<Notebook | null>(null);
  const [sources, setSources] = useState<Source[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [skills, setSkills] = useState<Skill[]>([]);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [studioError, setStudioError] = useState("");
  const [providers, setProviders] = useState<Provider[]>([]);
  const [activeSource, setActiveSource] = useState<SourceDetail | null>(null);
  const [research, setResearch] = useState<ResearchJob | null>(null);
  const [selectedCites, setSelectedCites] = useState<string[]>([]);
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<"fast" | "deep">("fast");
  const [chatInput, setChatInput] = useState("");
  const [draft, setDraft] = useState("");
  const [thoughts, setThoughts] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
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
  const [user, setUser] = useState<AuthUser | null>(null);

  const selectedCount = useMemo(() => sources.filter((s) => s.selected && s.status === "ready").length, [sources]);

  const refresh = useCallback(async (id: string) => {
    const [src, msg, art] = await Promise.all([api.sources(id), api.messages(id), api.artifacts(id)]);
    setSources(src);
    setMessages(msg);
    setArtifacts(art);
  }, []);

  useEffect(() => {
    let cancelled = false;
    api
      .me()
      .then(async (me) => {
        if (cancelled) return;
        setUser(me);
        const [nbs, sk, pv] = await Promise.all([api.notebooks(), api.skills(), api.providers()]);
        if (cancelled) return;
        setSkills(sk);
        setProviders(pv);
        const nb = nbs[0] || (await api.createNotebook());
        if (cancelled) return;
        setNotebook(nb);
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

  async function onAddUrl() {
    if (!notebook || !urlValue) return;
    setBusy(true);
    setError("");
    await api.addUrl(notebook.id, urlValue).catch((err: Error) => setError(err.message));
    setUrlValue("");
    setAddOpen(false);
    await refresh(notebook.id);
    setBusy(false);
  }

  async function onAddText() {
    if (!notebook) return;
    setBusy(true);
    await api.addText(notebook.id, textTitle, textBody);
    setTextBody("");
    setAddOpen(false);
    await refresh(notebook.id);
    setBusy(false);
  }

  async function onFiles(files: FileList | null) {
    if (!notebook || !files) return;
    setBusy(true);
    for (const file of Array.from(files)) {
      await uploadFile(notebook.id, file);
    }
    await refresh(notebook.id);
    setBusy(false);
  }

  async function onResearch() {
    if (!notebook || !query) return;
    setBusy(true);
    setError("");
    const job = await api.research(notebook.id, query, mode);
    setResearch(job);
    setSelectedCites(job.candidates.map((c) => c.id));
    setBusy(false);
  }

  async function onImport() {
    if (!notebook || !research) return;
    setBusy(true);
    await api.importResearch(notebook.id, research.id, selectedCites, true);
    setResearch(null);
    await refresh(notebook.id);
    setBusy(false);
  }

  async function onSend(text?: string) {
    if (!notebook) return;
    const content = (text || chatInput).trim();
    if (!content) return;
    setChatInput("");
    setDraft("");
    setThoughts([]);
    setBusy(true);
    setMessages((prev) => [
      ...prev,
      { id: "tmp-user", role: "user", content, citations: [], tool_calls: [], model: null, created_at: new Date().toISOString() },
    ]);
    await streamChat(notebook.id, content, (event) => {
      if (event.event === "token") {
        setDraft((d) => d + String(event.text || ""));
      }
      if (event.event === "thought") {
        setThoughts((items) => [...items, String(event.text || "")]);
      }
      if (event.event === "done") {
        setDraft("");
      }
    });
    await refresh(notebook.id);
    setBusy(false);
  }

  async function saveSettings() {
    if (!notebook) return;
    const next = await api.updateNotebook(notebook.id, {
      provider: notebook.provider,
      model_id: notebook.model_id,
      title: notebook.title,
      eu_notice_accepted: euOk,
      openrouter_notice_accepted: orOk,
    });
    setNotebook(next);
    setSettingsOpen(false);
  }

  async function onRunSkill(skill: Skill) {
    if (skill.id === "notes.create") {
      setNoteOpen(true);
      return;
    }
    if (!notebook) return;
    if (selectedCount === 0) {
      setStudioError(t.studioNoSources);
      return;
    }
    setBusy(true);
    setStudioError("");
    const result = await api.runSkill(notebook.id, skill.id).catch((err: Error) => {
      setStudioError(err.message);
      return null;
    });
    if (result) {
      await refresh(notebook.id);
    }
    setBusy(false);
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
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-ink text-sm text-white">en</div>
          <input
            className="bg-transparent text-lg font-medium outline-none"
            value={notebook.title}
            onChange={(e) => setNotebook({ ...notebook, title: e.target.value })}
            onBlur={() => api.updateNotebook(notebook.id, { title: notebook.title })}
          />
        </div>
        <div className="flex items-center gap-2">
          <span className="rounded-full bg-mist px-3 py-1 text-xs">
            {notebook.provider === "ollama" ? t.local : notebook.provider === "eu" ? t.eu : t.openrouter} · {notebook.model_id.split("/").pop()}
          </span>
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

      <main className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[320px_1fr_300px]">
        <section className="panel">
          <div className="flex items-center justify-between px-4 py-3">
            <h2 className="font-medium">{t.sources}</h2>
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
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && onResearch()}
              />
            </div>
            <div className="mt-2 flex gap-2 text-xs">
              <span className="chip">{t.web}</span>
              <select className="chip bg-white" value={mode} onChange={(e) => setMode(e.target.value as "fast" | "deep")}>
                <option value="fast">{t.fast}</option>
                <option value="deep">{t.deep}</option>
              </select>
            </div>
          </div>
          <div
            className="mt-4 min-h-0 flex-1 overflow-auto px-4 pb-4"
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              onFiles(e.dataTransfer.files);
            }}
          >
            {research ? (
              <div className="space-y-3 text-sm">
                <ReactMarkdown>{research.report_md}</ReactMarkdown>
                <p className="font-medium">{t.cited}</p>
                {research.candidates.filter((c) => c.cited_in_report).map((c) => (
                  <label key={c.id} className="flex gap-2">
                    <input
                      type="checkbox"
                      checked={selectedCites.includes(c.id)}
                      onChange={() =>
                        setSelectedCites((ids) => (ids.includes(c.id) ? ids.filter((x) => x !== c.id) : [...ids, c.id]))
                      }
                    />
                    <span>{c.title}</span>
                  </label>
                ))}
                <p className="font-medium">{t.notCited}</p>
                {research.candidates.filter((c) => !c.cited_in_report).map((c) => (
                  <label key={c.id} className="flex gap-2">
                    <input
                      type="checkbox"
                      checked={selectedCites.includes(c.id)}
                      onChange={() =>
                        setSelectedCites((ids) => (ids.includes(c.id) ? ids.filter((x) => x !== c.id) : [...ids, c.id]))
                      }
                    />
                    <span>{c.title}</span>
                  </label>
                ))}
                <button className="btn-primary" onClick={onImport}>
                  {t.import}
                </button>
              </div>
            ) : activeSource ? (
              <div className="space-y-3 text-sm">
                <button className="text-xs text-accent" onClick={() => setActiveSource(null)}>
                  ← {t.sources}
                </button>
                <h3 className="font-medium">{activeSource.title}</h3>
                <ReactMarkdown>{activeSource.summary_md || activeSource.content_md}</ReactMarkdown>
                <a className="btn-primary inline-block" href={api.pdfUrl(notebook.id, activeSource.id)}>
                  {t.downloadPdf}
                </a>
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
                  <input type="file" className="hidden" multiple onChange={(e) => onFiles(e.target.files)} />
                </label>
              </div>
            ) : (
              <ul className="space-y-2">
                {sources.map((source) => (
                  <li key={source.id} className="flex items-start gap-2 rounded-lg border border-line p-2 text-sm">
                    <input
                      type="checkbox"
                      checked={source.selected}
                      onChange={() => api.selectSource(notebook.id, source.id, !source.selected).then(() => refresh(notebook.id))}
                    />
                    <button className="text-left" onClick={() => api.source(notebook.id, source.id).then(setActiveSource)}>
                      <div className="font-medium">{source.title}</div>
                      <div className="text-xs text-neutral-500">{source.type} · {source.status}</div>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>

        <section className="panel">
          <div className="flex items-center justify-between px-4 py-3">
            <h2 className="font-medium">{t.chat}</h2>
          </div>
          <div className="min-h-0 flex-1 overflow-auto px-6">
            {messages.length === 0 && !draft ? (
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
                {thoughts.length > 0 && (
                  <details className="text-xs text-neutral-500">
                    <summary>{t.thoughts}</summary>
                    <ul className="mt-1 list-disc pl-4">
                      {thoughts.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </details>
                )}
                {messages.map((message) => (
                  <article key={message.id} className={message.role === "user" ? "text-right" : ""}>
                    <div className={`inline-block max-w-full rounded-2xl px-4 py-3 text-sm ${message.role === "user" ? "bg-mist" : "bg-white"}`}>
                      <ReactMarkdown>{message.content}</ReactMarkdown>
                      {message.citations?.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1">
                          {message.citations.map((c) => (
                            <button
                              key={`${c.n}-${c.chunk_id}`}
                              className="rounded bg-blue-50 px-1.5 text-xs text-accent"
                              title={c.quote}
                              onClick={() => api.source(notebook.id, c.source_id).then(setActiveSource)}
                            >
                              [{c.n}]
                            </button>
                          ))}
                        </div>
                      )}
                      {message.role === "assistant" && (
                        <button
                          className="mt-2 text-xs text-accent"
                          onClick={() => api.createNote(notebook.id, t.newNote, message.content, message.id).then(() => refresh(notebook.id))}
                        >
                          {t.saveNote}
                        </button>
                      )}
                    </div>
                  </article>
                ))}
                {draft && (
                  <article>
                    <div className="rounded-2xl px-4 py-3 text-sm">
                      <ReactMarkdown>{draft}</ReactMarkdown>
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
                    onSend();
                  }
                }}
              />
              <div className="flex items-center justify-between">
                <label className="cursor-pointer text-neutral-400">
                  📎
                  <input type="file" className="hidden" onChange={(e) => onFiles(e.target.files)} />
                </label>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-neutral-500">{t.sourcesCount(selectedCount)}</span>
                  <button className="btn-primary" disabled={busy} onClick={() => onSend()}>
                    →
                  </button>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="panel border-r-0">
          <div className="px-4 py-3">
            <h2 className="font-medium">{t.studio}</h2>
          </div>
          <div className="grid grid-cols-2 gap-2 px-4">
            {skills.map((skill) => (
              <button
                key={skill.id}
                disabled={skill.status === "locked" || busy}
                onClick={() => onRunSkill(skill)}
                className={`rounded-xl border border-line p-3 text-left text-xs ${skill.status === "locked" ? "opacity-50" : "hover:bg-mist"}`}
              >
                <div className="font-medium">{skill.title}</div>
                {skill.status === "locked" && <div className="text-neutral-400">{t.locked}</div>}
              </button>
            ))}
          </div>
          <div className="min-h-0 flex-1 overflow-auto px-4 py-4 text-sm">
            {studioError && <p className="mb-3 text-xs text-red-600">{studioError}</p>}
            {busy && <p className="mb-3 text-xs text-neutral-500">{t.generating}</p>}
            {artifacts.length === 0 ? (
              <p className="text-neutral-500">
                {t.studioEmpty} {t.studioHint}
              </p>
            ) : (
              <ul className="space-y-2">
                {artifacts.map((artifact) => (
                  <ArtifactCard key={artifact.id} artifact={artifact} notebookId={notebook.id} />
                ))}
              </ul>
            )}
          </div>
          <div className="p-4">
            <button className="btn-primary w-full" onClick={() => setNoteOpen(true)}>
              + {t.addNote}
            </button>
          </div>
        </section>
      </main>
      <SiteFooter extra={t.footer} />

      {addOpen && (
        <Modal title={t.addSources} onClose={() => setAddOpen(false)}>
          <label className="text-sm">{t.addUrl}</label>
          <input className="mt-1 w-full rounded border border-line px-2 py-1" value={urlValue} onChange={(e) => setUrlValue(e.target.value)} />
          <button className="btn-primary mt-2" onClick={onAddUrl}>
            {t.addUrl}
          </button>
          <hr className="my-4" />
          <label className="text-sm">{t.pasteText}</label>
          <input className="mt-1 w-full rounded border border-line px-2 py-1" value={textTitle} onChange={(e) => setTextTitle(e.target.value)} />
          <textarea className="mt-2 h-28 w-full rounded border border-line p-2" value={textBody} onChange={(e) => setTextBody(e.target.value)} />
          <button className="btn-primary mt-2" onClick={onAddText}>
            {t.pasteText}
          </button>
          <hr className="my-4" />
          <label className="btn cursor-pointer">
            {t.upload}
            <input type="file" className="hidden" multiple onChange={(e) => onFiles(e.target.files).then(() => setAddOpen(false))} />
          </label>
        </Modal>
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
            }}
          >
            {t.addNote}
          </button>
        </Modal>
      )}

      {settingsOpen && (
        <Modal title={t.settings} onClose={() => setSettingsOpen(false)}>
          <div className="space-y-3 text-sm">
            {providers.map((provider) => (
              <div key={provider.id} className="rounded-lg border border-line p-3">
                <label className="flex items-center gap-2 font-medium">
                  <input
                    type="radio"
                    name="provider"
                    checked={notebook.provider === provider.id}
                    disabled={!provider.available}
                    onChange={() => setNotebook({ ...notebook, provider: provider.id, model_id: provider.models[0]?.id || notebook.model_id })}
                  />
                  {provider.label}
                </label>
                <p className="mt-1 text-xs text-neutral-500">{provider.notice}</p>
                {provider.models.length > 0 && notebook.provider === provider.id && (
                  <select
                    className="mt-2 w-full rounded border border-line p-1"
                    value={notebook.model_id}
                    onChange={(e) => setNotebook({ ...notebook, model_id: e.target.value })}
                  >
                    {provider.models.map((model) => (
                      <option key={model.id} value={model.id}>
                        {model.label}
                      </option>
                    ))}
                  </select>
                )}
              </div>
            ))}
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
                window.location.reload();
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
