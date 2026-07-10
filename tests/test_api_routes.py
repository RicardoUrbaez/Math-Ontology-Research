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


if __name__ == "__main__":
    unittest.main()

