export function emptyPaperAnalysis(title, pdfStatus = "selected") {
  const document = {
    status: pdfStatus,
    detail: pdfStatus === "selected" ? "Document selected and ready to analyze." : "No document payload supplied."
  };
  return {
    title,
    equations: [],
    document_context: {
      source: "none",
      preview: "",
      preview_truncated: false,
      extracted_text: "",
      extracted_character_count: 0,
      analysis_scope: "none",
      context_chunk_count: 0,
      extractor: "none",
      pages_processed: 0
    },
    document,
    pdf: document,
    extracted_equation_count: 0
  };
}

export function extractedContextForDisplay(analysis) {
  const documentContext = analysis?.document_context || {};
  return documentContext.extracted_text || documentContext.preview || "";
}

export function documentPreviewKind(file) {
  if (!file) return "none";
  if (file.type === "application/pdf" || /\.pdf$/i.test(file.name || "")) return "pdf";
  if (file.type === "image/png" || file.type === "image/jpeg" || /\.(?:png|jpe?g)$/i.test(file.name || "")) {
    return "image";
  }
  return "unsupported";
}

export function resetForPaperUpload(filename) {
  const title = filename.replace(/\.(?:pdf|png|jpe?g)$/i, "") || "Untitled document";
  return {
    title,
    context: "",
    equations: "",
    analysis: emptyPaperAnalysis(title)
  };
}
