import assert from "node:assert/strict";
import {
  applyChatEvent,
  displayChatText,
  stepsFromReasoning,
  stripCitationDump,
  usedCitations,
  visibleChatText,
  type LivePart,
} from "./chatLive";

function nextId() {
  let n = 0;
  return () => {
    n += 1;
    return `id_${n}`;
  };
}

function applyAll(events: Record<string, unknown>[]): LivePart[] {
  const id = nextId();
  return events.reduce((parts, event) => applyChatEvent(parts, event, id), [] as LivePart[]);
}

const afterStep = applyAll([
  { event: "step", id: "s1", kind: "analyze", title: "Frage prüfen", detail: "Was macht Everlast?", status: "done" },
  { event: "step", id: "s2", kind: "retrieve", title: "Quellen durchsuchen", detail: "8 Treffer in 3 Quellen", status: "done" },
]);
assert.equal(afterStep.length, 2);
assert.equal(afterStep[0].kind, "step");
assert.equal(afterStep[1].kind, "step");
if (afterStep[1].kind === "step") {
  assert.equal(afterStep[1].step.detail, "8 Treffer in 3 Quellen");
}

const updated = applyChatEvent(
  afterStep,
  { event: "step", id: "s2", kind: "retrieve", title: "Quellen durchsuchen", detail: "8 Treffer in 3 Quellen", status: "done" },
  nextId(),
);
assert.equal(updated.length, 2);

const withThink = applyAll([
  { event: "think", text: "Erst " },
  { event: "think", text: "dann." },
  { event: "token", text: "Antwort" },
]);
assert.equal(withThink[0].kind, "think");
if (withThink[0].kind === "think") {
  assert.equal(withThink[0].text, "Erst dann.");
}
assert.equal(withThink[1].kind, "text");
if (withThink[1].kind === "text") {
  assert.equal(withThink[1].text, "Antwort");
}

const saved = stepsFromReasoning([
  { id: "a", title: "Frage prüfen", detail: "Hallo", kind: "analyze" },
  "Fähigkeit: sources.list",
]);
assert.equal(saved[0].title, "Frage prüfen");
assert.equal(saved[1].title, "Fähigkeit: sources.list");

assert.equal(visibleChatText('Hallo {"name": "notes_create", "arguments": {}} Ende'), "Hallo  Ende");
assert.equal(visibleChatText("Hallo {"), "Hallo");
assert.equal(visibleChatText("Hallo <tool_call>"), "Hallo");
assert.equal(visibleChatText("text\n```json\n"), "text");
assert.equal(
  visibleChatText('```json\n{"name": "notes_create", "arguments": {}}\n``` Rest'),
  "Rest",
);
assert.ok(!visibleChatText('{"tool": "notes.create", "parameters": {}}').includes("notes"));

const dumped = "[1] [2] [3] [4] [5] [6] [7] [8]\n\nSatz [1].";
assert.equal(stripCitationDump(dumped), "Satz [1].");
assert.deepEqual(
  usedCitations("Satz [1].", [
    { n: 1, quote: "a" },
    { n: 2, quote: "b" },
  ]).map((item) => item.n),
  [1],
);
assert.deepEqual(usedCitations("Keine Zitate.", [{ n: 1, quote: "a" }]), []);
assert.equal(displayChatText("[1] [2]\n\nHallo {"), "Hallo");
