import type { Source } from "./types";

export type SourceSortKey = "title" | "type" | "created";
export type SourceSortDir = "asc" | "desc";

export type SourceSort = {
  key: SourceSortKey;
  dir: SourceSortDir;
};

export const DEFAULT_SOURCE_SORT: SourceSort = { key: "created", dir: "desc" };

export function parseSourceSort(raw: string | null): SourceSort {
  if (!raw) return DEFAULT_SOURCE_SORT;
  const [key, dir] = raw.split(":");
  if (key !== "title" && key !== "type" && key !== "created") return DEFAULT_SOURCE_SORT;
  if (dir !== "asc" && dir !== "desc") return DEFAULT_SOURCE_SORT;
  return { key, dir };
}

export function formatSourceSort(sort: SourceSort): string {
  return `${sort.key}:${sort.dir}`;
}

export function sortSources(sources: Source[], sort: SourceSort): Source[] {
  const copy = [...sources];
  copy.sort((a, b) => {
    let cmp = 0;
    if (sort.key === "title") {
      cmp = a.title.localeCompare(b.title, "de", { sensitivity: "base" });
    } else if (sort.key === "type") {
      cmp = a.type.localeCompare(b.type, "de", { sensitivity: "base" });
    } else {
      cmp = (a.created_at || "").localeCompare(b.created_at || "");
    }
    if (cmp === 0) {
      cmp = a.id.localeCompare(b.id);
    }
    return sort.dir === "asc" ? cmp : -cmp;
  });
  return copy;
}
