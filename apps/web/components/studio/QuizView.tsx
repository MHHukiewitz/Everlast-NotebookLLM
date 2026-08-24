"use client";

import { useState } from "react";
import { CiteText, StudioCiteLinks, type StudioCiteProps } from "@/components/CiteText";
import { t } from "@/lib/i18n";
import type { QuizQuestion } from "@/lib/types";

export function QuizView({
  questions,
  citations,
  onCite,
}: { questions: QuizQuestion[] } & StudioCiteProps) {
  const [picked, setPicked] = useState<Record<number, number>>({});
  const [open, setOpen] = useState<Record<number, boolean>>({});

  const allText = questions
    .map((item) => `${item.question}\n${(item.choices || []).join("\n")}\n${item.explanation || ""}`)
    .join("\n");

  return (
    <div>
    <ol className="space-y-3 text-xs">
      {questions.map((item, index) => {
        const choice = picked[index];
        const shown = open[index];
        const correct = choice === item.answer_index;
        const explainText = `${item.explanation || ""}`;
        return (
          <li key={`${item.question}-${index}`}>
            <p className="font-medium text-neutral-800">
              <CiteText text={item.question} citations={citations} onCite={onCite} />
            </p>
            <div className="mt-1 space-y-1">
              {item.choices.map((label, choiceIndex) => (
                <label key={`${index}-${choiceIndex}`} className="flex items-start gap-2">
                  <input
                    type="radio"
                    name={`quiz-${index}`}
                    checked={choice === choiceIndex}
                    onChange={() => setPicked((current) => ({ ...current, [index]: choiceIndex }))}
                  />
                  <span>
                    <CiteText text={label} citations={citations} onCite={onCite} />
                  </span>
                </label>
              ))}
            </div>
            <button
              className="mt-1 text-accent"
              onClick={() => setOpen((current) => ({ ...current, [index]: true }))}
            >
              {t.quizCheck}
            </button>
            {shown && choice === undefined && <p className="mt-1 text-neutral-500">{t.quizPick}</p>}
            {shown && choice !== undefined && (
              <div className={`mt-1 ${correct ? "text-green-700" : "text-red-600"}`}>
                <p>
                  {correct ? t.quizCorrect : t.quizWrong}
                  {item.explanation ? " " : ""}
                  {item.explanation ? (
                    <CiteText text={item.explanation} citations={citations} onCite={onCite} />
                  ) : null}
                </p>
                <StudioCiteLinks text={explainText} citations={citations} onCite={onCite} />
              </div>
            )}
          </li>
        );
      })}
    </ol>
    <StudioCiteLinks text={allText} citations={citations} onCite={onCite} fallback="sources" />
    </div>
  );
}
