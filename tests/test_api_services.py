import unittest

from api.services import MathKGService


class MathKGServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service = MathKGService()

    def test_semantic_search_returns_ranked_gloss_records(self):
        results = self.service.semantic_search("matrix linear algebra", limit=5)

        self.assertTrue(results)
        self.assertEqual(results[0]["canonical_label"], "Matrix")
        self.assertIn("linear-algebra", results[0]["domain_tags"])

    def test_cross_disciplinary_discovery_bridges_from_seed(self):
        payload = self.service.cross_disciplinary_discovery(seed_concept="Matrix", target_domains=["calculus"], limit=5)

        self.assertEqual(payload["seed"]["canonical_label"], "Matrix")
        self.assertTrue(payload["results"])
        self.assertTrue(any("calculus" in result["domain_tags"] for result in payload["results"]))

    def test_concept_recommender_uses_latex_symbols_as_seeds(self):
        payload = self.service.recommend_concepts(latex=r"S=\sum_k a_k X_k", limit=5)
        seed_labels = {seed["canonical_label"] for seed in payload["seeds"]}

        self.assertIn("Equality", seed_labels)
        self.assertIn("Addition", seed_labels)
        self.assertTrue(payload["results"])

    def test_latex_accessibility_gloss_returns_json_tokens(self):
        payload = self.service.latex_accessibility_gloss(r"x \in \mathbb{R}", audience="pedagogical")
        labels = {token["canonical_label"] for token in payload["tokens"]}

        self.assertGreater(payload["resolved_count"], 0)
        self.assertIn("Variable", labels)
        self.assertIn("Real Number", labels)
        self.assertTrue(any("Think of" in token["surface_form"] for token in payload["tokens"]))


if __name__ == "__main__":
    unittest.main()

