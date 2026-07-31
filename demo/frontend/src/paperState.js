export function emptyPaperAnalysis(title, pdfStatus = "selected") {
  return {
    title,
    equations: [],
    document_context: {
      source: "none",
      preview: "",
      context_chunk_count: 0,
      extractor: "none",
      pages_processed: 0
    },
    pdf: {
      status: pdfStatus,
      detail: pdfStatus === "selected" ? "PDF selected and ready to analyze." : "No PDF payload supplied."
    },
    extracted_equation_count: 0
  };
}

export function resetForPaperUpload(filename) {
  const title = filename.replace(/\.pdf$/i, "") || "Untitled paper";
  return {
    title,
    context: "",
    equations: "",
    analysis: emptyPaperAnalysis(title)
  };
}
