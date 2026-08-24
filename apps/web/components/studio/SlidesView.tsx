"use client";

import { useState } from "react";
import { t } from "@/lib/i18n";
import type { Slide } from "@/lib/types";

export function SlidesView({ slides }: { slides: Slide[] }) {
  const [index, setIndex] = useState(0);
  if (slides.length === 0) return null;
  const slide = slides[Math.min(index, slides.length - 1)];
  return (
    <div className="text-xs">
      <div className="rounded-lg border border-line bg-mist p-3">
        <p className="text-[11px] text-neutral-400">
          {index + 1} / {slides.length}
        </p>
        <h3 className="mt-1 font-medium text-neutral-800">{slide.heading}</h3>
        <ul className="mt-2 list-disc pl-4 text-neutral-700">
          {(slide.bullets || []).map((bullet) => (
            <li key={bullet}>{bullet}</li>
          ))}
        </ul>
        {slide.notes && <p className="mt-2 text-neutral-500">{slide.notes}</p>}
      </div>
      <div className="mt-2 flex gap-2">
        <button className="text-accent" disabled={index === 0} onClick={() => setIndex((value) => value - 1)}>
          {t.slidePrev}
        </button>
        <button
          className="text-accent"
          disabled={index >= slides.length - 1}
          onClick={() => setIndex((value) => value + 1)}
        >
          {t.slideNext}
        </button>
      </div>
    </div>
  );
}
