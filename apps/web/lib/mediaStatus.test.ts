import assert from "node:assert/strict";
import { mediaIsBusy, mediaIsFailed, mediaIsReady, mediaStatusLabel } from "./mediaStatus";

assert.equal(mediaIsReady("ready"), true);
assert.equal(mediaIsReady("pending"), false);
assert.equal(mediaIsBusy("pending"), true);
assert.equal(mediaIsFailed("error"), true);
assert.equal(
  mediaStatusLabel("pending", "Szene 2/8: Sprache wird erzeugt", "Sprache und Datei werden erzeugt…", "Erzeugung fehlgeschlagen."),
  "Szene 2/8: Sprache wird erzeugt",
);
assert.equal(
  mediaStatusLabel("pending", "", "Sprache und Datei werden erzeugt…", "Erzeugung fehlgeschlagen."),
  "Sprache und Datei werden erzeugt…",
);
assert.equal(
  mediaStatusLabel("error", "Sprachmodell antwortete mit 400.", "Sprache und Datei werden erzeugt…", "Erzeugung fehlgeschlagen."),
  "Sprachmodell antwortete mit 400.",
);
assert.equal(
  mediaStatusLabel("error", "", "Sprache und Datei werden erzeugt…", "Erzeugung fehlgeschlagen."),
  "Erzeugung fehlgeschlagen.",
);

console.log("mediaStatus ok");
