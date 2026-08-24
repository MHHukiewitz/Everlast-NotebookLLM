import assert from "node:assert/strict";
import {
  artifactCiteText,
  artifactCitationMap,
  bindArtifactCitations,
  bindTextCitations,
  normalizeArtifactCitations,
  uniqueSourceCitations,
} from "./studioCitations";

const sources = [
  { id: "s1", title: "Quelle A", status: "ready", origin_uri: "https://a.example" },
  { id: "s2", title: "Quelle B", status: "ready", origin_uri: "https://b.example" },
] as const;

const map = [
  { n: 1, source_id: "s1", quote: "chunk one", source_title: "Quelle A" },
  { n: 2, source_id: "s2", quote: "chunk two", source_title: "Quelle B" },
];

const flashcards = {
  cards: [
    { front: "Frage", back: "Antwort aus dem Text [1]", cite: "[1]" },
    { front: "Zweite", back: "Andere Antwort", cite: "[2]" },
  ],
  citations: map,
};

assert.deepEqual(artifactCiteText(flashcards, "flashcards").includes("[1]"), true);
const boundCards = bindArtifactCitations(flashcards, "flashcards", [...sources]);
assert.deepEqual(
  boundCards.map((item) => [item.n, item.source_id]),
  [
    [1, "s1"],
    [2, "s2"],
  ],
);

const report = {
  body_md: "Ingest bleibt lokal [1]. Die Suche nutzt Hybrid [2].",
  citations: map,
};
const boundReport = bindArtifactCitations(report, "report", [...sources]);
assert.deepEqual(
  boundReport.map((item) => item.n),
  [1, 2],
);

const grouped = {
  body_md: "Berlin und Hamburg [7, 5].",
  citations: [
    { n: 5, source_id: "s1", quote: "Hamburg", source_title: "Quelle A" },
    { n: 7, source_id: "s2", quote: "Berlin", source_title: "Quelle B" },
  ],
};
assert.deepEqual(
  bindArtifactCitations(grouped, "report", [...sources]).map((item) => item.n),
  [7, 5],
);

const slideText = "Folie A [2]\nPunkt ohne Zahl";
assert.deepEqual(
  bindTextCitations(slideText, normalizeArtifactCitations(map)).map((item) => item.n),
  [2],
);

const mindmap = {
  mermaid: "mindmap\n  root((Thema))\n    Ingest",
  citations: map,
};
const boundMap = bindArtifactCitations(mindmap, "mindmap", [...sources]);
assert.deepEqual(
  boundMap.map((item) => [item.n, item.title]),
  [
    [1, "Quelle A"],
    [2, "Quelle B"],
  ],
);

const unique = uniqueSourceCitations([
  { n: 1, source_id: "s1", quote: "a", title: "Quelle A" },
  { n: 3, source_id: "s1", quote: "b", title: "Quelle A" },
  { n: 2, source_id: "s2", quote: "c", title: "Quelle B" },
]);
assert.deepEqual(
  unique.map((item) => item.n),
  [1, 2],
);

const noteWithoutMap = { body: "Satz aus der Quelle [2]." };
const mapped = artifactCitationMap(noteWithoutMap, [...sources]);
assert.equal(mapped[1]?.source_id, "s2");
const boundNote = bindArtifactCitations(noteWithoutMap, "note", [...sources]);
assert.deepEqual(
  boundNote.map((item) => [item.n, item.source_id]),
  [[2, "s2"]],
);

const quiz = {
  questions: [
    {
      question: "Was gilt [1]?",
      choices: ["A", "B", "C", "D"],
      answer_index: 0,
      explanation: "Siehe Quelle [1].",
    },
  ],
  citations: map,
};
assert.deepEqual(
  bindArtifactCitations(quiz, "quiz", [...sources]).map((item) => item.n),
  [1],
);
