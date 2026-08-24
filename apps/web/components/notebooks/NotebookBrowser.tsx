"use client";

import { t } from "@/lib/i18n";
import { isUntitled, sortNotebooks } from "@/lib/notebook";
import type { Notebook } from "@/lib/types";

function formatWhen(value: string | undefined): string {
  if (!value) return "";
  return new Date(value).toLocaleString("de-DE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function NotebookBrowser({
  notebooks,
  activeId,
  onOpen,
  onCreate,
  onClose,
}: {
  notebooks: Notebook[];
  activeId: string;
  onOpen: (notebook: Notebook) => void;
  onCreate: () => void;
  onClose: () => void;
}) {
  const items = sortNotebooks(notebooks);
  return (
    <div className="fixed inset-0 z-30 overflow-auto bg-mist">
      <header className="flex items-center justify-between border-b border-line bg-white px-6 py-3">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-ink text-sm text-white">en</div>
          <h2 className="text-lg font-medium">{t.notebooks}</h2>
        </div>
        <div className="flex items-center gap-2">
          <button className="rounded-full bg-ink px-3 py-1.5 text-sm text-white" onClick={onCreate}>
            + {t.createNotebook}
          </button>
          <button className="btn" onClick={onClose}>
            {t.close}
          </button>
        </div>
      </header>
      <div className="mx-auto grid max-w-5xl grid-cols-1 gap-4 p-6 sm:grid-cols-2 lg:grid-cols-3">
        <button
          className="flex min-h-40 flex-col items-center justify-center rounded-2xl border border-dashed border-neutral-300 bg-white text-sm text-neutral-600 hover:border-ink"
          onClick={onCreate}
        >
          <span className="mb-2 text-2xl">+</span>
          {t.createNotebook}
        </button>
        {items.map((notebook) => (
          <button
            key={notebook.id}
            className={`min-h-40 rounded-2xl border bg-white p-4 text-left shadow-sm hover:border-ink ${
              notebook.id === activeId ? "border-ink" : "border-line"
            }`}
            onClick={() => onOpen(notebook)}
          >
            <div className="text-base font-medium">{notebook.title}</div>
            {isUntitled(notebook.title) && <p className="mt-1 text-xs text-neutral-400">{t.untitled}</p>}
            <p className="mt-6 text-xs text-neutral-500">{formatWhen(notebook.updated_at || notebook.created_at)}</p>
          </button>
        ))}
        {items.length === 0 && <p className="text-sm text-neutral-500">{t.emptyNotebooks}</p>}
      </div>
    </div>
  );
}
