import assert from "node:assert/strict";
import test from "node:test";

import { createPaperJob } from "./api.js";

test("a disconnected analysis API reports a recoverable backend error", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => {
    throw new TypeError("Failed to fetch");
  };

  try {
    await assert.rejects(
      createPaperJob({ title: "test paper" }),
      (error) =>
        error.connectionError === true &&
        error.message.includes("confirm the API is running on port 8000") &&
        error.message.includes("PDF and form are still here")
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});
