import assert from "node:assert/strict";
import { panelLocks } from "./panelLocks";

const idle = panelLocks({
  chatBusy: false,
  addBusy: false,
  researchBusy: false,
});
assert.equal(idle.chatSendDisabled, false);
assert.equal(idle.sourceAddDisabled, false);
assert.equal(idle.sourceResearchDisabled, false);

const chat = panelLocks({
  chatBusy: true,
  addBusy: false,
  researchBusy: false,
});
assert.equal(chat.chatSendDisabled, true);
assert.equal(chat.sourceAddDisabled, false);

const sources = panelLocks({
  chatBusy: false,
  addBusy: true,
  researchBusy: true,
});
assert.equal(sources.chatSendDisabled, false);
assert.equal(sources.sourceAddDisabled, true);
assert.equal(sources.sourceResearchDisabled, true);
