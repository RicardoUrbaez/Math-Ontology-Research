import unittest

from fastapi.testclient import TestClient

from src.mathontospeak.api import app


class MathOntoSpeakAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health_and_concept_lookup(self):
        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["status"], "ok")

        concept = self.client.get("/concepts/matrix")
        self.assertEqual(concept.status_code, 200)
        self.assertEqual(concept.json()["local_name"], "Matrix")

    def test_search_discovery_and_recommender(self):
        search = self.client.get("/semantic-search", params={"q": "matrix linear algebra", "limit": 3})
        self.assertEqual(search.status_code, 200)
        self.assertEqual(search.json()["results"][0]["canonical_label"], "Matrix")

        discovery = self.client.get("/cross-disciplinary-discovery", params={"symbol": "T"})
        self.assertEqual(discovery.status_code, 200)
        meanings = {item["meaning"] for item in discovery.json()["meanings"]}
        self.assertIn("transpose marker", meanings)

        recommendation = self.client.get(
            "/concept-recommender",
            params={"latex": r"S=\sum_k a_k X_k", "context": "series"},
        )
        self.assertEqual(recommendation.status_code, 200)
        labels = {item["concept_label"] for item in recommendation.json()["recommendations"]}
        self.assertIn("Equality", labels)

    def test_latex_to_json_gloss_mock_backend(self):
        response = self.client.post(
            "/accessibility/latex-to-json-gloss",
            json={
                "latex": r"S=\sum_k a_k X_k",
                "context": "series and random variables",
                "surface_form": "pedagogical",
                "backend": "mock",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["backend_status"]["status"], "ok")
        self.assertTrue(payload["ssml"].startswith("<speak"))
        self.assertTrue(payload["output_file_paths"]["json_gloss_path"])


if __name__ == "__main__":
    unittest.main()

