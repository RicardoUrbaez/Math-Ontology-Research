from __future__ import annotations

from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from api.paper_jobs import PaperJobManager
from api.services import DEFAULT_PAPER_AUDIO_DIR, MathKGService


app = FastAPI(
    title="Math Accessibility Knowledge Graph API",
    description="FastAPI endpoints for semantic search, cross-disciplinary discovery, concept recommendation, and LaTeX accessibility glosses.",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)
DEFAULT_PAPER_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
app.mount(
    "/api/generated-audio",
    StaticFiles(directory=str(DEFAULT_PAPER_AUDIO_DIR)),
    name="generated-audio",
)
service = MathKGService()
paper_jobs = PaperJobManager(service.analyze_paper)


class SearchResponse(BaseModel):
    query: str
    results: list[dict]


class DiscoveryRequest(BaseModel):
    seed_concept: str | None = Field(default=None, description="Concept label or IRI to bridge from.")
    source_domain: str | None = Field(default=None, description="Optional source domain when no seed concept is supplied.")
    target_domains: list[str] = Field(default_factory=list)
    semantic_type: str | None = None
    limit: int = Field(default=10, ge=1, le=50)


class RecommenderRequest(BaseModel):
    context: str = ""
    latex: str = ""
    seed_concepts: list[str] = Field(default_factory=list)
    domain_tags: list[str] = Field(default_factory=list)
    limit: int = Field(default=10, ge=1, le=50)


class AccessibilityRequest(BaseModel):
    latex: str = Field(..., min_length=1)
    audience: Literal["concise", "pedagogical", "expert", "document_role"] = "concise"
    arxiv_id: str = "ad-hoc"
    title: str = "Ad-hoc equation"


class PaperAnalysisRequest(BaseModel):
    title: str = "Untitled paper"
    abstract_or_context: str = ""
    equations: list[str] = Field(default_factory=list)
    audience: Literal["concise", "pedagogical", "expert", "document_role"] = "pedagogical"
    audio_backend: Literal["none", "mock", "gtts", "kokoro", "azure"] = "none"
    generate_audio: bool = False
    pdf_base64: str = ""
    pdf_filename: str = ""
    document_base64: str = ""
    document_filename: str = ""
    document_media_type: str = ""


@app.get("/health")
def health() -> dict:
    return service.health()


@app.get("/api/search", response_model=SearchResponse)
def semantic_search(
    q: str = Query(..., min_length=1, description="Search text, concept label, or domain term."),
    limit: int = Query(10, ge=1, le=50),
    domain: list[str] = Query(default=[]),
    semantic_type: str | None = None,
    kind_role: str | None = None,
) -> dict:
    return {
        "query": q,
        "results": service.semantic_search(
            q,
            limit=limit,
            domain_tags=domain,
            semantic_type=semantic_type,
            kind_role=kind_role,
        ),
    }


@app.post("/api/discover")
def cross_disciplinary_discovery(request: DiscoveryRequest) -> dict:
    return service.cross_disciplinary_discovery(
        seed_concept=request.seed_concept,
        source_domain=request.source_domain,
        target_domains=request.target_domains,
        semantic_type=request.semantic_type,
        limit=request.limit,
    )


@app.post("/api/recommend")
def concept_recommender(request: RecommenderRequest) -> dict:
    return service.recommend_concepts(
        context=request.context,
        latex=request.latex,
        seed_concepts=request.seed_concepts,
        domain_tags=request.domain_tags,
        limit=request.limit,
    )


@app.post("/api/accessibility/latex-gloss")
def latex_accessibility_gloss(request: AccessibilityRequest) -> dict:
    try:
        return service.latex_accessibility_gloss(
            latex=request.latex,
            audience=request.audience,
            arxiv_id=request.arxiv_id,
            title=request.title,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/paper/analyze")
def paper_analysis(request: PaperAnalysisRequest) -> dict:
    return service.analyze_paper(
        title=request.title,
        abstract_or_context=request.abstract_or_context,
        equations=request.equations,
        audience=request.audience,
        audio_backend=request.audio_backend,
        generate_audio=request.generate_audio,
        pdf_base64=request.pdf_base64,
        pdf_filename=request.pdf_filename,
        document_base64=request.document_base64,
        document_filename=request.document_filename,
        document_media_type=request.document_media_type,
    )


@app.post("/api/paper/jobs", status_code=202)
def create_paper_analysis_job(request: PaperAnalysisRequest) -> dict:
    return paper_jobs.create(request.model_dump())


@app.get("/api/paper/jobs/{job_id}")
def get_paper_analysis_job(job_id: str) -> dict:
    job = paper_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Paper analysis job was not found.")
    return job
