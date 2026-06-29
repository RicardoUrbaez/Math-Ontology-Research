import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.week4_tts_rendering import (
    GlossRepository,
    MockTTSBackend,
    SymbolConceptLookup,
    assemble_ssml,
    build_surface_forms,
    load_arxiv_equations,
    parse_latex_tokens,
    resolve_latex_tokens,
    run_latex_audio_pipeline,
    synthesize_bundle,
)


class Week4TTSRenderingTests(unittest.TestCase):
    def test_build_surface_forms_from_minimal_metadata(self):
        record = {
            "concept_IRI": "http://example.org/mathkg/Integral",
            "canonical_label": "Integral",
            "semantic_type": "operator",
            "skos_definition": "An Integral is an operator used to accumulate quantities",
            "source_provenance": "OntoMathPRO",
        }

        bundle = build_surface_forms(record)

        self.assertEqual(bundle.canonical_label, "Integral")
        self.assertIn("Integral:", bundle.concise_form)
        self.assertIn("Think of integral", bundle.pedagogical_form)
        self.assertIn("Integral denotes", bundle.expert_form)
        self.assertIn("operator concept", bundle.document_role_form)

    def test_existing_forms_are_preserved_and_normalized(self):
        record = {
            "canonical_label": "Set",
            "semantic_type": "set",
            "concise_form": "Set: a collection",
            "pedagogical_form": "Think of set as a collection",
            "expert_form": "Set denotes a collection",
            "document_role_form": "Set signals collection semantics",
        }

        bundle = build_surface_forms(record)

        self.assertEqual(bundle.concise_form, "Set: a collection.")
        self.assertEqual(bundle.document_role_form, "Set signals collection semantics.")

    def test_assemble_ssml_is_valid_xml_and_contains_math_pauses(self):
        ssml = assemble_ssml("Integral: An operator. It accumulates quantities.")
        ET.fromstring(ssml)

        self.assertIn('rate="-8%"', ssml)
        self.assertIn('pitch="+1st"', ssml)
        self.assertIn('<break time="320ms"/>', ssml)
        self.assertIn('<break time="420ms"/>', ssml)

    def test_mock_backend_writes_four_artifacts_and_ssml_files(self):
        record = {
            "concept_IRI": "http://example.org/mathkg/Matrix",
            "canonical_label": "Matrix",
            "semantic_type": "matrix",
            "skos_definition": "A Matrix is a rectangular array used in linear algebra.",
        }
        bundle = build_surface_forms(record)

        with TemporaryDirectory() as tmp:
            results = synthesize_bundle(bundle, MockTTSBackend(), Path(tmp))

            self.assertEqual(len(results), 4)
            for result in results:
                self.assertEqual(result.status, "ok")
                self.assertTrue(Path(result.audio_path).exists())
                self.assertTrue(Path(result.ssml_path).exists())

    def test_latex_parser_resolves_symbols_to_concept_iris(self):
        repository = GlossRepository.from_json(Path("gloss/week3_gloss_dictionary.json"))
        lookup = SymbolConceptLookup(repository)

        tokens = resolve_latex_tokens(parse_latex_tokens(r"S=\sum_k a_k X_k"), lookup)
        labels = {token.canonical_label for token in tokens if token.concept_iri}

        self.assertIn("Variable", labels)
        self.assertIn("Equality", labels)
        self.assertIn("Addition", labels)
        self.assertTrue(all(token.concept_iri for token in tokens if token.canonical_label in labels))

    def test_twenty_arxiv_equations_render_end_to_end_with_mock_audio(self):
        equations = load_arxiv_equations(Path("validation/week4_20_arxiv_equation_fixture.csv"))

        with TemporaryDirectory() as tmp:
            results = run_latex_audio_pipeline(
                equations,
                gloss_path=Path("gloss/week3_gloss_dictionary.json"),
                backend=MockTTSBackend(),
                output_dir=Path(tmp),
                limit=20,
            )

            self.assertEqual(len(results), 20)
            for result in results:
                self.assertEqual(result.status, "ok")
                self.assertGreater(result.token_count, 0)
                self.assertGreater(result.resolved_count, 0)
                self.assertTrue(result.concepts)
                self.assertTrue(Path(result.audio_path).exists())
                ET.fromstring(Path(result.ssml_path).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
