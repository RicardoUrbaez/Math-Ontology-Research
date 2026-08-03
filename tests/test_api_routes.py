import json
import tempfile
import unittest
import time
from pathlib import Path

from fastapi.testclient import TestClient

from api.main import app
from api.paper_jobs import PaperJobManager

class MathKGAPIRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_search_route(self):
        response = self.client.get("/api/search", params={"q": "matrix", "limit": 2})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["query"], "matrix")
        self.assertEqual(payload["results"][0]["canonical_label"], "Matrix")

    def test_discovery_route(self):
        response = self.client.post(
            "/api/discover",
            json={"seed_concept": "Matrix", "target_domains": ["calculus"], "limit": 2},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["seed"]["canonical_label"], "Matrix")

    def test_recommender_route(self):
        response = self.client.post(
            "/api/recommend",
            json={"latex": r"S=\sum_k a_k X_k", "limit": 3},
        )

        self.assertEqual(response.status_code, 200)
        seed_labels = {seed["canonical_label"] for seed in response.json()["seeds"]}
        self.assertIn("Addition", seed_labels)

    def test_accessibility_route(self):
        response = self.client.post(
            "/api/accessibility/latex-gloss",
            json={"latex": r"x \in \mathbb{R}", "audience": "concise"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreater(payload["resolved_count"], 0)
        self.assertIn("tokens", payload)

    def test_paper_analysis_route_returns_contextual_equation_output(self):
        response = self.client.post(
            "/api/paper/analyze",
            json={
                "title": "Attention demo",
                "abstract_or_context": (
                    "Scaled attention computes relevance with a query matrix, key matrix, "
                    "and value matrix before weighting the output."
                ),
                "equations": [r"S=\sum_k a_k X_k", r"x \in \mathbb{R}"],
                "audience": "pedagogical",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["title"], "Attention demo")
        self.assertEqual(len(payload["equations"]), 2)
        first = payload["equations"][0]
        self.assertIn("plain_notation_reading", first)
        self.assertIn("semantic_reading", first)
        self.assertIn("contextual_explanation", first)
        self.assertIn("why_it_helps", first)
        self.assertIn("equation_label", first)
        self.assertIn("context_summary", first)
        self.assertIn("context_evidence", first)
        self.assertIn("term_explanations", first)
        self.assertIn("ontology_links", first)
        self.assertIn("spoken_script", first)
        self.assertIn("extraction_confidence", first)
        self.assertIn("document_id", payload)
        self.assertIn("document_graph", payload)
        self.assertIn("cross_references", payload["document_graph"])
        self.assertGreater(first["resolved_count"], 0)

    def test_paper_analysis_route_extracts_equations_from_pasted_context(self):
        response = self.client.post(
            "/api/paper/analyze",
            json={
                "title": "Extracted equation demo",
                "abstract_or_context": r"The paper states $x \in \mathbb{R}$ before solving the model.",
                "equations": [],
                "audience": "concise",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["extracted_equation_count"], 1)
        self.assertEqual(payload["equations"][0]["latex"], r"x \in \mathbb{R}")

    def test_paper_analysis_route_keeps_pasted_context_when_pdf_fails(self):
        response = self.client.post(
            "/api/paper/analyze",
            json={
                "title": "Fallback demo",
                "abstract_or_context": r"Fallback context still contains $x \in \mathbb{R}$.",
                "pdf_base64": "not-a-real-pdf",
                "pdf_filename": "broken.pdf",
                "audience": "concise",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["pdf"]["status"], "failed")
        self.assertEqual(payload["extracted_equation_count"], 1)

    def test_paper_analysis_route_reports_missing_azure_credentials(self):
        response = self.client.post(
            "/api/paper/analyze",
            json={
                "title": "Azure graceful demo",
                "abstract_or_context": "Equation-only analysis.",
                "equations": [r"x \in \mathbb{R}"],
                "audio_backend": "azure",
                "generate_audio": True,
            },
        )

        self.assertEqual(response.status_code, 200)
        audio = response.json()["equations"][0]["audio"]
        self.assertIn(audio["status"], {"not_configured", "failed", "ok"})
        if audio["status"] != "ok":
            self.assertIn("Azure", audio["detail"])

    def test_paper_analysis_route_accepts_local_kokoro_backend(self):
        response = self.client.post(
            "/api/paper/analyze",
            json={
                "title": "Local neural speech",
                "equations": [r"x=1"],
                "audio_backend": "kokoro",
                "generate_audio": False,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["equations"][0]["audio"]["backend"], "kokoro")

    def test_paper_job_route_reports_progress_and_returns_analysis(self):
        response = self.client.post(
            "/api/paper/jobs",
            json={
                "title": "Background job",
                "abstract_or_context": "Equation (5) gives a distance between two indexed points.",
                "equations": [r"r_{np}=\sqrt{D^2+R_t^2+R_r^2-2R_tR_r\cos(\theta_{np})}\tag{5}"],
            },
        )

        self.assertEqual(response.status_code, 202)
        job_id = response.json()["job_id"]
        payload = {}
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            poll = self.client.get(f"/api/paper/jobs/{job_id}")
            self.assertEqual(poll.status_code, 200)
            payload = poll.json()
            if payload["status"] in {"complete", "failed"}:
                break
            time.sleep(0.02)

        self.assertEqual(payload["status"], "complete")
        self.assertEqual(payload["result"]["equations"][0]["display_label"], "Equation 5")
        self.assertIn(payload["stage"], {"complete", "failed"})

    def test_unknown_paper_job_returns_404(self):
        response = self.client.get("/api/paper/jobs/not-a-real-job")
        self.assertEqual(response.status_code, 404)

    def test_interrupted_cached_job_returns_retryable_failure(self):
        with tempfile.TemporaryDirectory() as cache_dir:
            job_id = "abc123"
            Path(cache_dir, f"{job_id}.json").write_text(
                json.dumps(
                    {
                        "job_id": job_id,
                        "status": "processing",
                        "stage": "extracting_document",
                        "progress": 15,
                    }
                ),
                encoding="utf-8",
            )
            manager = PaperJobManager(lambda **_request: {}, cache_dir=Path(cache_dir))

            recovered = manager.get(job_id)

        self.assertEqual(recovered["status"], "failed")
        self.assertEqual(recovered["stage"], "interrupted")
        self.assertIn("submit it again", recovered["error"])

    def test_non_serializable_analysis_result_becomes_failed_job(self):
        circular_result = {}
        circular_result["document"] = circular_result

        with tempfile.TemporaryDirectory() as cache_dir:
            manager = PaperJobManager(
                lambda **_request: circular_result,
                cache_dir=Path(cache_dir),
            )
            created = manager.create({})
            payload = created
            for _attempt in range(100):
                payload = manager.get(created["job_id"])
                if payload["status"] in {"complete", "failed"}:
                    break
                time.sleep(0.01)

        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["stage"], "failed")
        self.assertIn("JSON", payload["error"])


if __name__ == "__main__":
    unittest.main()
