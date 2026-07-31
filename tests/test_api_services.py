import unittest
from unittest.mock import patch

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

    def test_paper_analysis_keeps_unknown_symbols_explainable(self):
        payload = self.service.analyze_paper(
            title="Unknown symbol demo",
            abstract_or_context="A short proof introduces a custom operator for a local argument.",
            equations=[r"\mysteryop(z)=q"],
            audience="expert",
        )

        self.assertEqual(len(payload["equations"]), 1)
        equation = payload["equations"][0]
        self.assertEqual(equation["audio"]["status"], "skipped")
        self.assertIn("blind researcher", equation["why_it_helps"])
        self.assertIn("semantic_reading", equation)
        self.assertIn("Variable", equation["concepts"])
        self.assertTrue(equation["spoken_script"].startswith("Next I am going to read Equation 1"))
        unresolved = [term for term in equation["term_explanations"] if term["source"] == "unresolved"]
        self.assertTrue(unresolved)
        self.assertTrue(all(term["confidence"] == "low" for term in unresolved))

    def test_wireless_signal_context_builds_contextual_spoken_script(self):
        payload = self.service.analyze_paper(
            title="Wireless Information and Power Transfer",
            abstract_or_context=(
                "The received signal is produced after transmission through a wireless channel. "
                "The channel gain h scales the transmitted signal and additive receiver noise is included. "
                "Where x[k] is a unit-power baseband information signal, P is the average transmit power, "
                "h is the channel gain, n_A[k] is antenna noise, and n_cov[k] is conversion noise."
            ),
            equations=[r"\hat{y}[k]=\sqrt{h}P x[k]+\tilde{n}_A[k]+n_{cov}[k]"],
            audience="pedagogical",
        )

        equation = payload["equations"][0]
        summary = equation["context_summary"].lower()
        self.assertEqual(equation["equation_label"], "Equation 1")
        self.assertIn("signal", summary)
        self.assertIn("channel", summary)
        self.assertIn("noise", summary)
        self.assertTrue(equation["context_evidence"])
        self.assertTrue(equation["spoken_script"].startswith("Next I am going to read Equation 1"))
        self.assertIn("Term by term", equation["spoken_script"])
        self.assertTrue(
            any(
                term["symbol"] in {"x", "P", "h", "n_A", "n_cov"} and term["source"] == "paper_context"
                for term in equation["term_explanations"]
            )
        )
        self.assertTrue(any(link["canonical_label"] == "Addition" for link in equation["ontology_links"]))

    def test_plain_pdf_style_equation_text_is_detected_without_latex_delimiters(self):
        payload = self.service.analyze_paper(
            title="Plain PDF extraction",
            abstract_or_context=(
                "The received signal is then given by y[k] = sqrt(h) P x[k] + n_A[k] + n_cov[k], "
                "where x[k] is the information signal and n_A[k] is additive antenna noise."
            ),
            equations=[],
            audience="concise",
        )

        self.assertGreater(payload["extracted_equation_count"], 0)
        equation = payload["equations"][0]
        self.assertIn("=", equation["latex"])
        self.assertEqual(equation["extraction_confidence"], "medium")
        self.assertIn("signal", equation["context_summary"].lower())

    def test_manual_equation_uses_paper_context_when_pdf_equation_recovery_is_empty(self):
        payload = self.service.analyze_paper(
            title="Manual equation fallback",
            abstract_or_context=(
                "This section defines the received signal after channel scaling. "
                "Here x is the information signal and n is additive noise."
            ),
            equations=[r"y=h x+n"],
            audience="concise",
        )

        equation = payload["equations"][0]
        self.assertEqual(payload["extracted_equation_count"], 0)
        self.assertEqual(equation["extraction_confidence"], "user_supplied")
        self.assertTrue(equation["context_evidence"])
        self.assertIn("channel", equation["context_summary"].lower())
        self.assertIn("noise", equation["spoken_script"].lower())

    def test_backend_audio_receives_the_contextual_spoken_script(self):
        skipped_audio = {
            "status": "skipped",
            "backend": "none",
            "detail": "captured by test",
            "audio_path": "",
        }
        with patch.object(
            self.service,
            "_maybe_generate_equation_audio",
            return_value=skipped_audio,
        ) as audio_generator:
            payload = self.service.analyze_paper(
                title="Audio contract",
                abstract_or_context=(
                    "The received signal is scaled by the channel and includes additive noise. "
                    "Here x is the information signal."
                ),
                equations=[r"y=h x+n"],
            )

        equation = payload["equations"][0]
        audio_arguments = audio_generator.call_args.kwargs
        self.assertEqual(audio_arguments["speech_text"], equation["spoken_script"])
        self.assertEqual(audio_arguments["ssml"], equation["ssml"])
        self.assertIn("Next I am going to read Equation 1", audio_arguments["ssml"])


if __name__ == "__main__":
    unittest.main()
