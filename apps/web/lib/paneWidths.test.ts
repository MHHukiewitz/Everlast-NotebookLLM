import assert from "node:assert/strict";
import {
  DEFAULT_SOURCES,
  DEFAULT_STUDIO,
  MIN_SOURCES,
  MIN_STUDIO,
  fitPaneWidths,
  formatPaneWidths,
  parsePaneWidths,
  samePaneWidths,
} from "./paneWidths";

assert.deepEqual(parsePaneWidths(""), { sources: DEFAULT_SOURCES, studio: DEFAULT_STUDIO });
assert.deepEqual(parsePaneWidths("360,300"), { sources: 360, studio: 300 });
assert.deepEqual(parsePaneWidths(`${MIN_SOURCES},${MIN_STUDIO}`), {
  sources: DEFAULT_SOURCES,
  studio: DEFAULT_STUDIO,
});
assert.deepEqual(parsePaneWidths("bad"), { sources: DEFAULT_SOURCES, studio: DEFAULT_STUDIO });
assert.equal(parsePaneWidths("100,100").sources, MIN_SOURCES);
assert.equal(formatPaneWidths({ sources: 360, studio: 300 }), "360,300");

const roomy = fitPaneWidths(1600, 400, 320);
assert.deepEqual(roomy, { sources: 400, studio: 320 });

const tight = fitPaneWidths(0, 400, 320);
assert.equal(tight.sources, MIN_SOURCES);
assert.equal(tight.studio, MIN_STUDIO);
assert.equal(samePaneWidths(roomy, { sources: 400, studio: 320 }), true);
assert.equal(samePaneWidths(roomy, tight), false);

console.log("paneWidths ok");
