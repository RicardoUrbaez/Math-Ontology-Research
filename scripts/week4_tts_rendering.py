"""Week 4 TTS rendering utilities for MathOntoSpeak.

This module turns a gloss metadata record into the four planned surface forms,
wraps each form in math-aware SSML, and sends the output to a selectable TTS
backend. Azure Speech and gTTS are optional runtime integrations; the mock
backend keeps the pipeline testable without credentials or network access.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Protocol
from xml.sax.saxutils import escape


ROOT = Path(__file__).resolve().parents[1]
SURFACE_FIELDS = ("concise_form", "pedagogical_form", "expert_form", "document_role_form")


@dataclass(frozen=True)
class MathProsodyProfile:
    """Prosody parameters tuned for spoken mathematical glosses."""

    name: str = "math-default"
    rate: str = "-8%"
    pitch: str = "+1st"
    volume: str = "medium"
    concept_pause_ms: int = 320
    clause_pause_ms: int = 180
    sentence_pause_ms: int = 420


@dataclass(frozen=True)
class SurfaceFormBundle:
    concept_iri: str
    canonical_label: str
    semantic_type: str
    concise_form: str
    pedagogical_form: str
    expert_form: str
    document_role_form: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class SynthesisResult:
    backend: str
    surface_name: str
    audio_path: str
    ssml_path: str
    status: str
    detail: str


@dataclass(frozen=True)
class ArxivEquation:
    arxiv_id: str
    title: str
    latex: str
    source_context: str = ""


@dataclass(frozen=True)
class LatexSemanticToken:
    raw: str
    token_type: str
    spoken: str
    concept_iri: str = ""
    canonical_label: str = ""
    source: str = "unresolved"


@dataclass(frozen=True)
class EquationSpeechBundle:
    arxiv_id: str
    title: str
    latex: str
    plain_text: str
    speech_text: str
    ssml: str
    tokens: list[LatexSemanticToken]


@dataclass(frozen=True)
class EquationSynthesisResult:
    arxiv_id: str
    title: str
    latex: str
    token_count: int
    resolved_count: int
    concepts: list[str]
    backend: str
    audio_path: str
    ssml_path: str
    status: str
    detail: str


class TTSBackend(Protocol):
    name: str

    def synthesize(self, text: str, ssml: str, output_path: Path) -> SynthesisResult:
        ...


SYMBOL_CONCEPT_HINTS = {
    "\\frac": "Division",
    "\\dfrac": "Division",
    "\\tfrac": "Division",
    "\\sum": "Addition",
    "\\prod": "Multiplication",
    "\\int": "Integral",
    "\\oint": "Integral",
    "\\partial": "Derivative",
    "\\nabla": "Gradient",
    "\\log": "Logarithm",
    "\\ln": "Logarithm",
    "\\exp": "Exponential Function",
    "\\sin": "Sine",
    "\\cos": "Cosine",
    "\\tan": "Tangent",
    "\\sqrt": "Exponentiating",
    "\\in": "Element",
    "\\notin": "Element",
    "\\subset": "Subset",
    "\\subseteq": "Subset",
    "\\cap": "Intersection",
    "\\cup": "Join",
    "\\to": "Map",
    "\\rightarrow": "Map",
    "\\mapsto": "Map",
    "\\hookrightarrow": "Embedding",
    "\\le": "Inequality",
    "\\leq": "Inequality",
    "\\ge": "Inequality",
    "\\geq": "Inequality",
    "\\lt": "Inequality",
    "\\gt": "Inequality",
    "\\neq": "Inequality",
    "\\ne": "Inequality",
    "\\times": "Multiplication",
    "\\cdot": "Multiplication",
    "\\ast": "Multiplication",
    "\\pm": "Addition",
    "=": "Equality",
    "<": "Inequality",
    ">": "Inequality",
    "+": "Addition",
    "-": "Subtraction",
    "/": "Division",
    "^": "Exponentiating",
    "|": "Norm",
}


NUMBER_SET_LABELS = {
    "N": ("Natural Number", "natural numbers"),
    "Z": ("Integer", "integers"),
    "Q": ("Rational Number", "rational numbers"),
    "R": ("Real Number", "real numbers"),
    "C": ("Complex Number", "complex numbers"),
}


GREEK_IDENTIFIER_MACROS = {
    "\\alpha",
    "\\beta",
    "\\gamma",
    "\\Gamma",
    "\\delta",
    "\\Delta",
    "\\epsilon",
    "\\varepsilon",
    "\\zeta",
    "\\eta",
    "\\theta",
    "\\Theta",
    "\\iota",
    "\\kappa",
    "\\lambda",
    "\\Lambda",
    "\\mu",
    "\\nu",
    "\\xi",
    "\\Xi",
    "\\pi",
    "\\Pi",
    "\\rho",
    "\\sigma",
    "\\Sigma",
    "\\tau",
    "\\upsilon",
    "\\phi",
    "\\varphi",
    "\\Phi",
    "\\chi",
    "\\psi",
    "\\Psi",
    "\\omega",
    "\\Omega",
    "\\ell",
}


def _sentence(value: str) -> str:
    value = re.sub(r"\s+", " ", value or "").strip()
    if not value:
        return ""
    return value if value.endswith((".", "!", "?")) else f"{value}."


def _lower_first(value: str) -> str:
    value = value.strip()
    if not value:
        return value
    return value[:1].lower() + value[1:]


def _definition_from_record(record: dict[str, Any]) -> str:
    for key in ("skos_definition", "definition", "canonical_definition"):
        if record.get(key):
            return _sentence(str(record[key]))
    canonical_gloss = str(record.get("canonical_gloss", "")).strip()
    if ":" in canonical_gloss:
        return _sentence(canonical_gloss.split(":", 1)[1])
    return _sentence(canonical_gloss)


def _normalize_lookup_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _unique_labels(tokens: list[LatexSemanticToken]) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        if not token.canonical_label:
            continue
        key = _normalize_lookup_key(token.canonical_label)
        if key and key not in seen:
            seen.add(key)
            labels.append(token.canonical_label)
    return labels


class GlossRepository:
    """Fast gloss metadata lookup by concept IRI or canonical label."""

    def __init__(self, records: list[dict[str, Any]]) -> None:
        self.records = records
        self.by_iri: dict[str, dict[str, Any]] = {}
        self.by_label: dict[str, dict[str, Any]] = {}
        for record in records:
            iri = str(record.get("concept_IRI") or record.get("concept_iri") or "").strip()
            label = str(record.get("canonical_label") or record.get("rdfs_label") or "").strip()
            if iri:
                self.by_iri[iri] = record
            if label:
                self.by_label[_normalize_lookup_key(label)] = record

    @classmethod
    def from_json(cls, path: Path) -> "GlossRepository":
        return cls(load_gloss_records(path))

    def get_by_iri(self, iri: str) -> dict[str, Any] | None:
        return self.by_iri.get(iri)

    def get_by_label(self, label: str) -> dict[str, Any] | None:
        return self.by_label.get(_normalize_lookup_key(label))


class SymbolConceptLookup:
    """Map parsed LaTeX symbols to canonical concept records."""

    def __init__(self, gloss_repository: GlossRepository) -> None:
        self.gloss_repository = gloss_repository

    def resolve(self, token: LatexSemanticToken) -> LatexSemanticToken:
        label = token.canonical_label
        if not label and token.raw in SYMBOL_CONCEPT_HINTS:
            label = SYMBOL_CONCEPT_HINTS[token.raw]
        if not label and token.token_type == "number":
            label = "Number"
        if not label and (token.token_type == "identifier" or token.raw in GREEK_IDENTIFIER_MACROS):
            label = "Variable"
        if not label:
            return token

        record = self.gloss_repository.get_by_label(label)
        if not record:
            return replace(token, canonical_label=label)

        return replace(
            token,
            concept_iri=str(record.get("concept_IRI") or record.get("concept_iri") or ""),
            canonical_label=str(record.get("canonical_label") or label),
            source="gloss_dictionary",
        )


def _node_latex(node: Any) -> str:
    latex_verbatim = getattr(node, "latex_verbatim", None)
    if callable(latex_verbatim):
        return str(latex_verbatim())
    return ""


def _latex_group_text(node: Any) -> str:
    nodelist = getattr(node, "nodelist", None)
    if not nodelist:
        return ""
    chars: list[str] = []
    for child in nodelist:
        if child.__class__.__name__ == "LatexCharsNode":
            chars.append(str(getattr(child, "chars", "")))
    return "".join(chars).strip()


def _styled_number_set_token(node: Any) -> LatexSemanticToken | None:
    if getattr(node, "macroname", "") != "mathbb":
        return None
    argnlist = list(getattr(getattr(node, "nodeargd", None), "argnlist", []) or [])
    if not argnlist:
        return None
    label_and_spoken = NUMBER_SET_LABELS.get(_latex_group_text(argnlist[0]))
    if not label_and_spoken:
        return None
    label, spoken = label_and_spoken
    return LatexSemanticToken(
        raw=_node_latex(node) or f"\\mathbb{{{_latex_group_text(argnlist[0])}}}",
        token_type="macro",
        spoken=spoken,
        canonical_label=label,
    )


def _tokens_from_chars(chars: str) -> list[LatexSemanticToken]:
    tokens: list[LatexSemanticToken] = []
    index = 0
    while index < len(chars):
        char = chars[index]
        if char.isspace() or char in "{}_(),;:":
            index += 1
            continue
        if char.isdigit():
            start = index
            index += 1
            while index < len(chars) and (chars[index].isdigit() or chars[index] == "."):
                index += 1
            raw = chars[start:index]
            tokens.append(LatexSemanticToken(raw=raw, token_type="number", spoken=raw))
            continue
        if char.isalpha():
            tokens.append(LatexSemanticToken(raw=char, token_type="identifier", spoken=char))
            index += 1
            continue
        if char in SYMBOL_CONCEPT_HINTS:
            tokens.append(LatexSemanticToken(raw=char, token_type="operator", spoken=char))
        index += 1
    return tokens


def parse_latex_tokens(latex: str) -> list[LatexSemanticToken]:
    """Parse LaTeX math with pylatexenc and emit a flat semantic token stream."""

    try:
        from pylatexenc.latexwalker import LatexWalker
    except ImportError as exc:
        raise RuntimeError("Install pylatexenc with `pip install pylatexenc` to parse LaTeX equations.") from exc

    walker = LatexWalker(latex)
    nodes, _, _ = walker.get_latex_nodes()
    tokens: list[LatexSemanticToken] = []

    def visit_list(nodelist: list[Any]) -> None:
        for child in nodelist:
            visit(child)

    def visit(node: Any) -> None:
        node_type = node.__class__.__name__
        if node_type == "LatexCharsNode":
            tokens.extend(_tokens_from_chars(str(getattr(node, "chars", ""))))
            return
        if node_type == "LatexMacroNode":
            styled_token = _styled_number_set_token(node)
            if styled_token:
                tokens.append(styled_token)
                return
            raw = f"\\{getattr(node, 'macroname', '')}"
            tokens.append(LatexSemanticToken(raw=raw, token_type="macro", spoken=raw))
            for arg in list(getattr(getattr(node, "nodeargd", None), "argnlist", []) or []):
                if arg is not None:
                    visit(arg)
            return
        if hasattr(node, "nodelist"):
            visit_list(list(getattr(node, "nodelist") or []))
            return
        for arg in list(getattr(getattr(node, "nodeargd", None), "argnlist", []) or []):
            if arg is not None:
                visit(arg)

    visit_list(list(nodes))
    return tokens


def resolve_latex_tokens(tokens: list[LatexSemanticToken], lookup: SymbolConceptLookup) -> list[LatexSemanticToken]:
    return [lookup.resolve(token) for token in tokens]


def latex_to_plain_text(latex: str) -> str:
    try:
        from pylatexenc.latex2text import LatexNodes2Text
    except ImportError:
        return re.sub(r"\s+", " ", latex).strip()
    plain = LatexNodes2Text().latex_to_text(latex)
    return re.sub(r"\s+", " ", plain).strip()


def build_equation_speech_bundle(
    equation: ArxivEquation,
    gloss_repository: GlossRepository,
    lookup: SymbolConceptLookup | None = None,
    voice: str = "en-US-JennyNeural",
) -> EquationSpeechBundle:
    lookup = lookup or SymbolConceptLookup(gloss_repository)
    tokens = resolve_latex_tokens(parse_latex_tokens(equation.latex), lookup)
    labels = _unique_labels(tokens)
    gloss_phrases: list[str] = []
    for label in labels[:4]:
        record = gloss_repository.get_by_label(label)
        if not record:
            continue
        gloss_phrases.append(f"{label} means {_lower_first(_definition_from_record(record).rstrip('.'))}.")
    concept_clause = ", ".join(labels[:8]) if labels else "no matched ontology concepts"
    plain_text = latex_to_plain_text(equation.latex)
    speech_text = _sentence(
        f"arXiv {equation.arxiv_id}. Equation {plain_text}. "
        f"Matched concepts: {concept_clause}. {' '.join(gloss_phrases)}"
    )
    return EquationSpeechBundle(
        arxiv_id=equation.arxiv_id,
        title=equation.title,
        latex=equation.latex,
        plain_text=plain_text,
        speech_text=speech_text,
        ssml=assemble_ssml(speech_text, voice=voice),
        tokens=tokens,
    )


def build_surface_forms(record: dict[str, Any]) -> SurfaceFormBundle:
    """Generate or normalize the four TTS surface forms from one gloss record."""

    label = str(record.get("canonical_label") or record.get("rdfs_label") or "Unknown concept").strip()
    lower = label.lower()
    concept_iri = str(record.get("concept_IRI") or record.get("concept_iri") or "")
    semantic_type = str(record.get("semantic_type") or "mathematical").strip()
    source = str(record.get("source_provenance") or record.get("source") or "the merged ontology").strip()
    definition = _definition_from_record(record) or f"{label} is a mathematical concept."
    definition_phrase = _lower_first(definition.rstrip("."))

    generated = {
        "concise_form": f"{label}: {definition}",
        "pedagogical_form": f"Think of {lower} as {definition_phrase}.",
        "expert_form": f"{label} denotes {definition_phrase}.",
        "document_role_form": (
            f"In a mathematical document, {lower} usually signals a {semantic_type} "
            f"concept with provenance from {source}."
        ),
    }
    forms = {field: _sentence(str(record.get(field) or generated[field])) for field in SURFACE_FIELDS}
    return SurfaceFormBundle(
        concept_iri=concept_iri,
        canonical_label=label,
        semantic_type=semantic_type,
        concise_form=forms["concise_form"],
        pedagogical_form=forms["pedagogical_form"],
        expert_form=forms["expert_form"],
        document_role_form=forms["document_role_form"],
    )


def _math_phrase_markup(text: str, profile: MathProsodyProfile) -> str:
    """Escape text and insert pauses where math glosses benefit from breathing room."""

    escaped = escape(text, {'"': "&quot;"})
    escaped = re.sub(
        r"^([^:]{1,80}):\s+",
        f'\\1:<break time="{profile.concept_pause_ms}ms"/> ',
        escaped,
        count=1,
    )
    escaped = re.sub(
        r";\s+",
        f';<break time="{profile.clause_pause_ms}ms"/> ',
        escaped,
    )
    escaped = re.sub(
        r"([.!?])\s+",
        f'\\1<break time="{profile.sentence_pause_ms}ms"/> ',
        escaped,
    )
    return escaped


def assemble_ssml(
    text: str,
    profile: MathProsodyProfile | None = None,
    voice: str = "en-US-JennyNeural",
    language: str = "en-US",
) -> str:
    """Build Azure-compatible SSML with conservative math prosody."""

    profile = profile or MathProsodyProfile()
    marked_text = _math_phrase_markup(text, profile)
    return (
        f'<speak version="1.0" xml:lang="{language}" '
        'xmlns="http://www.w3.org/2001/10/synthesis">'
        f'<voice name="{escape(voice)}">'
        f'<prosody rate="{profile.rate}" pitch="{profile.pitch}" volume="{profile.volume}">'
        f"{marked_text}"
        "</prosody>"
        "</voice>"
        "</speak>"
    )


def validate_ssml(ssml: str) -> None:
    ET.fromstring(ssml)


def write_ssml_bundle(
    bundle: SurfaceFormBundle,
    output_dir: Path,
    profile: MathProsodyProfile | None = None,
    voice: str = "en-US-JennyNeural",
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = re.sub(r"[^A-Za-z0-9]+", "_", bundle.canonical_label).strip("_") or "concept"
    paths: dict[str, Path] = {}
    for surface_name in SURFACE_FIELDS:
        text = getattr(bundle, surface_name)
        ssml = assemble_ssml(text, profile=profile, voice=voice)
        validate_ssml(ssml)
        path = output_dir / f"{stem}_{surface_name}.ssml"
        path.write_text(ssml, encoding="utf-8")
        paths[surface_name] = path
    return paths


class MockTTSBackend:
    name = "mock"

    def synthesize(self, text: str, ssml: str, output_path: Path) -> SynthesisResult:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps({"backend": self.name, "text": text, "ssml": ssml}, indent=2),
            encoding="utf-8",
        )
        return SynthesisResult(self.name, output_path.stem, str(output_path), "", "ok", "mock artifact written")


class GTTSBackend:
    name = "gtts"

    def __init__(self, language: str = "en") -> None:
        self.language = language

    def synthesize(self, text: str, ssml: str, output_path: Path) -> SynthesisResult:
        try:
            from gtts import gTTS
        except ImportError as exc:
            raise RuntimeError("Install gTTS with `pip install gTTS` to use the gtts backend.") from exc

        output_path.parent.mkdir(parents=True, exist_ok=True)
        gTTS(text=text, lang=self.language).save(str(output_path))
        return SynthesisResult(self.name, output_path.stem, str(output_path), "", "ok", "gTTS MP3 written")


class AzureTTSBackend:
    name = "azure"

    def __init__(self, speech_key: str | None = None, speech_region: str | None = None) -> None:
        self.speech_key = speech_key or os.getenv("AZURE_SPEECH_KEY")
        self.speech_region = speech_region or os.getenv("AZURE_SPEECH_REGION")

    def synthesize(self, text: str, ssml: str, output_path: Path) -> SynthesisResult:
        if not self.speech_key or not self.speech_region:
            raise RuntimeError("Set AZURE_SPEECH_KEY and AZURE_SPEECH_REGION to use the Azure backend.")
        try:
            import azure.cognitiveservices.speech as speechsdk
        except ImportError as exc:
            raise RuntimeError(
                "Install Azure Speech with `pip install azure-cognitiveservices-speech` to use the Azure backend."
            ) from exc

        output_path.parent.mkdir(parents=True, exist_ok=True)
        speech_config = speechsdk.SpeechConfig(subscription=self.speech_key, region=self.speech_region)
        audio_config = speechsdk.audio.AudioOutputConfig(filename=str(output_path))
        synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
        result = synthesizer.speak_ssml_async(ssml).get()
        if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
            detail = getattr(result, "cancellation_details", result.reason)
            raise RuntimeError(f"Azure synthesis failed: {detail}")
        return SynthesisResult(self.name, output_path.stem, str(output_path), "", "ok", "Azure WAV written")


def backend_for(name: str) -> TTSBackend:
    normalized = name.lower()
    if normalized == "mock":
        return MockTTSBackend()
    if normalized == "gtts":
        return GTTSBackend()
    if normalized == "azure":
        return AzureTTSBackend()
    raise ValueError(f"Unknown backend: {name}")


def synthesize_bundle(
    bundle: SurfaceFormBundle,
    backend: TTSBackend,
    output_dir: Path,
    profile: MathProsodyProfile | None = None,
    voice: str = "en-US-JennyNeural",
) -> list[SynthesisResult]:
    output_dir.mkdir(parents=True, exist_ok=True)
    ssml_dir = output_dir / "ssml"
    audio_dir = output_dir / backend.name
    ssml_paths = write_ssml_bundle(bundle, ssml_dir, profile=profile, voice=voice)
    stem = re.sub(r"[^A-Za-z0-9]+", "_", bundle.canonical_label).strip("_") or "concept"
    extension = ".mp3" if backend.name == "gtts" else ".wav" if backend.name == "azure" else ".json"
    results: list[SynthesisResult] = []
    for surface_name in SURFACE_FIELDS:
        text = getattr(bundle, surface_name)
        ssml_path = ssml_paths[surface_name]
        ssml = ssml_path.read_text(encoding="utf-8")
        audio_path = audio_dir / f"{stem}_{surface_name}{extension}"
        result = backend.synthesize(text, ssml, audio_path)
        results.append(
            SynthesisResult(
                backend=result.backend,
                surface_name=surface_name,
                audio_path=result.audio_path,
                ssml_path=str(ssml_path),
                status=result.status,
                detail=result.detail,
            )
        )
    return results


def load_gloss_records(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_arxiv_equations(path: Path) -> list[ArxivEquation]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [
            ArxivEquation(
                arxiv_id=row["arxiv_id"],
                title=row["title"],
                latex=row["latex_equation"],
                source_context=row.get("source_context", ""),
            )
            for row in csv.DictReader(handle)
        ]


def _safe_equation_stem(index: int, equation: ArxivEquation) -> str:
    arxiv_id = re.sub(r"[^A-Za-z0-9]+", "_", equation.arxiv_id).strip("_")
    return f"eq_{index:03d}_{arxiv_id or 'arxiv'}"


def synthesize_equation_bundle(
    bundle: EquationSpeechBundle,
    backend: TTSBackend,
    output_dir: Path,
    index: int,
) -> EquationSynthesisResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    ssml_dir = output_dir / "equation_ssml"
    audio_dir = output_dir / f"equation_{backend.name}"
    ssml_dir.mkdir(parents=True, exist_ok=True)
    audio_dir.mkdir(parents=True, exist_ok=True)

    stem = _safe_equation_stem(index, ArxivEquation(bundle.arxiv_id, bundle.title, bundle.latex))
    ssml_path = ssml_dir / f"{stem}.ssml"
    validate_ssml(bundle.ssml)
    ssml_path.write_text(bundle.ssml, encoding="utf-8")

    extension = ".mp3" if backend.name == "gtts" else ".wav" if backend.name == "azure" else ".json"
    audio_path = audio_dir / f"{stem}{extension}"
    result = backend.synthesize(bundle.speech_text, bundle.ssml, audio_path)
    labels = _unique_labels(bundle.tokens)
    return EquationSynthesisResult(
        arxiv_id=bundle.arxiv_id,
        title=bundle.title,
        latex=bundle.latex,
        token_count=len(bundle.tokens),
        resolved_count=sum(1 for token in bundle.tokens if token.concept_iri),
        concepts=labels,
        backend=result.backend,
        audio_path=result.audio_path,
        ssml_path=str(ssml_path),
        status=result.status,
        detail=result.detail,
    )


def run_latex_audio_pipeline(
    equations: list[ArxivEquation],
    gloss_path: Path,
    backend: TTSBackend,
    output_dir: Path,
    limit: int = 20,
    voice: str = "en-US-JennyNeural",
) -> list[EquationSynthesisResult]:
    gloss_repository = GlossRepository.from_json(gloss_path)
    lookup = SymbolConceptLookup(gloss_repository)
    results: list[EquationSynthesisResult] = []
    for index, equation in enumerate(equations[:limit], start=1):
        bundle = build_equation_speech_bundle(equation, gloss_repository, lookup=lookup, voice=voice)
        results.append(synthesize_equation_bundle(bundle, backend, output_dir, index))
    return results


def run_cli() -> None:
    parser = argparse.ArgumentParser(description="Generate Week 4 SSML/audio artifacts from gloss metadata or LaTeX equations.")
    parser.add_argument("--gloss", type=Path, default=ROOT / "gloss" / "week3_gloss_dictionary.json")
    parser.add_argument("--equations", type=Path, help="CSV fixture with arXiv LaTeX equations for end-to-end rendering.")
    parser.add_argument("--out", type=Path, default=ROOT / "reports" / "audio" / "week4_tts")
    parser.add_argument("--backend", choices=("mock", "gtts", "azure"), default="mock")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--voice", default="en-US-JennyNeural")
    args = parser.parse_args()

    backend = backend_for(args.backend)
    if args.equations:
        equations = load_arxiv_equations(args.equations)
        results = run_latex_audio_pipeline(
            equations,
            gloss_path=args.gloss,
            backend=backend,
            output_dir=args.out,
            limit=args.limit,
            voice=args.voice,
        )
        manifest_path = args.out / f"week4_latex_audio_{args.backend}_manifest.json"
        manifest_path.write_text(json.dumps([asdict(result) for result in results], indent=2), encoding="utf-8")
        print(f"Wrote {len(results)} equation synthesis artifacts to {args.out}")
        print(f"Manifest: {manifest_path}")
        return

    records = load_gloss_records(args.gloss)[: args.limit]
    manifest: list[dict[str, str]] = []
    for record in records:
        bundle = build_surface_forms(record)
        for result in synthesize_bundle(bundle, backend, args.out, voice=args.voice):
            manifest.append(asdict(result))
    manifest_path = args.out / f"week4_tts_{args.backend}_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote {len(manifest)} synthesis artifacts to {args.out}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    run_cli()
