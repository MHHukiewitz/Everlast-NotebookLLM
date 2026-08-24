"use client";

import { useState } from "react";
import { t } from "@/lib/i18n";
import type { QuizQuestion } from "@/lib/types";

export function QuizView({ questions }: { questions: QuizQuestion[] }) {
  const [picked, setPicked] = useState<Record<number, number>>({});
  const [open, setOpen] = useState<Record<number, boolean>>({});

  return (
    <ol className="space-y-3 text-xs">
      {questions.map((item, index) => {
        const choice = picked[index];
        const shown = open[index];
        const correct = choice === item.answer_index;
        return (
          <li key={`${item.question}-${index}`}>
            <p className="font-medium text-neutral-800">{item.question}</p>
            <div className="mt-1 space-y-1">
              {item.choices.map((label, choiceIndex) => (
                <label key={`${index}-${choiceIndex}`} className="flex items-start gap-2">
                  <input
                    type="radio"
                    name={`quiz-${index}`}
                    checked={choice === choiceIndex}
                    onChange={() => setPicked((current) => ({ ...current, [index]: choiceIndex }))}
                  />
                  <span>{label}</span>
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
              <p className={`mt-1 ${correct ? "text-green-700" : "text-red-600"}`}>
                {correct ? t.quizCorrect : t.quizWrong}
                {item.explanation ? ` ${item.explanation}` : ""}
              </p>
            )}
          </li>
        );
      })}
    </ol>
  );
}
