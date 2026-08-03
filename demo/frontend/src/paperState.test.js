import assert from "node:assert/strict";
import test from "node:test";

import { documentPreviewKind, extractedContextForDisplay, resetForPaperUpload } from "./paperState.js";

test("a document upload clears stale demo context and analysis", () => {
  const nextState = resetForPaperUpload("wireless-paper.pdf");

  assert.equal(nextState.title, "wireless-paper");
  assert.equal(nextState.context, "");
  assert.equal(nextState.equations, "");
  assert.deepEqual(nextState.analysis.equations, []);
  assert.equal(nextState.analysis.pdf.status, "selected");
});

test("an equation image filename becomes a clean analysis title", () => {
  assert.equal(resetForPaperUpload("equation-5.jpeg").title, "equation-5");
  assert.equal(resetForPaperUpload("signal-model.png").title, "signal-model");
});

test("complete extracted document text is preferred over the short preview", () => {
  const analysis = {
    document_context: {
      preview: "Short introduction only",
      extracted_text: "Short introduction only\n\nFinal section from page 32"
    }
  };

  assert.equal(
    extractedContextForDisplay(analysis),
    "Short introduction only\n\nFinal section from page 32"
  );
  assert.equal(
    extractedContextForDisplay({ document_context: { preview: "Legacy preview" } }),
    "Legacy preview"
  );
});

test("uploaded research files select the appropriate preview", () => {
  assert.equal(documentPreviewKind({ name: "paper.pdf", type: "application/pdf" }), "pdf");
  assert.equal(documentPreviewKind({ name: "equation.PNG", type: "" }), "image");
  assert.equal(documentPreviewKind({ name: "notes.txt", type: "text/plain" }), "unsupported");
  assert.equal(documentPreviewKind(null), "none");
});
