import assert from "node:assert/strict";
import { pendingStudioStillOpen } from "./studioPending";

const startedAt = Date.parse("2026-08-24T21:50:00Z");
const pending = { skillId: "studio.video", startedAt };

assert.equal(pendingStudioStillOpen(pending, []), true);
assert.equal(
  pendingStudioStillOpen(pending, [{ skill_id: "studio.audio", created_at: "2026-08-24T21:50:10Z" }]),
  true,
);
assert.equal(
  pendingStudioStillOpen(pending, [{ skill_id: "studio.video", created_at: "2026-08-24T21:49:00Z" }]),
  true,
);
assert.equal(
  pendingStudioStillOpen(pending, [{ skill_id: "studio.video", created_at: "2026-08-24T21:50:08Z" }]),
  false,
);
assert.equal(pendingStudioStillOpen(pending, [{ skill_id: "studio.video", created_at: "" }]), true);

console.log("studioPending ok");
