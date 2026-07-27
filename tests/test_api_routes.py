import unittest

from fastapi.testclient import TestClient

from api.main import app


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


if __name__ == "__main__":
    unittest.main()
