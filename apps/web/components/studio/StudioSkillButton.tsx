"use client";

import type { ReactNode } from "react";
import { t } from "@/lib/i18n";
import type { Skill } from "@/lib/types";

type Look = {
  tint: string;
  icon: ReactNode;
};

function Glyph({ children }: { children: React.ReactNode }) {
  return (
    <svg viewBox="0 0 24 24" className="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
      {children}
    </svg>
  );
}

const LOOK: Record<string, Look> = {
  "studio.audio": {
    tint: "bg-blue-50 text-blue-800",
    icon: (
      <Glyph>
        <path d="M4 10v4M8 7v10M12 4v16M16 8v8M20 11v2" strokeLinecap="round" />
      </Glyph>
    ),
  },
  "studio.slides": {
    tint: "bg-amber-50 text-amber-800",
    icon: (
      <Glyph>
        <rect x="3" y="5" width="18" height="12" rx="2" />
        <path d="M8 21h8M12 17v4" strokeLinecap="round" />
      </Glyph>
    ),
  },
  "studio.video": {
    tint: "bg-green-50 text-green-800",
    icon: (
      <Glyph>
        <rect x="3" y="6" width="13" height="12" rx="2" />
        <path d="M16 10l5-3v10l-5-3z" strokeLinejoin="round" />
      </Glyph>
    ),
  },
  "studio.mindmap": {
    tint: "bg-purple-50 text-purple-800",
    icon: (
      <Glyph>
        <circle cx="12" cy="12" r="2.2" />
        <path d="M12 9.8V5M12 14.2V19M9.8 12H5M14.2 12H19M9.6 9.6L6.5 6.5M14.4 14.4l3.1 3.1M14.4 9.6l3.1-3.1M9.6 14.4l-3.1 3.1" strokeLinecap="round" />
      </Glyph>
    ),
  },
  "studio.report": {
    tint: "bg-yellow-50 text-yellow-900",
    icon: (
      <Glyph>
        <path d="M7 3h8l4 4v14H7z" />
        <path d="M15 3v4h4M9 13h6M9 17h4" strokeLinecap="round" />
      </Glyph>
    ),
  },
  "studio.flashcards": {
    tint: "bg-red-50 text-red-800",
    icon: (
      <Glyph>
        <rect x="5" y="7" width="12" height="13" rx="1.5" />
        <path d="M8 7V5.5A1.5 1.5 0 0 1 9.5 4H18a1.5 1.5 0 0 1 1.5 1.5V16" strokeLinecap="round" />
      </Glyph>
    ),
  },
  "studio.quiz": {
    tint: "bg-sky-50 text-sky-800",
    icon: (
      <Glyph>
        <circle cx="12" cy="12" r="9" />
        <path d="M9.5 9.5a2.5 2.5 0 1 1 3.6 2.2c-.7.4-1.1.9-1.1 1.8V14" strokeLinecap="round" />
        <circle cx="12" cy="17" r="0.7" fill="currentColor" stroke="none" />
      </Glyph>
    ),
  },
  "studio.infographic": {
    tint: "bg-pink-50 text-pink-800",
    icon: (
      <Glyph>
        <path d="M5 19V10M12 19V5M19 19v-6" strokeLinecap="round" />
      </Glyph>
    ),
  },
  "studio.table": {
    tint: "bg-indigo-50 text-indigo-900",
    icon: (
      <Glyph>
        <rect x="4" y="5" width="16" height="14" rx="1.5" />
        <path d="M4 10h16M4 14h16M10 5v14" />
      </Glyph>
    ),
  },
  "notes.create": {
    tint: "bg-emerald-50 text-emerald-900",
    icon: (
      <Glyph>
        <path d="M6 4h9l3 3v13H6z" />
        <path d="M15 4v3h3M8 12h8M8 16h5" strokeLinecap="round" />
      </Glyph>
    ),
  },
};

const FALLBACK: Look = {
  tint: "bg-mist text-ink",
  icon: (
    <Glyph>
      <rect x="5" y="5" width="14" height="14" rx="2" />
    </Glyph>
  ),
};

export function StudioSkillButton({
  skill,
  busy,
  active,
  onRun,
}: {
  skill: Skill;
  busy: boolean;
  active?: boolean;
  onRun: (skill: Skill) => void;
}) {
  const look = LOOK[skill.id] || FALLBACK;
  const locked = skill.status === "locked";
  return (
    <button
      type="button"
      disabled={locked || busy}
      aria-pressed={active}
      onClick={() => onRun(skill)}
      className={`studio-skill ${look.tint} ${active ? "is-active" : ""} ${locked ? "opacity-50" : "hover:brightness-[0.97]"}`}
    >
      {look.icon}
      <span className="min-w-0 font-medium">{skill.title}</span>
      {locked && <span className="text-neutral-400">{t.locked}</span>}
    </button>
  );
}
