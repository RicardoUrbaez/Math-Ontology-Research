export const samplePaper = {
  title: "Transformer Attention Demo",
  context:
    "The dominant sequence transduction models are based on recurrent or convolutional layers. We propose a new simple network architecture, the Transformer, based solely on attention mechanisms. Scaled dot-product attention computes relevance with a query matrix, key matrix, and value matrix, then normalizes the scores before weighting the output.",
  equations: ["S=\\sum_k a_k X_k", "x \\in \\mathbb{R}"]
};

export const audiences = [
  { value: "concise", label: "Concise" },
  { value: "pedagogical", label: "Pedagogical" },
  { value: "expert", label: "Expert" },
  { value: "document_role", label: "Document role" }
];

export const backends = [
  { value: "none", label: "No file" },
  { value: "mock", label: "Mock transcript" },
  { value: "gtts", label: "gTTS MP3" },
  { value: "azure", label: "Azure Speech" }
];
