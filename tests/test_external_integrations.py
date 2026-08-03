import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.external_integrations import (
    docling_runtime_status,
    extract_pdf_context_with_docling,
    extract_pdf_context_with_mineru,
    integration_registry,
)
from api.main import app
from api.services import rank_context_evidence
from api.grobid_integration import grobid_tei_context_chunks


class ExternalIntegrationTests(unittest.TestCase):
    def test_health_identifies_cloned_and_runtime_ready_integrations(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "repos" / "docling" / ".git").mkdir(parents=True)
            python_path = root / ".venvs" / "docling" / "Scripts" / "python.exe"
            python_path.parent.mkdir(parents=True)
            python_path.touch()

            with patch(
                "api.external_integrations.python_module_available",
                return_value=True,
            ):
                registry = integration_registry(external_root=root)

        self.assertTrue(registry["docling"]["cloned"])
        self.assertTrue(registry["docling"]["runtime_available"])
        self.assertTrue(registry["docling"]["enabled"])
        self.assertEqual(registry["docling"]["role"], "document_extraction")

    def test_docling_worker_output_becomes_structured_document_context(self):
        def fake_run(command, **_kwargs):
            output_path = Path(command[-1])
            output_path.write_text(
                json.dumps(
                    {
                        "text": "System Model\nThe received signal includes channel gain and noise.\ny=hx+n (1)",
                        "chunks": [
                            {
                                "source": "docling",
                                "kind": "section_heading",
                                "text": "System Model",
                                "page": 2,
                                "reading_order": 0,
                            },
                            {
                                "source": "docling",
                                "kind": "paragraph",
                                "text": "The received signal includes channel gain and noise.",
                                "page": 2,
                                "reading_order": 1,
                            },
                            {
                                "source": "docling",
                                "kind": "equation",
                                "text": "$$y=hx+n$$ (1)",
                                "latex": "y=hx+n",
                                "source_label": "1",
                                "page": 2,
                                "reading_order": 2,
                            },
                        ],
                        "engine_version": "test",
                    }
                ),
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as cache_dir:
            with (
                patch("api.external_integrations.subprocess.run", side_effect=fake_run),
                patch.dict("os.environ", {"MATHONTOSPEAK_CACHE_DIR": cache_dir}),
            ):
                text, chunks, status = extract_pdf_context_with_docling(
                    b"%PDF-docling-test",
                    pdf_filename="wireless.pdf",
                    python_path=Path(r"C:\Tools\docling\python.exe"),
                    worker_path=Path(r"C:\Project\docling_pdf_worker.py"),
                )

        self.assertEqual(status["status"], "ok")
        self.assertEqual(status["extractor"], "docling")
        self.assertEqual(status["engine_version"], "test")
        self.assertIn("channel gain", text)
        equation = next(chunk for chunk in chunks if chunk["kind"] == "equation")
        self.assertEqual(equation["source_label"], "1")
        self.assertEqual(equation["page"], 2)

    def test_mineru_worker_output_preserves_equation_structure_and_provenance(self):
        def fake_run(command, **_kwargs):
            output_path = Path(command[-1])
            output_path.write_text(
                json.dumps(
                    {
                        "text": "Channel Model\nThe channel coefficient is defined below.\nh_{pn}=\\beta e^{-jkr_{np}}\\frac{\\lambda}{4\\pi r_{np}} (4)",
                        "chunks": [
                            {
                                "source": "mineru",
                                "kind": "section_heading",
                                "text": "Channel Model",
                                "page": 7,
                                "reading_order": 0,
                                "bbox": [40, 50, 700, 90],
                            },
                            {
                                "source": "mineru",
                                "kind": "paragraph",
                                "text": "The channel coefficient is defined below.",
                                "page": 7,
                                "reading_order": 1,
                                "bbox": [40, 100, 700, 150],
                            },
                            {
                                "source": "mineru",
                                "kind": "equation",
                                "text": "$$h_{pn}=\\beta e^{-jkr_{np}}\\frac{\\lambda}{4\\pi r_{np}}$$ (4)",
                                "latex": "h_{pn}=\\beta e^{-jkr_{np}}\\frac{\\lambda}{4\\pi r_{np}}",
                                "source_label": "4",
                                "page": 7,
                                "reading_order": 2,
                                "bbox": [120, 170, 620, 250],
                            },
                        ],
                        "engine_version": "test",
                        "backend": "pipeline",
                    }
                ),
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as cache_dir:
            with (
                patch("api.external_integrations.subprocess.run", side_effect=fake_run),
                patch.dict("os.environ", {"MATHONTOSPEAK_CACHE_DIR": cache_dir}),
            ):
                text, chunks, status = extract_pdf_context_with_mineru(
                    b"%PDF-mineru-test",
                    pdf_filename="wireless.pdf",
                    python_path=Path(r"C:\Tools\mineru\python.exe"),
                    worker_path=Path(r"C:\Project\mineru_pdf_worker.py"),
                )

        self.assertEqual(status["status"], "ok")
        self.assertEqual(status["extractor"], "mineru")
        self.assertEqual(status["backend"], "pipeline")
        self.assertIn("channel coefficient", text)
        equation = next(chunk for chunk in chunks if chunk["kind"] == "equation")
        self.assertEqual(equation["source_label"], "4")
        self.assertEqual(equation["page"], 7)
        self.assertEqual(equation["bbox"], [120, 170, 620, 250])

    def test_health_exposes_external_integration_evidence(self):
        client = TestClient(app)
        response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        integrations = response.json()["integrations"]
        self.assertIn("docling", integrations)
        self.assertIn("sentence_transformers", integrations)
        self.assertIn("grobid", integrations)
        self.assertIn("ragas", integrations)
        self.assertIn("mineru", integrations)
        self.assertIn("cloned", integrations["docling"])
        self.assertIn("runtime_available", integrations["docling"])


class DoclingExtractionStrategyTests(unittest.TestCase):
    def test_explicit_docling_strategy_records_the_selected_extractor(self):
        from api.services import extract_pdf_context

        pypdf_result = (
            "Readable fallback text.",
            [{"source": "pdf", "kind": "paragraph", "text": "Readable fallback text."}],
            {"status": "ok", "extractor": "pypdf"},
        )
        docling_result = (
            "Grounded text with $$y=hx+n$$ (1).",
            [{"source": "docling", "kind": "equation", "text": "$$y=hx+n$$ (1)"}],
            {"status": "ok", "extractor": "docling", "engine_version": "test"},
        )

        with (
            patch("api.services.extract_pdf_context_from_base64", return_value=pypdf_result),
            patch("api.services.docling_runtime_status", return_value={"runtime_available": True}),
            patch("api.services.extract_pdf_context_with_docling", return_value=docling_result) as docling,
            patch.dict("os.environ", {"MATHONTOSPEAK_PDF_EXTRACTOR": "docling"}),
        ):
            text, chunks, status = extract_pdf_context(
                "JVBERi10ZXN0",
                pdf_filename="paper.pdf",
                manual_equations_present=False,
            )

        docling.assert_called_once()
        self.assertEqual(status["extractor"], "docling")
        self.assertEqual(status["selected_integration"], "docling")
        self.assertIn("$$y=hx+n$$", text)
        self.assertEqual(chunks[0]["source"], "docling")

    def test_auto_strategy_uses_mineru_when_docling_context_has_no_equation(self):
        from api.services import extract_pdf_context

        pypdf_result = (
            "Short text layer without a recoverable formula.",
            [{"source": "pdf", "kind": "paragraph", "text": "Short text layer without a recoverable formula."}],
            {"status": "ok", "extractor": "pypdf"},
        )
        docling_result = (
            "Channel Model\nThe propagation coefficient is defined for each transmitter and receiver element.",
            [
                {"source": "docling", "kind": "section_heading", "text": "Channel Model", "page": 7},
                {
                    "source": "docling",
                    "kind": "paragraph",
                    "text": "The propagation coefficient is defined for each transmitter and receiver element.",
                    "page": 7,
                },
            ],
            {"status": "ok", "extractor": "docling", "engine_version": "test"},
        )
        mineru_result = (
            "Channel Model\n$$h_{pn}=\\beta e^{-jkr_{np}}\\frac{\\lambda}{4\\pi r_{np}}$$ (4)",
            [
                {
                    "source": "mineru",
                    "kind": "equation",
                    "text": "$$h_{pn}=\\beta e^{-jkr_{np}}\\frac{\\lambda}{4\\pi r_{np}}$$ (4)",
                    "latex": "h_{pn}=\\beta e^{-jkr_{np}}\\frac{\\lambda}{4\\pi r_{np}}",
                    "source_label": "4",
                    "page": 7,
                }
            ],
            {"status": "ok", "extractor": "mineru", "backend": "pipeline"},
        )

        with (
            patch("api.services.extract_pdf_context_from_base64", return_value=pypdf_result),
            patch("api.services.docling_runtime_status", return_value={"enabled": True}),
            patch("api.services.extract_pdf_context_with_docling", return_value=docling_result),
            patch("api.services.mineru_runtime_status", return_value={"enabled": True}),
            patch("api.services.extract_pdf_context_with_mineru", return_value=mineru_result) as mineru,
            patch.dict("os.environ", {"MATHONTOSPEAK_PDF_EXTRACTOR": "auto"}),
        ):
            text, chunks, status = extract_pdf_context(
                "JVBERi10ZXN0",
                pdf_filename="paper.pdf",
                manual_equations_present=False,
            )

        mineru.assert_called_once()
        self.assertEqual(status["extractor"], "mineru")
        self.assertEqual(status["selected_integration"], "mineru")
        self.assertEqual(status["context_provider"], "docling")
        self.assertIn("propagation coefficient", text)
        self.assertTrue(any(chunk["source"] == "docling" for chunk in chunks))
        equation = next(chunk for chunk in chunks if chunk["kind"] == "equation")
        self.assertEqual(equation["source_label"], "4")

    def test_auto_strategy_uses_mineru_when_docling_finds_formula_without_context(self):
        from api.services import extract_pdf_context

        pypdf_result = ("", [], {"status": "empty", "extractor": "pypdf"})
        docling_result = (
            "$$y=hx+n$$ (1)",
            [
                {
                    "source": "docling",
                    "kind": "equation",
                    "text": "$$y=hx+n$$ (1)",
                    "latex": "y=hx+n",
                    "source_label": "1",
                    "page": 2,
                }
            ],
            {"status": "ok", "extractor": "docling", "detail": "One block extracted."},
        )
        mineru_result = (
            "The received waveform is scaled by channel gain and includes additive noise.\n$$y=hx+n$$ (1)",
            [
                {
                    "source": "mineru",
                    "kind": "paragraph",
                    "text": "The received waveform is scaled by channel gain and includes additive noise.",
                    "page": 2,
                },
                {
                    "source": "mineru",
                    "kind": "equation",
                    "text": "$$y=hx+n$$ (1)",
                    "latex": "y=hx+n",
                    "source_label": "1",
                    "page": 2,
                },
            ],
            {"status": "ok", "extractor": "mineru", "backend": "pipeline"},
        )

        with (
            patch("api.services.extract_pdf_context_from_base64", return_value=pypdf_result),
            patch("api.services.docling_runtime_status", return_value={"enabled": True}),
            patch("api.services.extract_pdf_context_with_docling", return_value=docling_result),
            patch("api.services.mineru_runtime_status", return_value={"enabled": True}),
            patch("api.services.extract_pdf_context_with_mineru", return_value=mineru_result) as mineru,
            patch.dict("os.environ", {"MATHONTOSPEAK_PDF_EXTRACTOR": "auto"}),
        ):
            text, _chunks, status = extract_pdf_context(
                "JVBERi10ZXN0",
                pdf_filename="paper.pdf",
                manual_equations_present=False,
            )

        mineru.assert_called_once()
        self.assertEqual(status["selected_integration"], "mineru")
        self.assertEqual(status["fallback_reason"], "low_document_quality")
        self.assertIn("received waveform", text)


class SemanticRetrievalIntegrationTests(unittest.TestCase):
    def test_semantic_reranker_marks_the_evidence_it_reranks(self):
        chunks = [
            {
                "source": "docling",
                "kind": "paragraph",
                "text": "A generic description of the experimental setup.",
                "page": 2,
                "reading_order": 1,
                "block_id": "generic",
            },
            {
                "source": "docling",
                "kind": "paragraph",
                "text": "The received waveform is scaled by channel gain and corrupted by additive noise.",
                "page": 2,
                "reading_order": 2,
                "block_id": "signal-definition",
            },
        ]

        with (
            patch("api.services.semantic_retrieval_status", return_value={"enabled": True}),
            patch(
                "api.services.semantic_similarity_scores",
                side_effect=lambda _query, texts: (
                    [0.98 if "received waveform" in text.lower() else 0.05 for text in texts],
                    {"status": "ok"},
                ),
            ),
        ):
            evidence = rank_context_evidence(
                chunks,
                latex="y=hx+n",
                labels=["Variable", "Addition"],
                equation_metadata={"page": 2, "reading_order": 3},
                limit=2,
            )

        self.assertEqual(evidence[0]["block_id"], "signal-definition")
        self.assertEqual(evidence[0]["ranking_engine"], "sentence_transformers")
        self.assertGreater(evidence[0]["semantic_score"], 0.9)


class GroundingEvaluationIntegrationTests(unittest.TestCase):
    def test_analysis_reports_the_evaluation_engine_used(self):
        from api.services import MathKGService

        with patch(
            "api.services.evaluate_grounding",
            return_value={
                "status": "ok",
                "engine": "ragas",
                "metric": "non_llm_string_similarity",
                "score": 0.81,
                "claim": "evidence_alignment_only",
            },
        ):
            payload = MathKGService().analyze_paper(
                title="Evaluation evidence",
                abstract_or_context="The received signal is scaled by channel gain and includes additive noise.",
                equations=["y=hx+n"],
            )

        evaluation = payload["equations"][0]["grounding_evaluation"]
        self.assertEqual(evaluation["engine"], "ragas")
        self.assertEqual(payload["pipeline"]["evaluation"]["engine"], "ragas")
        self.assertEqual(evaluation["claim"], "evidence_alignment_only")


class GrobidIntegrationTests(unittest.TestCase):
    def test_tei_structure_preserves_section_equation_label_page_and_bounds(self):
        chunks = grobid_tei_context_chunks(
            """
            <TEI xmlns="http://www.tei-c.org/ns/1.0">
              <text><body><div>
                <head>Geometry model</head>
                <p>Equation (5) gives the distance between the indexed points.</p>
                <formula coords="3,80,180,440,60">
                  r_np = sqrt(D^2 + R_t^2 + R_r^2 - 2 R_t R_r cos(theta_np))
                  <label>(5)</label>
                </formula>
              </div></body></text>
            </TEI>
            """
        )

        equation = next(chunk for chunk in chunks if chunk["kind"] == "equation")
        self.assertEqual(equation["source_label"], "5")
        self.assertEqual(equation["page"], 3)
        self.assertEqual(equation["bbox"], [80.0, 180.0, 520.0, 240.0])
        self.assertEqual(equation["section_heading"], "Geometry model")


if __name__ == "__main__":
    unittest.main()
