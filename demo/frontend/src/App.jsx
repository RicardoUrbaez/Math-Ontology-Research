import { useEffect, useMemo, useState } from "react";
import { analyzePaper, fileToBase64, getHealth } from "./api.js";
import { audiences, backends, samplePaper } from "./sampleData.js";
import { Icon } from "./icons.jsx";

function splitEquations(value) {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
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
    pdf: { status: "not_provided", detail: "No PDF payload supplied.", extractor: "pypdf" },
    extracted_equation_count: 0
  };
}

function StatusPill({ health, loading }) {
  const ok = health?.api === "ok" || health?.status === "ok";
  return (
    <div className={`status-pill ${ok ? "ready" : ""}`}>
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
        <span>MathOntoSpeak</span>
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

function PaperInput({
  title,
  setTitle,
  context,
  setContext,
  equations,
  setEquations,
  pdfFile,
  onPdf,
  onAnalyze,
  loading
}) {
  return (
    <section className="panel input-panel" aria-labelledby="input-heading">
      <div className="panel-heading">
        <span>1.</span>
        <h2 id="input-heading">Input: Paper & Equations</h2>
      </div>
      <label>
        Paper title
        <input value={title} onChange={(event) => setTitle(event.target.value)} />
      </label>
      <label className="drop-zone">
        <Icon name="upload" />
        <span>{pdfFile ? pdfFile.name : "Upload PDF (optional)"}</span>
        <small>
          {pdfFile
            ? `${(pdfFile.size / 1024 / 1024).toFixed(2)} MB`
            : "Automatic text and equation OCR"}
        </small>
        <input type="file" accept="application/pdf" onChange={onPdf} />
      </label>
      <label>
        Abstract / context
        <textarea value={context} onChange={(event) => setContext(event.target.value)} rows={10} />
      </label>
      <label>
        Equations in paper
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
      <button className="primary-button" type="button" onClick={onAnalyze} disabled={loading}>
        <Icon name="spark" />
        {loading ? "Analyzing" : "Analyze paper"}
      </button>
    </section>
  );
}

function EquationList({ equations, selectedIndex, setSelectedIndex }) {
  if (!equations.length) {
    return <p className="empty-note">No equations have been analyzed yet.</p>;
  }
  return (
    <div className="equation-list" aria-label="Analyzed equations">
      {equations.map((equation, index) => (
        <button
          key={`${equation.latex}-${index}`}
          className={selectedIndex === index ? "selected" : ""}
          type="button"
          onClick={() => setSelectedIndex(index)}
        >
          <span>{index + 1}</span>
          <strong>{equation.latex}</strong>
          <small>{equation.resolved_count} resolved</small>
        </button>
      ))}
    </div>
  );
}

function AnalysisPanel({ analysis, selectedIndex, setSelectedIndex }) {
  const equations = analysis?.equations || [];
  const equation = equations[selectedIndex] || equations[0];
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

  return (
    <section className="panel analysis-panel" aria-labelledby="analysis-heading">
      <div className="analysis-header">
        <div className="panel-heading">
          <span>2.</span>
          <h2 id="analysis-heading">Equation Analysis</h2>
        </div>
        <div className="stepper" aria-label="Selected equation">
          <button type="button" onClick={() => setSelectedIndex(Math.max(0, selectedIndex - 1))}>
            Prev
          </button>
          <strong>{equations.length ? `${selectedIndex + 1} of ${equations.length}` : "0 of 0"}</strong>
          <button type="button" onClick={() => setSelectedIndex(Math.min(equations.length - 1, selectedIndex + 1))}>
            Next
          </button>
        </div>
      </div>
      <EquationList equations={equations} selectedIndex={selectedIndex} setSelectedIndex={setSelectedIndex} />
      {equation ? (
        <div className="analysis-stack">
          <Readout title="Raw LaTeX" text={equation.latex} mono />
          <Readout title="Plain Notation Reading" text={equation.plain_notation_reading} />
          <Readout title="Context Summary" text={equation.context_summary} accent />
          <TermExplanationTable terms={equation.term_explanations || []} />
          <Readout title="Spoken Script" text={equation.spoken_script || equation.semantic_reading} />
          <Readout title="Contextual Explanation" text={equation.contextual_explanation} />
          <div>
            <h3>Ontology Evidence</h3>
            <div className="concept-table">
              {visibleConceptRows.slice(0, 8).map((row, index) => (
                <div className="concept-row" key={`${row.label}-${index}`}>
                  <span className="symbol">{row.symbol}</span>
                  <strong>{row.label}</strong>
                  <small>{row.domain}</small>
                  <em>{row.confidence}</em>
                </div>
              ))}
              {!visibleConceptRows.length && (
                <p className="empty-note">No ontology concepts resolved for this equation.</p>
              )}
            </div>
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

  function speak() {
    if (!selectedEquation || !window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const script = selectedEquation.spoken_script || selectedEquation.semantic_reading;
    const utterance = new SpeechSynthesisUtterance(script);
    utterance.rate = 0.95;
    utterance.onend = () => setSpeaking(false);
    setSpeaking(true);
    window.speechSynthesis.speak(utterance);
  }

  function stop() {
    window.speechSynthesis?.cancel();
    setSpeaking(false);
  }

  return (
    <section className="panel evidence-panel" aria-labelledby="evidence-heading">
      <div className="panel-heading">
        <span>3.</span>
        <h2 id="evidence-heading">Audio & Evidence</h2>
      </div>
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
      <label className="toggle-line">
        <input
          type="checkbox"
          checked={generateAudio}
          onChange={(event) => setGenerateAudio(event.target.checked)}
        />
        Generate backend audio artifact
      </label>
      <div className="callout">
        Azure Speech is optional. If credentials are missing, the API reports that safely and keeps the analysis visible.
      </div>
      <div className="play-row">
        <button className="primary-button" type="button" onClick={speaking ? stop : speak}>
          <Icon name={speaking ? "stop" : "play"} />
          {speaking ? "Stop" : "Play with context"}
        </button>
        <button className="secondary-button" type="button" onClick={speak}>
          <Icon name="wave" />
          Replay
        </button>
      </div>
      <div className="evidence-tabs">
        <h3>Linked Text Span</h3>
        <p>
          {selectedEquation?.context_evidence?.[0]?.text ||
            selectedEquation?.linked_text_span ||
            "Analyze a paper to connect the equation back to nearby text."}
        </p>
        <h3>ASR / Evaluation (Whisper)</h3>
        <p>
          Whisper remains an evaluation layer: generate speech, transcribe it, then compare concept-keyword recall and WER.
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
  const [analysis, setAnalysis] = useState(defaultAnalysis);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [health, setHealth] = useState(null);
  const [healthLoading, setHealthLoading] = useState(true);

  const selectedEquation = useMemo(() => analysis?.equations?.[selectedIndex] || analysis?.equations?.[0], [analysis, selectedIndex]);

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => setHealth(null))
      .finally(() => setHealthLoading(false));
  }, []);

  async function onPdf(event) {
    const file = event.target.files?.[0];
    setPdfFile(file || null);
    if (file) {
      setEquations("");
      if (title === samplePaper.title) {
        setTitle(file.name.replace(/\.pdf$/i, ""));
      }
    }
    setPdfBase64(file ? await fileToBase64(file) : "");
  }

  async function onAnalyze() {
    setLoading(true);
    setError("");
    try {
      const payload = await analyzePaper({
        title,
        abstract_or_context: context,
        equations: splitEquations(equations),
        audience,
        audio_backend: backend,
        generate_audio: generateAudio,
        pdf_base64: pdfBase64,
        pdf_filename: pdfFile?.name || ""
      });
      setAnalysis(payload);
      setSelectedIndex(0);
    } catch (exc) {
      setError(exc.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app-shell">
      <Header health={health} loading={healthLoading} />
      {error ? <div className="error-banner">{error}</div> : null}
      <main className="workspace">
        <PaperInput
          title={title}
          setTitle={setTitle}
          context={context}
          setContext={setContext}
          equations={equations}
          setEquations={setEquations}
          pdfFile={pdfFile}
          onPdf={onPdf}
          onAnalyze={onAnalyze}
          loading={loading}
        />
        <AnalysisPanel analysis={analysis} selectedIndex={selectedIndex} setSelectedIndex={setSelectedIndex} />
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
      <footer className="app-footer">
        <span>Project: paper equation demo</span>
        <span>Equations: {analysis?.equations?.length || 0}</span>
        <span>
          PDF: {analysis?.pdf?.status || "not_provided"}
          {analysis?.pdf?.status === "ok" && analysis?.pdf?.extractor
            ? ` via ${analysis.pdf.extractor === "marker" ? "Marker OCR" : "fast parser"}`
            : ""}
        </span>
        <span>Auto-save: local state only</span>
      </footer>
    </div>
  );
}
