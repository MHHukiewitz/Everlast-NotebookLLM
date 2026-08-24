"use client";

import { useState } from "react";
import { t } from "@/lib/i18n";
import type { Flashcard } from "@/lib/types";

export function FlashcardsView({ cards }: { cards: Flashcard[] }) {
  const [open, setOpen] = useState<Record<number, boolean>>({});

  return (
    <ul className="space-y-2 text-xs">
      {cards.map((card, index) => (
        <li key={`${card.front}-${index}`} className="rounded border border-line p-2">
          <p className="font-medium text-neutral-800">{card.front}</p>
          <button
            className="mt-1 text-accent"
            onClick={() => setOpen((current) => ({ ...current, [index]: !current[index] }))}
          >
            {open[index] ? t.cardHide : t.cardReveal}
          </button>
          {open[index] && (
            <p className="mt-1 text-neutral-600">
              {card.back}
              {card.cite ? ` ${card.cite}` : ""}
            </p>
          )}
        </li>
      ))}
    </ul>
  );
}
