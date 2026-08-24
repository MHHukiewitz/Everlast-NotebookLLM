"use client";

import { useEffect, useMemo, useState } from "react";
import { SiteFooter } from "@/components/SiteFooter";
import { ApiError, api, type EvalItem, type EvalRun, type GenerationLog } from "@/lib/api";
import { reasoningLabel } from "@/lib/chatLive";
import { t } from "@/lib/i18n";

export default function EvalPage() {
  const [runs, setRuns] = useState<EvalRun[]>([]);
  const [activeId, setActiveId] = useState("");
  const [compareId, setCompareId] = useState("");
  const [compareRows, setCompareRows] = useState<{ case_id: string; question: string; a: EvalItem | null; b: EvalItem | null }[]>([]);
  const [provider, setProvider] = useState("ollama");
  const [model, setModel] = useState("qwen2.5:7b");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [reviewer, setReviewer] = useState("reviewer");
  const [generations, setGenerations] = useState<GenerationLog[]>([]);

  const active = useMemo(() => runs.find((run) => run.id === activeId) || runs[0], [runs, activeId]);

  function reload() {
    return Promise.all([api.evalRuns(), api.generations()]).then(([list, logs]) => {
      setRuns(list);
      setGenerations(logs);
      if (!activeId && list[0]) setActiveId(list[0].id);
    });
  }

  useEffect(() => {
    api
      .me()
      .then(() => reload())
      .catch((err: Error) => {
        if (err instanceof ApiError && err.status === 401) {
          window.location.replace("/login");
          return;
        }
        setError(err.message);
      });
  }, []);

  async function start() {
    setBusy(true);
    setError("");
    const run = await api.startEval(provider, model).catch((err: Error) => {
      setError(err.message === "Failed to fetch" ? t.apiOffline : err.message);
      return null;
    });
    if (!run) {
      setBusy(false);
      return;
    }
    setActiveId(run.id);
    await reload();
    let ticks = 0;
    while (ticks < 90) {
      ticks += 1;
      await new Promise((resolve) => window.setTimeout(resolve, 2000));
      const next = await api.evalRun(run.id).catch((err: Error) => {
        setError(err.message === "Failed to fetch" ? t.apiOffline : err.message);
        return null;
      });
      if (!next) {
        break;
      }
      setRuns((prev) => {
        const others = prev.filter((item) => item.id !== next.id);
        return [next, ...others];
      });
      if (next.status === "ready" || next.status === "error") {
        await reload();
        break;
      }
    }
    setBusy(false);
  }

  async function loadCompare() {
    if (!active || !compareId) return;
    const data = await api.compareEval(active.id, compareId);
    setCompareRows(data.rows);
  }

  async function saveScore(item: EvalItem, patch: Partial<EvalItem>) {
    await api.scoreEvalItem(item.id, {
      human_faithfulness: patch.human_faithfulness ?? item.human_faithfulness,
      human_usefulness: patch.human_usefulness ?? item.human_usefulness,
      human_citation: patch.human_citation ?? item.human_citation,
      human_pass: patch.human_pass ?? item.human_pass,
      human_comment: patch.human_comment ?? item.human_comment,
      reviewer,
    });
    await reload();
  }

  return (
    <div className="flex min-h-screen flex-col bg-white">
      <div className="flex-1 p-6">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <a className="text-sm text-accent" href="/">
            ← Notebook
          </a>
          <h1 className="text-xl font-medium">Eval-Harness</h1>
          <p className="text-sm text-neutral-500">
            Automatische Metriken plus menschliche Bewertung. Chat, HTML-Extrakt, Quellenbericht und Studio. Gleiche Gold-Fälle für jeden Lauf.
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <label className="text-xs">
            Reviewer
            <input className="mt-1 block rounded border border-line px-2 py-1" value={reviewer} onChange={(e) => setReviewer(e.target.value)} />
          </label>
          <label className="text-xs">
            Provider
            <select className="mt-1 block rounded border border-line px-2 py-1" value={provider} onChange={(e) => setProvider(e.target.value)}>
              <option value="ollama">Lokal</option>
              <option value="hetzner">Hetzner</option>
              <option value="eu">EU</option>
              <option value="openrouter">OpenRouter</option>
            </select>
          </label>
          <label className="text-xs">
            Modell
            <input className="mt-1 block rounded border border-line px-2 py-1" value={model} onChange={(e) => setModel(e.target.value)} />
          </label>
          <button className="btn-primary" disabled={busy} onClick={start}>
            {busy ? "Lauf läuft…" : "Lauf starten"}
          </button>
        </div>
      </div>
      {error && <p className="mb-3 text-sm text-red-600">{error}</p>}

      <div className="mb-4 flex gap-2 overflow-auto">
        {runs.map((run) => (
          <button
            key={run.id}
            className={`rounded-lg border px-3 py-2 text-left text-xs ${run.id === active?.id ? "border-accent bg-blue-50" : "border-line"}`}
            onClick={() => setActiveId(run.id)}
          >
            <div className="font-medium">
              {run.provider}/{run.model_id}
            </div>
            <div>
              {run.status} · overlap {run.metrics.avg_overlap ?? "–"} · {run.metrics.avg_latency_ms ?? "–"} ms
            </div>
            <div>human {run.metrics.human_reviewed ?? 0}/{run.metrics.n ?? 0}</div>
          </button>
        ))}
      </div>

      {active && (
        <section>
          <div className="mb-3 flex flex-wrap items-center gap-3 text-sm">
            <span>
              Refuse {active.metrics.refuse_accuracy} · Chat-Keywords {active.metrics.chat_avg_keyword_hit ?? active.metrics.avg_keyword_hit} ·
              Quelle-Keywords {active.metrics.source_avg_keyword_hit ?? "–"} · Quelle-Overlap {active.metrics.source_avg_overlap ?? "–"} ·
              Studio-Keywords {active.metrics.studio_avg_keyword_hit ?? "–"}
            </span>
            <select className="rounded border border-line px-2 py-1" value={compareId} onChange={(e) => setCompareId(e.target.value)}>
              <option value="">Vergleichen mit…</option>
              {runs
                .filter((run) => run.id !== active.id)
                .map((run) => (
                  <option key={run.id} value={run.id}>
                    {run.provider}/{run.model_id}
                  </option>
                ))}
            </select>
            <button className="btn" onClick={loadCompare} disabled={!compareId}>
              Vergleich laden
            </button>
          </div>

          {compareRows.length > 0 && (
            <table className="mb-6 w-full text-left text-xs">
              <thead>
                <tr className="border-b border-line">
                  <th className="py-2">Fall</th>
                  <th>A overlap / human</th>
                  <th>B overlap / human</th>
                </tr>
              </thead>
              <tbody>
                {compareRows.map((row) => (
                  <tr key={row.case_id} className="border-b border-line align-top">
                    <td className="py-2 pr-3">{row.question}</td>
                    <td className="pr-3">
                      {row.a ? `${row.a.overlap_score.toFixed(2)} / ${row.a.human_faithfulness ?? "–"}` : "–"}
                    </td>
                    <td>{row.b ? `${row.b.overlap_score.toFixed(2)} / ${row.b.human_faithfulness ?? "–"}` : "–"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <div className="space-y-4">
            {active.items.map((item) => (
              <article key={item.id} className="rounded-xl border border-line p-4">
                <div className="flex justify-between gap-4 text-xs text-neutral-500">
                  <span>
                    {item.case_id}
                    <span className="ml-2 rounded border border-line px-1.5 py-0.5">
                      {item.task === "source_extract"
                        ? "Quelle · Extrakt"
                        : item.task === "source_summary"
                          ? "Quelle · Bericht"
                          : item.task === "studio_mindmap"
                            ? "Studio · Mindmap"
                            : item.task === "studio_report"
                              ? "Studio · Bericht"
                              : item.task === "studio_quiz"
                                ? "Studio · Quiz"
                                : item.task === "studio_flashcards"
                                  ? "Studio · Karten"
                                  : item.task === "studio_table"
                                    ? "Studio · Tabelle"
                                    : item.task === "studio_slides"
                                      ? "Studio · Folien"
                                      : item.task === "studio_infographic"
                                        ? "Studio · Infografik"
                                        : item.task === "studio_audio"
                                          ? "Studio · Audio"
                                          : item.task === "studio_video"
                                            ? "Studio · Video"
                                            : "Chat"}
                    </span>
                  </span>
                  <span>
                    {item.latency_ms} ms · overlap {item.overlap_score.toFixed(2)} · keywords {item.keyword_hit_rate.toFixed(2)}
                    {item.must_refuse ? ` · refuse ${item.refuse_ok ? "ok" : "fail"}` : ""}
                  </span>
                </div>
                <h2 className="mt-1 font-medium">{item.question}</h2>
                <p className="mt-1 text-sm text-neutral-600">Soll: {item.expected_answer}</p>
                <p className="mt-2 whitespace-pre-wrap text-sm">{item.answer}</p>
                <div className="mt-3 grid gap-2 text-xs md:grid-cols-5">
                  <label>
                    Treue 1–5
                    <input
                      type="number"
                      min={1}
                      max={5}
                      className="mt-1 w-full rounded border border-line px-2 py-1"
                      defaultValue={item.human_faithfulness ?? ""}
                      onBlur={(e) => saveScore(item, { human_faithfulness: Number(e.target.value) || null })}
                    />
                  </label>
                  <label>
                    Nutzen 1–5
                    <input
                      type="number"
                      min={1}
                      max={5}
                      className="mt-1 w-full rounded border border-line px-2 py-1"
                      defaultValue={item.human_usefulness ?? ""}
                      onBlur={(e) => saveScore(item, { human_usefulness: Number(e.target.value) || null })}
                    />
                  </label>
                  <label>
                    Zitate 1–5
                    <input
                      type="number"
                      min={1}
                      max={5}
                      className="mt-1 w-full rounded border border-line px-2 py-1"
                      defaultValue={item.human_citation ?? ""}
                      onBlur={(e) => saveScore(item, { human_citation: Number(e.target.value) || null })}
                    />
                  </label>
                  <label>
                    Urteil
                    <select
                      className="mt-1 w-full rounded border border-line px-2 py-1"
                      defaultValue={item.human_pass == null ? "" : item.human_pass ? "pass" : "fail"}
                      onChange={(e) =>
                        saveScore(item, { human_pass: e.target.value === "" ? null : e.target.value === "pass" })
                      }
                    >
                      <option value="">offen</option>
                      <option value="pass">bestanden</option>
                      <option value="fail">nicht bestanden</option>
                    </select>
                  </label>
                  <label>
                    Kommentar
                    <input
                      className="mt-1 w-full rounded border border-line px-2 py-1"
                      defaultValue={item.human_comment}
                      onBlur={(e) => saveScore(item, { human_comment: e.target.value })}
                    />
                  </label>
                </div>
              </article>
            ))}
          </div>
        </section>
      )}

      <section className="mt-10">
        <h2 className="text-lg font-medium">LLM-Protokoll</h2>
        <p className="mb-3 text-sm text-neutral-500">
          Interne Ablage: Rohausgabe, sichtbare Antwort und Reasoning. Nicht für Training.
        </p>
        {generations.length === 0 ? (
          <p className="text-sm text-neutral-500">Noch keine Generierungen gespeichert.</p>
        ) : (
          <div className="space-y-3">
            {generations.map((row) => (
              <article key={row.id} className="rounded-xl border border-line p-3 text-xs">
                <div className="flex flex-wrap justify-between gap-2 text-neutral-500">
                  <span>
                    {row.kind} · {row.model} · {row.latency_ms} ms
                  </span>
                  <span>{row.created_at}</span>
                </div>
                {row.reasoning.length > 0 && (
                  <p className="mt-2">
                    Ablauf:{" "}
                    {row.reasoning.map(reasoningLabel).filter(Boolean).join(" · ")}
                  </p>
                )}
                <details className="mt-2">
                  <summary>Prompt</summary>
                  <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap">{row.prompt}</pre>
                </details>
                <details className="mt-2">
                  <summary>Rohausgabe</summary>
                  <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap">{row.raw_output || "—"}</pre>
                </details>
                <details className="mt-2">
                  <summary>Sichtbare Ausgabe</summary>
                  <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap">{row.visible_output || "—"}</pre>
                </details>
              </article>
            ))}
          </div>
        )}
      </section>
      </div>
      <SiteFooter extra={t.footer} />
    </div>
  );
}
