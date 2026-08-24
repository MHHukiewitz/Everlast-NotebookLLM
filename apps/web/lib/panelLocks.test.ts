import assert from "node:assert/strict";
import { panelLocks } from "./panelLocks";

const idle = panelLocks({
  chatBusy: false,
  studioBusy: false,
  addBusy: false,
  researchBusy: false,
});
assert.equal(idle.chatSendDisabled, false);
assert.equal(idle.studioSkillsDisabled, false);
assert.equal(idle.studioModalLocked, false);
assert.equal(idle.sourceAddDisabled, false);
assert.equal(idle.sourceResearchDisabled, false);

const studio = panelLocks({
  chatBusy: false,
  studioBusy: true,
  addBusy: false,
  researchBusy: false,
});
assert.equal(studio.chatSendDisabled, false);
assert.equal(studio.sourceAddDisabled, false);
assert.equal(studio.sourceResearchDisabled, false);
assert.equal(studio.studioSkillsDisabled, true);
assert.equal(studio.studioModalLocked, true);

const chat = panelLocks({
  chatBusy: true,
  studioBusy: false,
  addBusy: false,
  researchBusy: false,
});
assert.equal(chat.chatSendDisabled, true);
assert.equal(chat.studioSkillsDisabled, false);
assert.equal(chat.sourceAddDisabled, false);

const sources = panelLocks({
  chatBusy: false,
  studioBusy: true,
  addBusy: true,
  researchBusy: true,
});
assert.equal(sources.chatSendDisabled, false);
assert.equal(sources.sourceAddDisabled, true);
assert.equal(sources.sourceResearchDisabled, true);
assert.equal(sources.studioSkillsDisabled, true);
