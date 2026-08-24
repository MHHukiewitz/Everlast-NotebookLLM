"use client";

import { useState } from "react";
import { CiteText, StudioCiteLinks, type StudioCiteProps } from "@/components/CiteText";
import { t } from "@/lib/i18n";
import type { Slide } from "@/lib/types";

export function SlidesView({
  slides,
  citations,
  onCite,
}: { slides: Slide[] } & StudioCiteProps) {
  const [index, setIndex] = useState(0);
  if (slides.length === 0) return null;
  const slide = slides[Math.min(index, slides.length - 1)];
  const slideText = [slide.heading, ...(slide.bullets || []), slide.notes || ""].join("\n");
  return (
    <div className="text-xs">
      <div className="rounded-lg border border-line bg-mist p-3">
        <p className="text-[11px] text-neutral-400">
          {index + 1} / {slides.length}
        </p>
        <h3 className="mt-1 font-medium text-neutral-800">
          <CiteText text={slide.heading} citations={citations} onCite={onCite} />
        </h3>
        <ul className="mt-2 list-disc pl-4 text-neutral-700">
          {(slide.bullets || []).map((bullet) => (
            <li key={bullet}>
              <CiteText text={bullet} citations={citations} onCite={onCite} />
            </li>
          ))}
        </ul>
        {slide.notes && (
          <p className="mt-2 text-neutral-500">
            <CiteText text={slide.notes} citations={citations} onCite={onCite} />
          </p>
        )}
        <StudioCiteLinks text={slideText} citations={citations} onCite={onCite} fallback="sources" />
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
