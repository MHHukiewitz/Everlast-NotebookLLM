"use client";

import { useState } from "react";
import { CiteText, StudioCiteLinks, type StudioCiteProps } from "@/components/CiteText";
import { t } from "@/lib/i18n";
import type { Flashcard } from "@/lib/types";

export function FlashcardsView({
  cards,
  citations,
  onCite,
}: { cards: Flashcard[] } & StudioCiteProps) {
  const [open, setOpen] = useState<Record<number, boolean>>({});
  const allText = cards.map((card) => `${card.front}\n${card.back}\n${card.cite || ""}`).join("\n");

  return (
    <div>
      <ul className="space-y-2 text-xs">
        {cards.map((card, index) => (
          <li key={`${card.front}-${index}`} className="rounded border border-line p-2">
            <p className="font-medium text-neutral-800">
              <CiteText text={card.front} citations={citations} onCite={onCite} />
            </p>
            <button
              className="mt-1 text-accent"
              onClick={() => setOpen((current) => ({ ...current, [index]: !current[index] }))}
            >
              {open[index] ? t.cardHide : t.cardReveal}
            </button>
            {open[index] && (
              <div className="mt-1 text-neutral-600">
                <p>
                  <CiteText text={card.back} citations={citations} onCite={onCite} />
                </p>
                {card.cite ? (
                  <p className="mt-1">
                    <CiteText text={card.cite} citations={citations} onCite={onCite} />
                  </p>
                ) : null}
              </div>
            )}
          </li>
        ))}
      </ul>
      <StudioCiteLinks text={allText} citations={citations} onCite={onCite} fallback="sources" />
    </div>
  );
}
