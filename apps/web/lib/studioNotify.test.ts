import assert from "node:assert/strict";
import { artifactStatusMap, finishedStudioArtifacts } from "./studioNotify";

const pending = { id: "a1", title: "Audio", payload: { status: "pending" } };
const ready = { id: "a1", title: "Audio", payload: { status: "ready" } };
const failed = { id: "a1", title: "Audio", payload: { status: "error", progress: "TTS 400" } };
const note = { id: "n1", title: "Notiz", payload: {} };

assert.deepEqual(artifactStatusMap([pending, note]), { a1: "pending", n1: "ready" });

assert.deepEqual(
  finishedStudioArtifacts({ a1: "pending" }, [ready]).map((item) => item.id),
  ["a1"],
);
assert.deepEqual(
  finishedStudioArtifacts({ a1: "pending" }, [failed]).map((item) => item.id),
  ["a1"],
);
assert.deepEqual(finishedStudioArtifacts({ a1: "pending" }, [pending]), []);
assert.deepEqual(finishedStudioArtifacts({ a1: "ready" }, [ready]), []);
assert.deepEqual(finishedStudioArtifacts({}, [ready]), []);
assert.deepEqual(finishedStudioArtifacts({ n1: "ready" }, [note]), []);
assert.deepEqual(
  finishedStudioArtifacts({ a1: "pending", n1: "ready" }, [ready, note]).map((item) => item.id),
  ["a1"],
);

console.log("studioNotify ok");
