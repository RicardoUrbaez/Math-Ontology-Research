import assert from "node:assert/strict";
import test from "node:test";

import { resetForPaperUpload } from "./paperState.js";

test("a PDF upload clears stale demo context and analysis", () => {
  const nextState = resetForPaperUpload("wireless-paper.pdf");

  assert.equal(nextState.title, "wireless-paper");
  assert.equal(nextState.context, "");
  assert.equal(nextState.equations, "");
  assert.deepEqual(nextState.analysis.equations, []);
  assert.equal(nextState.analysis.pdf.status, "selected");
});
