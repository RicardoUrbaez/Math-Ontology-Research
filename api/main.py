from __future__ import annotations

from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from api.services import MathKGService


app = FastAPI(
    title="Math Accessibility Knowledge Graph API",
    description="FastAPI endpoints for semantic search, cross-disciplinary discovery, concept recommendation, and LaTeX accessibility glosses.",
    version="0.1.0",
)
service = MathKGService()


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

