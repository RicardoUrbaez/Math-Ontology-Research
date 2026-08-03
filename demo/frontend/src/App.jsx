import { useEffect, useMemo, useRef, useState } from "react";
import katex from "katex";
import "katex/dist/katex.min.css";
import pdfWorkerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import { analyzePaper, analyzePaperJob, fileToBase64, getHealth } from "./api.js";
import { audiences, backends, samplePaper } from "./sampleData.js";
import { Icon } from "./icons.jsx";
import { documentPreviewKind, extractedContextForDisplay, resetForPaperUpload } from "./paperState.js";

function initialPreviewScale() {
  if (window.innerWidth <= 480) return 0.55;
  if (window.innerWidth <= 820) return 0.85;
  return 1.15;
}

function splitEquations(value) {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function EquationNotation({ latex }) {
  const rendered = useMemo(() => {
    try {
      return katex.renderToString(latex || "", {
        displayMode: true,
        output: "htmlAndMathml",
        strict: "ignore",
        throwOnError: false,
        trust: false
      });
    } catch {
      return "";
    }
  }, [latex]);

  if (!rendered) return <code>{latex}</code>;
  return <div className="rendered-equation" dangerouslySetInnerHTML={{ __html: rendered }} />;
}

function defaultAnalysis() {
  return {
    title: samplePaper.title,
    equations: [
      {
        index: 1,
        latex: samplePaper.equations[0],
        plain_notation_reading: "S equals sum k a k X k",
        semantic_reading:
          "Pedagogical MathOntoSpeak reading: Equation S equals sum k a k X k. Matched concepts: Equality, Addition, Variable.",
        contextual_explanation:
          "Resolved ontology concepts include Equality, Addition, and Variable. The surrounding paper context explains how attention mechanisms weight output values.",
        context_summary:
          "Equation 1 expresses a matrix or vector relationship used by the paper's attention model.",
        context_evidence: [
          {
            source: "provided_context",
            kind: "sentence",
            text:
              "Scaled dot-product attention computes relevance with a query matrix, key matrix, and value matrix, then normalizes the scores before weighting the output."
          }
        ],
        term_explanations: [
          {
            symbol: "S",
            spoken: "S",
            meaning: "the attention score produced by the expression",
            source: "paper_context",
            ontology_concept: "Variable",
            confidence: "high"
          },
          {
            symbol: "\\sum",
            spoken: "sum",
            meaning: "combines the indexed terms through summation",
            source: "ontology",
            ontology_concept: "Addition",
            confidence: "medium"
          }
        ],
        ontology_links: [],
        spoken_script:
          "Next I am going to read Equation 1. Equation 1 expresses a matrix or vector relationship used by the paper's attention model. Term by term, S means the attention score produced by the expression; sum combines the indexed terms through summation. Now the notation is: S equals sum k a k X k.",
        extraction_confidence: "user_supplied",
        why_it_helps:
          "This gives a blind researcher meaning, role, and document context before the notation is spoken.",
        resolved_count: 3,
        concepts: ["Equality", "Addition", "Variable"],
        linked_text_span:
          "Scaled dot-product attention computes relevance with a query matrix, key matrix, and value matrix, then normalizes the scores before weighting the output.",
        recommendations: [],
        tokens: [],
        audio: { status: "skipped", detail: "Audio generation was not requested." }
      }
    ],
    document: { status: "not_provided", detail: "No document payload supplied.", extractor: "none" },
    pdf: { status: "not_provided", detail: "No document payload supplied.", extractor: "none" },
    extracted_equation_count: 0
  };
}

function StatusPill({ health, loading }) {
  const ok = health?.api === "ok" || health?.status === "ok";
  return (
    <div className={`status-pill ${ok ? "ready" : ""}`} aria-label="System status">
      <span className="dot" />
      {loading ? "Checking system" : ok ? "System health ready" : "Backend not checked"}
    </div>
  );
}

function Header({ health, loading }) {
  return (
    <header className="app-header">
      <div className="brand">
        <div className="brand-mark">
          <Icon name="sigma" />
        </div>
        <span>MathOnto<span className="brand-accent">Speak</span></span>
        <small>Research workbench</small>
      </div>
      <nav aria-label="Demo controls">
        <StatusPill health={health} loading={loading} />
        <a href="http://127.0.0.1:8000/docs" target="_blank" rel="noreferrer">
          API docs
        </a>
      </nav>
    </header>
  );
}

function IntegrationStrip({ health, loading }) {
  const integrations = Object.entries(health?.integrations || {});
  const kokoro = health?.tts?.kokoro;
  const labels = {
    docling: "Docling",
    mineru: "MinerU",
    sentence_transformers: "Semantic retrieval",
    grobid: "GROBID",
    ragas: "Ragas"
  };
  return (
    <section className="integration-strip" aria-label="External processing integrations">
      <strong>Processing engines</strong>
      <div className="integration-items">
        {loading ? <span className="integration-state waiting">Checking runtimes</span> : null}
        {!loading
          ? integrations.map(([name, integration]) => {
              const state = integration.enabled
                ? "Enabled"
                : integration.runtime_available
                  ? "Ready"
                  : integration.cloned
                    ? "Cloned only"
                    : "Unavailable";
              return (
                <span
                  key={name}
                  className={`integration-state ${integration.enabled ? "enabled" : integration.cloned ? "cloned" : "missing"}`}
                  title={integration.role?.replaceAll("_", " ") || "External integration"}
                >
                  <i aria-hidden="true" />
                  {labels[name] || name}: {state}
                </span>
              );
            })
          : null}
        {!loading && kokoro ? (
          <span
            className={`integration-state ${kokoro.available ? "enabled" : "missing"}`}
            title={kokoro.detail || "Local neural speech runtime"}
          >
            <i aria-hidden="true" />
            Kokoro voice: {kokoro.available ? "Enabled" : "Unavailable"}
          </span>
        ) : null}
      </div>
    </section>
  );
}

function PaperInput({
  title,
  setTitle,
  context,
  contextSource,
  documentContext,
  onContextChange,
  equations,
  setEquations,
  pdfFile,
  previewUrl,
  onPreview,
  onPdf,
  onAnalyze,
  loading,
  pdfReading,
  progressMessage
}) {
  return (
    <section className="panel input-panel" aria-labelledby="input-heading">
      <div className="panel-heading">
        <span>1.</span>
        <h2 id="input-heading">Document & Equation</h2>
      </div>
      <p className="panel-intro">Upload a paper or equation image, then add any context the reader should consider.</p>
      <label>
        Paper title
        <input value={title} onChange={(event) => setTitle(event.target.value)} />
      </label>
      <label className="drop-zone">
        <Icon name="upload" />
        <span>{pdfFile ? pdfFile.name : "Upload PDF or equation image"}</span>
        <small>
          {pdfFile
            ? `${(pdfFile.size / 1024 / 1024).toFixed(2)} MB`
            : "PDF, PNG, JPG, or JPEG"}
        </small>
        <input type="file" accept="application/pdf,image/png,image/jpeg" onChange={onPdf} />
      </label>
      {pdfFile && previewUrl ? (
        <button className="secondary-button preview-button" type="button" onClick={onPreview}>
          <Icon name="eye" />
          View uploaded {documentPreviewKind(pdfFile) === "pdf" ? "PDF" : "image"}
        </button>
      ) : null}
      <label>
        {contextSource === "document" ? "Extracted document context (full paper)" : "Abstract / context"}
        <textarea value={context} onChange={(event) => onContextChange(event.target.value)} rows={10} />
      </label>
      {contextSource === "document" ? (
        <p className="context-coverage" role="status">
          Full document analyzed | {(documentContext?.extracted_character_count || context.length).toLocaleString()} characters
          {documentContext?.pages_processed ? ` | ${documentContext.pages_processed} pages` : ""}
        </p>
      ) : null}
      <label>
        Equations in document
        <textarea
          className="equation-entry"
          value={equations}
          onChange={(event) => setEquations(event.target.value)}
          rows={5}
          placeholder="One LaTeX equation per line"
        />
      </label>
      <button className="secondary-button" type="button" onClick={() => setEquations("")}>
        Extract from context
      </button>
      <button className="primary-button" type="button" onClick={onAnalyze} disabled={loading || pdfReading}>
        <Icon name="spark" />
        {pdfReading ? "Reading file" : loading ? "Analyzing" : "Analyze document"}
      </button>
      <p className="progress-message" role="status" aria-live="polite">
        {progressMessage}
      </p>
    </section>
  );
}

function PdfPreview({ previewUrl, filename }) {
  const canvasRef = useRef(null);
  const [pdfDocument, setPdfDocument] = useState(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [scale, setScale] = useState(initialPreviewScale);
  const [status, setStatus] = useState("Loading PDF preview...");
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    let loadingTask;
    setPdfDocument(null);
    setPageNumber(1);
    setScale(initialPreviewScale());
    setError("");
    setStatus("Loading PDF preview...");

    import("pdfjs-dist")
      .then(({ getDocument, GlobalWorkerOptions }) => {
        if (!active) return null;
        GlobalWorkerOptions.workerSrc = pdfWorkerUrl;
        loadingTask = getDocument({ url: previewUrl });
        return loadingTask.promise;
      })
      .then((document) => {
        if (!active || !document) return;
        setPdfDocument(document);
        setStatus(`${document.numPages} page PDF ready.`);
      })
      .catch((exc) => {
        if (!active) return;
        setError(`The PDF preview could not be rendered: ${exc.message}`);
        setStatus("");
      });

    return () => {
      active = false;
      loadingTask?.destroy();
    };
  }, [previewUrl]);

  useEffect(() => {
    if (!pdfDocument || !canvasRef.current) return undefined;

    let cancelled = false;
    let renderTask;
    pdfDocument.getPage(pageNumber).then((page) => {
      if (cancelled || !canvasRef.current) return;
      const canvas = canvasRef.current;
      const viewport = page.getViewport({ scale });
      const outputScale = Math.min(window.devicePixelRatio || 1, 2);
      const context = canvas.getContext("2d", { alpha: false });
      canvas.width = Math.floor(viewport.width * outputScale);
      canvas.height = Math.floor(viewport.height * outputScale);
      canvas.style.width = `${Math.floor(viewport.width)}px`;
      canvas.style.height = `${Math.floor(viewport.height)}px`;
      renderTask = page.render({
        canvas,
        canvasContext: context,
        viewport,
        transform: outputScale === 1 ? null : [outputScale, 0, 0, outputScale, 0, 0]
      });
      return renderTask.promise;
    }).catch((exc) => {
      if (!cancelled && exc?.name !== "RenderingCancelledException") {
        setError(`Page ${pageNumber} could not be rendered: ${exc.message}`);
      }
    });

    return () => {
      cancelled = true;
      renderTask?.cancel();
    };
  }, [pdfDocument, pageNumber, scale]);

  const pageCount = pdfDocument?.numPages || 0;

  return (
    <div className="pdf-preview-viewer">
      <div className="pdf-preview-toolbar" aria-label="PDF preview controls">
        <div className="pdf-page-controls">
          <button
            className="icon-button"
            type="button"
            title="Previous page"
            aria-label="Previous page"
            disabled={pageNumber <= 1}
            onClick={() => setPageNumber((current) => Math.max(1, current - 1))}
          >
            <Icon name="chevron-left" />
          </button>
          <span>Page {pageNumber} of {pageCount || "..."}</span>
          <button
            className="icon-button"
            type="button"
            title="Next page"
            aria-label="Next page"
            disabled={!pageCount || pageNumber >= pageCount}
            onClick={() => setPageNumber((current) => Math.min(pageCount, current + 1))}
          >
            <Icon name="chevron-right" />
          </button>
        </div>
        <div className="pdf-zoom-controls">
          <button
            className="icon-button"
            type="button"
            title="Zoom out"
            aria-label="Zoom out"
            disabled={scale <= 0.4}
            onClick={() => setScale((current) => Math.max(0.4, Number((current - 0.15).toFixed(2))))}
          >
            <Icon name="zoom-out" />
          </button>
          <span>{Math.round(scale * 100)}%</span>
          <button
            className="icon-button"
            type="button"
            title="Zoom in"
            aria-label="Zoom in"
            disabled={scale >= 2.35}
            onClick={() => setScale((current) => Math.min(2.35, Number((current + 0.15).toFixed(2))))}
          >
            <Icon name="zoom-in" />
          </button>
        </div>
      </div>
      <div className="pdf-canvas-scroller" aria-label={`Rendered preview of ${filename}`}>
        {error ? <p className="pdf-preview-error" role="alert">{error}</p> : null}
        {!error ? <canvas ref={canvasRef} aria-label={`Page ${pageNumber} of ${filename}`} /> : null}
      </div>
      <p className="sr-only" role="status" aria-live="polite">{status}</p>
    </div>
  );
}

function DocumentPreview({ file, previewUrl, dialogRef }) {
  if (!file || !previewUrl) return null;

  const kind = documentPreviewKind(file);
  const closePreview = () => dialogRef.current?.close();

  return (
    <dialog
      className="document-preview-dialog"
      ref={dialogRef}
      aria-labelledby="document-preview-title"
      onClick={(event) => {
        if (event.target === event.currentTarget) closePreview();
      }}
    >
      <div className="document-preview-shell">
        <header className="document-preview-header">
          <div>
            <h2 id="document-preview-title">Document preview</h2>
            <p>{file.name}</p>
          </div>
          <div className="document-preview-actions">
            <a href={previewUrl} target="_blank" rel="noreferrer" title="Open uploaded file in a new tab">
              <Icon name="external" />
              <span>Open in new tab</span>
            </a>
            <button className="icon-button" type="button" onClick={closePreview} title="Close document preview">
              <Icon name="close" />
              <span className="sr-only">Close document preview</span>
            </button>
          </div>
        </header>
        <div className={`document-preview-content ${kind}`}>
          {kind === "pdf" ? (
            <PdfPreview previewUrl={previewUrl} filename={file.name} />
          ) : (
            <img src={previewUrl} alt={`Preview of uploaded equation file ${file.name}`} />
          )}
        </div>
        <footer className="document-preview-footer">
          <span>{(file.size / 1024 / 1024).toFixed(2)} MB</span>
          <span>Use the viewer controls to move between pages or change zoom.</span>
        </footer>
      </div>
    </dialog>
  );
}

function EquationList({ equations, selectedIndex, setSelectedIndex }) {
  if (!equations.length) {
    return <p className="empty-note">No equations have been analyzed yet.</p>;
  }
  return (
    <div className="equation-list" aria-label="Analyzed equations">
      {equations.map((equation, index) => {
        const unnumbered = equation.display_label?.startsWith("Unnumbered equation");
        return (
          <button
            key={`${equation.latex}-${index}`}
            className={selectedIndex === index ? "selected" : ""}
            type="button"
            onClick={() => setSelectedIndex(index)}
          >
            <span title={equation.display_label || equation.equation_label || `Equation ${index + 1}`}>
              {equation.source_label || (unnumbered ? `U${index + 1}` : index + 1)}
            </span>
            <strong>{equation.latex}</strong>
            <small>
              {equation.page ? `Page ${equation.page} - ` : ""}
              {equation.extraction_confidence || "unknown"}
            </small>
          </button>
        );
      })}
    </div>
  );
}

function AnalysisPanel({ analysis, selectedIndex, setSelectedIndex, headingRef }) {
  const [activeView, setActiveView] = useState("meaning");
  const equations = analysis?.equations || [];
  const equation = equations[selectedIndex] || equations[0];
  const ontologyRuntime = analysis?.ontology_runtime || {};
  const liveOntology = ontologyRuntime.query_mode === "live_fuseki" && equation?.ontology_query_mode === "live_fuseki";
  const ontologyRows = equation
    ? (equation.ontology_links || []).map((link) => ({
        symbol: link.symbols?.join(", ") || "KG",
        label: link.canonical_label,
        domain: link.domain_tags?.join(", ") || link.source_provenance || "knowledge graph",
        confidence: "Linked"
      }))
    : [];
  const tokenRows = equation
    ? (equation.tokens || [])
        .filter((token) => token.canonical_label)
        .map((token) => ({
          symbol: token.raw,
          label: token.canonical_label,
          domain: token.domain_tags?.join(", ") || "general",
          confidence: token.concept_iri ? "Linked" : "Open"
        }))
    : [];
  const conceptRows = ontologyRows.length ? ontologyRows : tokenRows;
  const fallbackConceptRows =
    equation && conceptRows.length === 0
      ? (equation.concepts || []).map((label) => ({
          symbol: label.slice(0, 2),
          label,
          domain: "resolved concept",
          confidence: "High"
        }))
      : [];
  const visibleConceptRows = conceptRows.length ? conceptRows : fallbackConceptRows;
  const views = ["meaning", "terms", "evidence", "ontology", "notation"];

  useEffect(() => {
    setActiveView("meaning");
  }, [equation?.equation_id]);

  return (
    <section className="panel analysis-panel" aria-labelledby="analysis-heading">
      <div className="analysis-header">
        <div className="panel-heading">
          <span>2.</span>
          <h2 id="analysis-heading" ref={headingRef} tabIndex="-1">Equation Analysis</h2>
        </div>
        <div className="stepper" aria-label="Selected equation">
          <button
            type="button"
            aria-label="Previous equation"
            disabled={!equations.length || selectedIndex === 0}
            onClick={() => setSelectedIndex(Math.max(0, selectedIndex - 1))}
          >
            Prev
          </button>
          <strong>{equations.length ? `${selectedIndex + 1} of ${equations.length}` : "0 of 0"}</strong>
          <button
            type="button"
            aria-label="Next equation"
            disabled={!equations.length || selectedIndex >= equations.length - 1}
            onClick={() => setSelectedIndex(Math.min(equations.length - 1, selectedIndex + 1))}
          >
            Next
          </button>
        </div>
      </div>
      <EquationList equations={equations} selectedIndex={selectedIndex} setSelectedIndex={setSelectedIndex} />
      {equation ? (
        <div className="analysis-stack">
          <div className="equation-source-line" aria-label="Equation source details">
            <strong>{equation.display_label || equation.equation_label || `Equation ${selectedIndex + 1}`}</strong>
            <span>{equation.page ? `Page ${equation.page}` : "Page unavailable"}</span>
            <span>Role: {equation.equation_role?.label?.replaceAll("_", " ") || "unknown"}</span>
            <span>Context: {equation.confidence?.context || "low"}</span>
            {analysis?.document?.input_type === "image" ? (
              <span>Text detection: {Math.round((analysis.document.ocr_confidence || 0) * 100)}%</span>
            ) : null}
          </div>
          <div className="equation-display" aria-label="Selected equation notation">
            <EquationNotation latex={equation.latex} />
            <span>{equation.source_label ? `(${equation.source_label})` : ""}</span>
          </div>
          {equation.equation_image ? (
            <img className="equation-crop" src={equation.equation_image} alt={`Source crop for ${equation.display_label || "equation"}`} />
          ) : null}
          <div className="analysis-tabs" role="tablist" aria-label="Equation analysis views">
            {views.map((view) => (
              <button
                key={view}
                type="button"
                role="tab"
                aria-selected={activeView === view}
                className={activeView === view ? "active" : ""}
                onClick={() => setActiveView(view)}
              >
                {view[0].toUpperCase() + view.slice(1)}
              </button>
            ))}
          </div>
          <div role="tabpanel" className="analysis-view">
            {activeView === "meaning" ? (
              <>
                {analysis?.pipeline ? (
                  <div className="pipeline-evidence" aria-label="Processing evidence">
                    <h3>Processing Evidence</h3>
                    {Object.entries(analysis.pipeline).map(([stage, item]) => (
                      <span key={stage}>
                        <strong>{stage.replaceAll("_", " ")}</strong>
                        {item.engine?.replaceAll("_", " ") || "not run"}
                      </span>
                    ))}
                  </div>
                ) : null}
                <Readout title="Context Summary" text={equation.context_summary} accent />
                {equation.conceptual_structure ? (
                  <Readout title="Conceptual Structure" text={equation.conceptual_structure} />
                ) : null}
                <Readout title="Spoken Script" text={equation.spoken_script || equation.semantic_reading} />
                <Readout title="Contextual Explanation" text={equation.contextual_explanation} />
                {equation.grounding_evaluation ? (
                  <div className="grounding-evaluation">
                    <strong>Evidence alignment</strong>
                    <span>{equation.grounding_evaluation.engine?.replaceAll("_", " ")}</span>
                    <span>{Math.round((equation.grounding_evaluation.score || 0) * 100)}%</span>
                    <small>{equation.grounding_evaluation.detail}</small>
                  </div>
                ) : null}
                {equation.unresolved_symbols?.length ? (
                  <div className="unresolved-note">
                    <strong>Unresolved from this paper:</strong> {equation.unresolved_symbols.join(", ")}
                  </div>
                ) : null}
              </>
            ) : null}
            {activeView === "terms" ? <TermExplanationTable terms={equation.term_explanations || []} /> : null}
            {activeView === "evidence" ? (
              <div className="evidence-list">
                {(equation.formula_repairs || []).map((repair, index) => (
                  <article className="formula-repair" key={`${repair.kind || "repair"}-${index}`}>
                    <strong>Formula recovery</strong>
                    <small>
                      {(repair.confidence || "unknown").replaceAll("_", " ")} confidence ·{" "}
                      {(repair.provenance_type || "unknown").replaceAll("_", " ")}
                    </small>
                    <p>{repair.description}</p>
                    {index === 0 && equation.original_latex && equation.original_latex !== equation.latex ? (
                      <code>Original extraction: {equation.original_latex}</code>
                    ) : null}
                  </article>
                ))}
                {(equation.context_evidence || []).map((item, index) => (
                  <article key={item.evidence_id || index}>
                    <strong>{item.section_heading || item.kind || "Paper context"}</strong>
                    <small>{item.page ? `Page ${item.page}` : "Document context"}</small>
                    <p>{item.text}</p>
                    <code>{item.evidence_id}</code>
                  </article>
                ))}
                {!equation.context_evidence?.length ? <p className="empty-note">No paper evidence was recovered.</p> : null}
              </div>
            ) : null}
            {activeView === "ontology" ? (
              <div>
                <h3>Ontology Evidence</h3>
                <p className={`ontology-runtime ${liveOntology ? "connected" : ontologyRuntime.available ? "local" : ""}`}>
                  {liveOntology
                    ? `Live Fuseki query verified: ${ontologyRuntime.dataset} | ${equation.ontology_links?.length || 0} graph concepts`
                    : ontologyRuntime.available
                      ? `Local Protege snapshot fallback: ${ontologyRuntime.gloss_records || 0} mapped records`
                    : "Ontology runtime unavailable"}
                </p>
                {equation.ontology_links?.length ? (
                  <div className="ontology-graph-list">
                    {equation.ontology_links.slice(0, 10).map((link, index) => (
                      <article key={`${link.concept_iri}-${index}`}>
                        <span className="symbol">{link.symbols?.join(", ") || "KG"}</span>
                        <div>
                          <strong>{link.canonical_label}</strong>
                          <small>
                            {link.parent_concepts?.length
                              ? `Parent: ${link.parent_concepts.map((parent) => parent.canonical_label).join(", ")}`
                              : link.domain_tags?.join(", ") || "No parent class returned"}
                          </small>
                          {link.definition ? <p>{link.definition}</p> : null}
                          <code>{link.concept_iri}</code>
                        </div>
                        <em className={link.query_mode === "live_fuseki" ? "live" : "local"}>
                          {link.query_mode === "live_fuseki" ? "Live graph" : "Local"}
                        </em>
                      </article>
                    ))}
                  </div>
                ) : (
                  <div className="concept-table">
                    {visibleConceptRows.slice(0, 10).map((row, index) => (
                      <div className="concept-row" key={`${row.label}-${index}`}>
                        <span className="symbol">{row.symbol}</span>
                        <strong>{row.label}</strong>
                        <small>{row.domain}</small>
                        <em>{row.confidence}</em>
                      </div>
                    ))}
                    {!visibleConceptRows.length ? <p className="empty-note">No ontology concepts resolved for this equation.</p> : null}
                  </div>
                )}
              </div>
            ) : null}
            {activeView === "notation" ? (
              <>
                <div className={`speech-engine-note ${equation.math_speech?.available ? "active" : "fallback"}`}>
                  <strong>Notation speech engine</strong>
                  <span>{equation.math_speech?.engine?.replaceAll("_", " ") || "unknown"}</span>
                  <small>{equation.math_speech?.detail || "No notation speech diagnostic was returned."}</small>
                </div>
                <Readout title="Raw LaTeX" text={equation.latex} mono />
                <Readout title="Plain Notation Reading" text={equation.plain_notation_reading} />
                <Readout title="MathML" text={equation.mathml} mono />
              </>
            ) : null}
          </div>
        </div>
      ) : null}
    </section>
  );
}

function TermExplanationTable({ terms }) {
  return (
    <div>
      <h3>Term-by-Term</h3>
      <div className="term-table">
        {terms.slice(0, 12).map((term, index) => (
          <div className="term-row" key={`${term.symbol}-${index}`}>
            <span className="symbol">{term.symbol}</span>
            <p>{term.meaning}</p>
            <small>{term.source?.replace("_", " ") || "unresolved"}</small>
            <em className={`confidence ${term.confidence || "low"}`}>{term.confidence || "low"}</em>
          </div>
        ))}
        {!terms.length && <p className="empty-note">No term explanations are available yet.</p>}
      </div>
    </div>
  );
}

function Readout({ title, text, mono = false, accent = false }) {
  return (
    <div className={`readout ${accent ? "accent" : ""}`}>
      <h3>{title}</h3>
      <p className={mono ? "mono" : ""}>{text || "No output yet."}</p>
    </div>
  );
}

function EvidencePanel({ audience, setAudience, backend, setBackend, generateAudio, setGenerateAudio, selectedEquation }) {
  const [speaking, setSpeaking] = useState(false);
  const [paused, setPaused] = useState(false);
  const [rate, setRate] = useState(0.95);
  const [voices, setVoices] = useState([]);
  const [voiceName, setVoiceName] = useState("");
  const [currentSegmentIndex, setCurrentSegmentIndex] = useState(0);
  const segmentIndexRef = useRef(0);
  const audioRef = useRef(null);
  const backendAudioUrl = selectedEquation?.audio?.audio_url || "";
  const segments = useMemo(() => {
    if (selectedEquation?.speech_segments?.length) return selectedEquation.speech_segments;
    const text = selectedEquation?.spoken_script || selectedEquation?.semantic_reading || "";
    return text ? [{ segment_id: "speech-full", kind: "reading", text }] : [];
  }, [selectedEquation]);

  useEffect(() => {
    if (!window.speechSynthesis) return undefined;
    const loadVoices = () => {
      const available = window.speechSynthesis.getVoices();
      setVoices(available);
      setVoiceName((current) => current || available[0]?.name || "");
    };
    loadVoices();
    window.speechSynthesis.addEventListener?.("voiceschanged", loadVoices);
    return () => window.speechSynthesis.removeEventListener?.("voiceschanged", loadVoices);
  }, []);

  useEffect(() => {
    window.speechSynthesis?.cancel();
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }
    setSpeaking(false);
    setPaused(false);
    setCurrentSegmentIndex(0);
    segmentIndexRef.current = 0;
  }, [selectedEquation?.equation_id]);

  function speakSegment(index, continueReading = true) {
    if (!window.speechSynthesis || !segments[index]) return;
    window.speechSynthesis.cancel();
    segmentIndexRef.current = index;
    setCurrentSegmentIndex(index);
    const utterance = new SpeechSynthesisUtterance(segments[index].text);
    utterance.rate = rate;
    utterance.voice = voices.find((voice) => voice.name === voiceName) || null;
    utterance.onend = () => {
      const nextIndex = segmentIndexRef.current + 1;
      if (continueReading && nextIndex < segments.length) {
        speakSegment(nextIndex, true);
      } else {
        setSpeaking(false);
        setPaused(false);
      }
    };
    utterance.onerror = () => {
      setSpeaking(false);
      setPaused(false);
    };
    setSpeaking(true);
    setPaused(false);
    window.speechSynthesis.speak(utterance);
  }

  function speak() {
    if (backendAudioUrl && audioRef.current) {
      audioRef.current.play();
      setSpeaking(true);
      setPaused(false);
      return;
    }
    if (paused) {
      window.speechSynthesis?.resume();
      setPaused(false);
      return;
    }
    speakSegment(speaking ? currentSegmentIndex : 0, true);
  }

  function pause() {
    if (backendAudioUrl && audioRef.current) {
      audioRef.current.pause();
      setPaused(true);
      return;
    }
    window.speechSynthesis?.pause();
    setPaused(true);
  }

  function stop() {
    window.speechSynthesis?.cancel();
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }
    setSpeaking(false);
    setPaused(false);
    setCurrentSegmentIndex(0);
    segmentIndexRef.current = 0;
  }

  function syncBackendCaption() {
    const audio = audioRef.current;
    if (!audio?.duration || !segments.length) return;
    const totalWeight = segments.reduce((sum, segment) => sum + Math.max(segment.text.length, 1), 0);
    const target = (audio.currentTime / audio.duration) * totalWeight;
    let cumulative = 0;
    const index = segments.findIndex((segment) => {
      cumulative += Math.max(segment.text.length, 1);
      return target <= cumulative;
    });
    const nextIndex = index < 0 ? segments.length - 1 : index;
    segmentIndexRef.current = nextIndex;
    setCurrentSegmentIndex(nextIndex);
  }

  function downloadTranscript() {
    if (!selectedEquation) return;
    const content = segments.map((segment) => segment.text).join("\n\n");
    const url = URL.createObjectURL(new Blob([content], { type: "text/plain;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `${selectedEquation.equation_id || "equation"}-transcript.txt`;
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <section className="panel evidence-panel" aria-labelledby="evidence-heading">
      <div className="panel-heading">
        <span>3.</span>
        <h2 id="evidence-heading">Listen & Evidence</h2>
      </div>
      <p className="panel-intro">Hear the same contextual script shown in the analysis, with sentence-level captions.</p>
      <div className="audio-settings">
      <label>
        Audience mode
        <select value={audience} onChange={(event) => setAudience(event.target.value)}>
          {audiences.map((item) => (
            <option key={item.value} value={item.value}>
              {item.label}
            </option>
          ))}
        </select>
      </label>
      <label>
        Audio backend
        <select value={backend} onChange={(event) => setBackend(event.target.value)}>
          {backends.map((item) => (
            <option key={item.value} value={item.value}>
              {item.label}
            </option>
          ))}
        </select>
      </label>
      <label>
        Browser voice
        <select value={voiceName} onChange={(event) => setVoiceName(event.target.value)}>
          {voices.map((voice) => (
            <option key={`${voice.name}-${voice.lang}`} value={voice.name}>
              {voice.name} ({voice.lang})
            </option>
          ))}
          {!voices.length ? <option value="">System default</option> : null}
        </select>
      </label>
      <label>
        Reading speed: {rate.toFixed(2)}x
        <input
          className="rate-slider"
          type="range"
          min="0.6"
          max="1.4"
          step="0.05"
          value={rate}
          onChange={(event) => setRate(Number(event.target.value))}
        />
      </label>
      <label className="toggle-line">
        <input
          type="checkbox"
          checked={generateAudio}
          onChange={(event) => setGenerateAudio(event.target.checked)}
        />
        Generate backend audio artifact
      </label>
      </div>
      <h3 className="section-label">Contextual reading</h3>
      <div className="play-row">
        <button className="primary-button" type="button" onClick={speaking && !paused ? pause : speak} disabled={!segments.length}>
          <Icon name={speaking && !paused ? "pause" : "play"} />
          {speaking && !paused ? "Pause" : paused ? "Resume" : backendAudioUrl ? "Play neural reading" : "Play with context"}
        </button>
        <button className="icon-button" type="button" onClick={stop} aria-label="Stop reading" title="Stop reading" disabled={!speaking && !paused}>
          <Icon name="stop" />
        </button>
        <button className="icon-button" type="button" onClick={() => speakSegment(currentSegmentIndex, false)} aria-label="Replay current sentence" title="Replay current sentence" disabled={!segments.length}>
          <Icon name="wave" />
        </button>
        <button className="icon-button" type="button" onClick={downloadTranscript} aria-label="Download transcript" title="Download transcript" disabled={!segments.length}>
          <Icon name="download" />
        </button>
      </div>
      {backendAudioUrl ? (
        <audio
          ref={audioRef}
          className="backend-audio"
          controls
          preload="metadata"
          src={backendAudioUrl}
          onPlay={() => { setSpeaking(true); setPaused(false); }}
          onPause={() => { if (!audioRef.current?.ended) setPaused(true); }}
          onTimeUpdate={syncBackendCaption}
          onEnded={() => { setSpeaking(false); setPaused(false); setCurrentSegmentIndex(0); }}
        >
          Your browser does not support audio playback.
        </audio>
      ) : null}
      <div className="caption-box" aria-live="polite">
        <small>{segments[currentSegmentIndex]?.kind || "Caption"}</small>
        <p>{segments[currentSegmentIndex]?.text || "Analyze an equation to create a contextual reading."}</p>
      </div>
      <details className="transcript">
        <summary>Full transcript</summary>
        <ol>
          {segments.map((segment, index) => (
            <li className={index === currentSegmentIndex ? "current" : ""} key={segment.segment_id || index}>
              <button type="button" onClick={() => speakSegment(index, false)}>{segment.text}</button>
            </li>
          ))}
        </ol>
      </details>
      <div className="evidence-tabs">
        <h3>Linked Text Span</h3>
        <p>
          {selectedEquation?.context_evidence?.[0]?.text ||
            selectedEquation?.linked_text_span ||
            (selectedEquation?.equation_image
              ? "Equation recognized from the uploaded image; no surrounding prose was provided."
              : "Analyze a paper to connect the equation back to nearby text.")}
        </p>
        <dl>
          <div>
            <dt>Audio status</dt>
            <dd>{selectedEquation?.audio?.status || "skipped"}</dd>
          </div>
          <div>
            <dt>Resolved concepts</dt>
            <dd>{selectedEquation?.resolved_count || 0}</dd>
          </div>
          <div>
            <dt>Explanation source</dt>
            <dd>{selectedEquation?.explanation_provider?.name || "deterministic"}</dd>
          </div>
          <div>
            <dt>Unresolved terms</dt>
            <dd>{selectedEquation?.unresolved_symbols?.length || 0}</dd>
          </div>
        </dl>
      </div>
    </section>
  );
}

export default function App() {
  const [title, setTitle] = useState(samplePaper.title);
  const [context, setContext] = useState(samplePaper.context);
  const [equations, setEquations] = useState(samplePaper.equations.join("\n"));
  const [audience, setAudience] = useState("pedagogical");
  const [backend, setBackend] = useState("none");
  const [generateAudio, setGenerateAudio] = useState(false);
  const [pdfFile, setPdfFile] = useState(null);
  const [pdfBase64, setPdfBase64] = useState("");
  const [previewUrl, setPreviewUrl] = useState("");
  const [pdfReading, setPdfReading] = useState(false);
  const [analysis, setAnalysis] = useState(defaultAnalysis);
  const [contextSource, setContextSource] = useState("sample");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [loading, setLoading] = useState(false);
  const [progressMessage, setProgressMessage] = useState("");
  const [error, setError] = useState("");
  const [health, setHealth] = useState(null);
  const [healthLoading, setHealthLoading] = useState(true);
  const analysisHeadingRef = useRef(null);
  const previewDialogRef = useRef(null);

  const selectedEquation = useMemo(() => analysis?.equations?.[selectedIndex] || analysis?.equations?.[0], [analysis, selectedIndex]);
  const documentStatus = analysis?.document || analysis?.pdf || {};

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => setHealth(null))
      .finally(() => setHealthLoading(false));
  }, []);

  useEffect(() => {
    if (!pdfFile) {
      setPreviewUrl("");
      return undefined;
    }

    const nextUrl = URL.createObjectURL(pdfFile);
    setPreviewUrl(nextUrl);
    return () => URL.revokeObjectURL(nextUrl);
  }, [pdfFile]);

  async function onPdf(event) {
    const file = event.target.files?.[0];
    setPdfFile(file || null);
    if (!file) {
      setPdfBase64("");
      return;
    }

    const resetState = resetForPaperUpload(file.name);
    setTitle(resetState.title);
    setContext(resetState.context);
    setContextSource("empty");
    setEquations(resetState.equations);
    setAnalysis(resetState.analysis);
    setSelectedIndex(0);
    setError("");
    setProgressMessage("File selected. Ready to extract structure and equations.");
    setPdfReading(true);
    try {
      setPdfBase64(await fileToBase64(file));
    } catch (exc) {
      setPdfBase64("");
      setError(`Could not read the selected PDF: ${exc.message}`);
    } finally {
      setPdfReading(false);
    }
  }

  function onContextChange(value) {
    setContext(value);
    setContextSource(value.trim() ? "user" : "empty");
  }

  function openDocumentPreview() {
    if (!previewUrl || !previewDialogRef.current) return;
    previewDialogRef.current.showModal();
  }

  async function onAnalyze() {
    setLoading(true);
    setError("");
    setProgressMessage(pdfBase64 ? "Queueing document and equation extraction..." : "Analyzing equations and context...");
    try {
      const request = {
        title,
        abstract_or_context: contextSource === "document" ? "" : context,
        equations: splitEquations(equations),
        audience,
        audio_backend: backend,
        generate_audio: generateAudio,
        document_base64: pdfBase64,
        document_filename: pdfFile?.name || "",
        document_media_type: pdfFile?.type || ""
      };
      const payload = pdfBase64
        ? await analyzePaperJob(request, (job) => {
            const stage = job.stage?.replaceAll("_", " ") || job.status;
            setProgressMessage(`${stage}: ${job.progress || 0}%`);
          })
        : await analyzePaper(request);
      setAnalysis(payload);
      setSelectedIndex(0);
      if (payload?.document?.input_type === "image" && !equations.trim()) {
        setEquations(
          (payload.equations || [])
            .map((equation) => `${equation.latex}${equation.source_label ? `\\tag{${equation.source_label}}` : ""}`)
            .join("\n")
        );
      }
      setProgressMessage(`Analysis complete. ${payload.equations?.length || 0} equation(s) ready.`);
      const extractedDocumentContext = extractedContextForDisplay(payload);
      if (pdfFile && contextSource !== "user" && extractedDocumentContext) {
        setContext(extractedDocumentContext);
        setContextSource("document");
      }
      window.requestAnimationFrame(() => analysisHeadingRef.current?.focus());
    } catch (exc) {
      setError(exc.message);
      if (exc.connectionError) setHealth(null);
      setProgressMessage("Analysis failed. Review the error and try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app-shell">
      <a className="skip-link" href="#analysis-heading">Skip to equation analysis</a>
      <Header health={health} loading={healthLoading} />
      <IntegrationStrip health={health} loading={healthLoading} />
      <div className={`error-banner${error ? "" : " empty"}`} role="alert" aria-live="assertive">
        {error}
      </div>
      <main className="workspace">
        <PaperInput
          title={title}
          setTitle={setTitle}
          context={context}
          contextSource={contextSource}
          documentContext={analysis?.document_context}
          onContextChange={onContextChange}
          equations={equations}
          setEquations={setEquations}
          pdfFile={pdfFile}
          previewUrl={previewUrl}
          onPreview={openDocumentPreview}
          onPdf={onPdf}
          onAnalyze={onAnalyze}
          loading={loading}
          pdfReading={pdfReading}
          progressMessage={progressMessage}
        />
        <AnalysisPanel
          analysis={analysis}
          selectedIndex={selectedIndex}
          setSelectedIndex={setSelectedIndex}
          headingRef={analysisHeadingRef}
        />
        <EvidencePanel
          audience={audience}
          setAudience={setAudience}
          backend={backend}
          setBackend={setBackend}
          generateAudio={generateAudio}
          setGenerateAudio={setGenerateAudio}
          selectedEquation={selectedEquation}
        />
      </main>
      <DocumentPreview file={pdfFile} previewUrl={previewUrl} dialogRef={previewDialogRef} />
      <footer className="app-footer">
        <span>Project: paper equation demo</span>
        <span>Equations: {analysis?.equations?.length || 0}</span>
        <span>
          Input: {documentStatus.status || "not_provided"}
          {documentStatus.status === "ok" && documentStatus.extractor
            ? ` via ${
                documentStatus.extractor === "marker"
                  ? documentStatus.ocr_enabled
                    ? "Marker OCR"
                    : "Marker structured parser"
                  : documentStatus.extractor === "latex_ocr"
                    ? "LaTeX-OCR"
                  : "fast parser"
              }`
            : ""}
        </span>
        <span>Auto-save: local state only</span>
      </footer>
    </div>
  );
}
