import { t } from "./i18n";
import type { Notebook } from "./types";

export const ACTIVE_NOTEBOOK_KEY = "everlast.activeNotebook";
export const PANE_WIDTHS_COOKIE = "everlast_pane_widths";
export const SOURCE_SORT_KEY = "everlast.sourceSort";

export function readCookie(name: string): string {
  const prefix = `${name}=`;
  for (const part of document.cookie.split(";")) {
    const item = part.trim();
    if (item.startsWith(prefix)) return decodeURIComponent(item.slice(prefix.length));
  }
  return "";
}

export function writeCookie(name: string, value: string): void {
  document.cookie = `${name}=${encodeURIComponent(value)}; Path=/; Max-Age=31536000; SameSite=Lax`;
}

export function isUntitled(title: string | null | undefined): boolean {
  return !title || title.trim() === t.untitled;
}

export function notebookStamp(notebook: Notebook): string {
  return notebook.updated_at || notebook.created_at || "";
}

export function sortNotebooks(notebooks: Notebook[]): Notebook[] {
  return [...notebooks].sort((a, b) => notebookStamp(b).localeCompare(notebookStamp(a)));
}
