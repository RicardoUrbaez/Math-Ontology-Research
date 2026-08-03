import subprocess
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from api.services import (
    extract_pdf_context,
    extract_pdf_context_with_marker,
    marker_structured_context_chunks,
    marker_executable_path,
    marker_mode_policy,
    marker_ocr_policy,
)
from api.equation_normalization import normalize_extracted_equation, validate_equation_structure


class MarkerPdfExtractionTests(unittest.TestCase):
    def test_normalization_is_document_agnostic_and_preserves_function_arguments(self):
        examples = [
            (
                r"r_{np}=\sqrt{D^2+R_t^2+R_r^2-2R_tR_r\cos(\theta_{np})} \qquad (5)",
                "5",
                r"r_{np} = \sqrt{D^2 + R_t^2 + R_r^2 - 2 R_tR_r\cos(\theta_{np})}",
            ),
            (
                r"\int_0^1 x^2\,dx=\frac{1}{3} \tag{12}",
                "12",
                r"\int_0^1 x^2\,dx = \frac{1}{3}",
            ),
            (r"P(X\leq x)=F_X(x)", "", r"P(X\leq x) = F_X(x)"),
            (r"y=f(3)", "", r"y = f(3)"),
            (r"A\mathbf{x}=\mathbf{b} \quad (7)", "7", r"A\mathbf{x} = \mathbf{b}"),
        ]

        for raw, expected_label, expected_latex in examples:
            with self.subTest(raw=raw):
                latex, label = normalize_extracted_equation(raw)
                validation = validate_equation_structure(latex)
                self.assertEqual(label, expected_label)
                self.assertEqual(latex, expected_latex)
                self.assertEqual(validation["status"], "valid")
                self.assertGreaterEqual(validation["score"], 0.9)

    def test_structure_validation_rejects_label_contamination_and_unbalanced_groups(self):
        validation = validate_equation_structure(r"y=\frac{x+1}{z g_(3)")

        self.assertEqual(validation["status"], "invalid")
        self.assertIn("unbalanced_delimiters", validation["issues"])
        self.assertIn("label_contamination", validation["issues"])

    def test_structure_validation_flags_flattened_pdf_math(self):
        validation = validate_equation_structure(
            "rnp = q D 2 + R 2 t + R 2 r - 2 RtR r cos (theta np)"
        )

        self.assertEqual(validation["status"], "invalid")
        self.assertIn("flattened_math_structure", validation["issues"])

    def test_legacy_pdf_braces_fraction_and_equation_label_are_recovered(self):
        chunks = marker_structured_context_chunks(
            [
                {
                    "id": "/page/2/Equation/12",
                    "block_type": "Equation",
                    "html": (
                        '<p block-type="Equation">'
                        "Eth 0 ð eVÞ¼ð511 keVÞf½1þ4AEsd="
                        "ð561eVÞ1=2–1gð3 Þ</p>"
                    ),
                    "polygon": [[40, 100], [510, 100], [510, 145], [40, 145]],
                }
            ]
        )

        equation = chunks[0]

        self.assertEqual(equation["source_label"], "3")
        self.assertEqual(
            equation["latex"],
            r"E_0^{\mathrm{th}}(\mathrm{eV}) = (511 \mathrm{keV}) "
            r"\left\{\left[1 + \frac{4 A E_{sd}}{561 \mathrm{eV}}\right]^{1/2} - 1\right\}",
        )
        self.assertNotRegex(equation["latex"], r"(?:^|[^A-Za-z])g(?:_|\s|$)")

        normalized_again, label_again = normalize_extracted_equation(
            equation["latex"], equation["source_label"]
        )
        self.assertEqual(normalized_again, equation["latex"])
        self.assertEqual(label_again, "3")

    def test_marker_executable_uses_explicit_environment_path(self):
        expected = Path(r"C:\Tools\marker_single.exe")

        with patch.dict("os.environ", {"MARKER_SINGLE_PATH": str(expected)}):
            self.assertEqual(marker_executable_path(), expected)

    def test_auto_marker_mode_avoids_docker_backed_gpu_path_when_docker_is_missing(self):
        with (
            patch.dict("os.environ", {"MATHONTOSPEAK_MARKER_MODE": "auto"}),
            patch("api.services.shutil.which", side_effect=lambda name: None if name == "docker" else "nvidia-smi"),
        ):
            requested, effective, reason = marker_mode_policy()

        self.assertEqual(requested, "auto")
        self.assertEqual(effective, "fast")
        self.assertIn("Docker-backed GPU inference is unavailable", reason)

    def test_auto_marker_ocr_uses_text_layer_when_no_vlm_runtime_exists(self):
        with (
            patch.dict("os.environ", {"MATHONTOSPEAK_MARKER_MODE": "auto"}),
            patch("api.services.shutil.which", return_value=None),
        ):
            enabled, reason = marker_ocr_policy("auto")

        self.assertFalse(enabled)
        self.assertIn("without OCR", reason)

    def test_marker_markdown_returns_equations_and_structured_context(self):
        def fake_run(command, **_kwargs):
            output_dir = Path(command[command.index("--output_dir") + 1])
            markdown_path = output_dir / "wireless" / "wireless.md"
            markdown_path.parent.mkdir(parents=True, exist_ok=True)
            markdown_path.write_text(
                "# System Model\n\n"
                "The received signal is scaled by the channel and includes additive noise.\n\n"
                "$$y[k] = \\sqrt{h}P x[k] + n_A[k]$$\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="done", stderr="")

        with patch("api.services.subprocess.run", side_effect=fake_run):
            text, chunks, status = extract_pdf_context_with_marker(
                b"%PDF-test",
                pdf_filename="wireless.pdf",
                executable=Path(r"C:\Tools\marker_single.exe"),
            )

        self.assertEqual(status["status"], "ok")
        self.assertEqual(status["extractor"], "marker")
        self.assertIn(r"y[k] = \sqrt{h}P x[k] + n_A[k]", text)
        self.assertTrue(any(chunk["kind"] == "section_heading" for chunk in chunks))
        self.assertTrue(any("additive noise" in chunk["text"] for chunk in chunks))

    def test_marker_chunks_preserve_equation_label_page_and_bounds(self):
        def fake_run(command, **_kwargs):
            output_dir = Path(command[command.index("--output_dir") + 1])
            chunks_path = output_dir / "geometry" / "geometry.json"
            chunks_path.parent.mkdir(parents=True, exist_ok=True)
            chunks_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "/page/3/SectionHeader/0",
                            "block_type": "SectionHeader",
                            "html": "<h2>Geometry model</h2>",
                            "polygon": [[40, 80], [500, 80], [500, 110], [40, 110]],
                        },
                        {
                            "id": "/page/3/Text/1",
                            "block_type": "Text",
                            "html": "<p>Equation (5) gives the distance between the indexed points.</p>",
                            "polygon": [[40, 120], [500, 120], [500, 170], [40, 170]],
                        },
                        {
                            "id": "/page/3/Equation/2",
                            "block_type": "Equation",
                            "html": "<p>$$r_{np}=\\sqrt{D^2+R_t^2+R_r^2-2R_tR_r\\cos(\\theta_{np})}$$ (5)</p>",
                            "polygon": [[80, 180], [520, 180], [520, 240], [80, 240]],
                        },
                    ]
                ),
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="done", stderr="")

        with (
            patch("api.services.subprocess.run", side_effect=fake_run),
            patch.dict("os.environ", {"MATHONTOSPEAK_MARKER_MODE": "auto"}),
        ):
            text, chunks, status = extract_pdf_context_with_marker(
                b"%PDF-structured-test",
                pdf_filename="geometry.pdf",
                executable=Path(r"C:\Tools\marker_single.exe"),
            )

        equation = next(chunk for chunk in chunks if chunk["kind"] == "equation")
        self.assertEqual(status["output_format"], "chunks")
        self.assertEqual(status["requested_mode"], "auto")
        self.assertEqual(status["mode"], "fast")
        self.assertIn("Equation (5)", text)
        self.assertEqual(equation["source_label"], "5")
        self.assertEqual(equation["page"], 4)
        self.assertEqual(equation["bbox"], [80.0, 180.0, 520.0, 240.0])
        self.assertEqual(equation["section_heading"], "Geometry model")

    def test_marker_chunks_accept_top_level_blocks_and_prefer_page_index_from_id(self):
        from api.services import marker_structured_context_chunks

        chunks = marker_structured_context_chunks(
            {
                "blocks": [
                    {
                        "id": "/page/0/Text/1",
                        "block_type": "Text",
                        "page": 377,
                        "html": "<p>The paper abstract.</p>",
                        "polygon": [[10, 10], [100, 10], [100, 40], [10, 40]],
                    }
                ]
            }
        )

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["page"], 1)
        self.assertEqual(chunks[0]["text"], "The paper abstract.")

    def test_marker_reuses_cached_structured_extraction(self):
        calls = 0

        def fake_run(command, **_kwargs):
            nonlocal calls
            calls += 1
            output_dir = Path(command[command.index("--output_dir") + 1])
            chunks_path = output_dir / "paper" / "paper.json"
            chunks_path.parent.mkdir(parents=True, exist_ok=True)
            chunks_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "/page/0/Equation/0",
                            "block_type": "Equation",
                            "html": "<p>$$y=hx+n$$ (1)</p>",
                            "polygon": [[10, 10], [100, 10], [100, 40], [10, 40]],
                        }
                    ]
                ),
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="done", stderr="")

        with tempfile.TemporaryDirectory() as cache_dir:
            with (
                patch("api.services.subprocess.run", side_effect=fake_run),
                patch.object(Path, "is_file", return_value=True),
                patch.dict("os.environ", {"MATHONTOSPEAK_CACHE_DIR": cache_dir}),
            ):
                first = extract_pdf_context_with_marker(b"%PDF-cache-test", executable=Path("marker_single"))
                second = extract_pdf_context_with_marker(b"%PDF-cache-test", executable=Path("marker_single"))

        self.assertEqual(calls, 1)
        self.assertFalse(first[2]["cache_hit"])
        self.assertTrue(second[2]["cache_hit"])
        self.assertEqual(first[1], second[1])

    def test_auto_mode_uses_marker_when_pypdf_has_no_high_confidence_equations(self):
        pypdf_result = (
            "The PDF text says y = h x + n without LaTeX delimiters.",
            [{"source": "pdf", "kind": "paragraph", "text": "The PDF text says y = h x + n."}],
            {"status": "ok", "detail": "pypdf worked", "extractor": "pypdf"},
        )
        marker_result = (
            r"The model states $$y = h x + n$$.",
            [{"source": "marker", "kind": "paragraph", "text": r"The model states $$y = h x + n$$."}],
            {"status": "ok", "detail": "Marker worked", "extractor": "marker"},
        )

        with (
            patch("api.services.extract_pdf_context_from_base64", return_value=pypdf_result),
            patch("api.services.extract_pdf_context_with_marker", return_value=marker_result) as marker,
            patch("api.services.docling_runtime_status", return_value={"runtime_available": False}),
            patch("api.services.marker_executable_path", return_value=Path(r"C:\Tools\marker_single.exe")),
            patch.object(Path, "is_file", return_value=True),
            patch.dict("os.environ", {"MATHONTOSPEAK_PDF_EXTRACTOR": "auto"}),
        ):
            text, chunks, status = extract_pdf_context(
                "JVBERi10ZXN0",
                pdf_filename="paper.pdf",
                manual_equations_present=False,
            )

        marker.assert_called_once()
        self.assertEqual(status["extractor"], "marker")
        self.assertTrue(status["fallback_used"])
        self.assertIn("$$y = h x + n$$", text)
        self.assertEqual(chunks[0]["source"], "marker")

    def test_docling_context_with_marker_equations_has_json_serializable_status(self):
        pypdf_result = (
            "Useful text layer without delimited equations.",
            [{"source": "pdf", "kind": "paragraph", "text": "Useful text layer."}],
            {"status": "ok", "detail": "pypdf worked", "extractor": "pypdf"},
        )
        docling_result = (
            "Structured document context without equation blocks.",
            [{"source": "docling", "kind": "paragraph", "text": "Structured context."}],
            {"status": "ok", "detail": "Docling worked", "extractor": "docling"},
        )
        marker_result = (
            r"The model states $$y = h x + n$$.",
            [{"source": "marker", "kind": "equation", "text": r"y = h x + n", "latex": "y = h x + n"}],
            {"status": "ok", "detail": "Marker worked", "extractor": "marker"},
        )

        with (
            patch("api.services.extract_pdf_context_from_base64", return_value=pypdf_result),
            patch("api.services.docling_runtime_status", return_value={"enabled": True}),
            patch("api.services.extract_pdf_context_with_docling", return_value=docling_result),
            patch("api.services.extract_pdf_context_with_marker", return_value=marker_result),
            patch("api.services.marker_executable_path", return_value=Path(r"C:\Tools\marker_single.exe")),
            patch.object(Path, "is_file", return_value=True),
            patch.dict("os.environ", {"MATHONTOSPEAK_PDF_EXTRACTOR": "auto"}),
        ):
            text, chunks, status = extract_pdf_context(
                "JVBERi10ZXN0",
                pdf_filename="paper.pdf",
                manual_equations_present=False,
            )

        encoded = json.dumps(status)
        self.assertIn('"extractor": "marker"', encoded)
        self.assertEqual(status["context_provider"], "docling")
        self.assertEqual(text.count("Structured context."), 1)
        self.assertIn("y = h x + n", text)
        self.assertNotIn("Structured document context without equation blocks", text)
        self.assertEqual(len(chunks), 2)

    def test_auto_mode_keeps_pypdf_when_manual_equations_have_context(self):
        pypdf_result = (
            "Useful surrounding paper context.",
            [{"source": "pdf", "kind": "paragraph", "text": "Useful surrounding paper context."}],
            {"status": "ok", "detail": "pypdf worked", "extractor": "pypdf"},
        )

        with (
            patch("api.services.extract_pdf_context_from_base64", return_value=pypdf_result),
            patch("api.services.extract_pdf_context_with_marker") as marker,
            patch.dict("os.environ", {"MATHONTOSPEAK_PDF_EXTRACTOR": "auto"}),
        ):
            text, chunks, status = extract_pdf_context(
                "valid-base64",
                pdf_filename="paper.pdf",
                manual_equations_present=True,
            )

        marker.assert_not_called()
        self.assertEqual(status["extractor"], "pypdf")
        self.assertFalse(status["fallback_used"])
        self.assertEqual(text, pypdf_result[0])
        self.assertEqual(chunks, pypdf_result[1])

    def test_marker_failure_falls_back_to_pypdf_without_losing_context(self):
        pypdf_result = (
            "Readable PDF text.",
            [{"source": "pdf", "kind": "paragraph", "text": "Readable PDF text."}],
            {"status": "ok", "detail": "pypdf worked", "extractor": "pypdf"},
        )
        marker_result = (
            "",
            [],
            {"status": "failed", "detail": "Marker timed out", "extractor": "marker"},
        )

        with (
            patch("api.services.extract_pdf_context_from_base64", return_value=pypdf_result),
            patch("api.services.extract_pdf_context_with_marker", return_value=marker_result),
            patch("api.services.marker_executable_path", return_value=Path(r"C:\Tools\marker_single.exe")),
            patch.object(Path, "is_file", return_value=True),
            patch.dict("os.environ", {"MATHONTOSPEAK_PDF_EXTRACTOR": "marker"}),
        ):
            text, chunks, status = extract_pdf_context(
                "valid-base64",
                pdf_filename="paper.pdf",
                manual_equations_present=False,
            )

        self.assertEqual(text, pypdf_result[0])
        self.assertEqual(chunks, pypdf_result[1])
        self.assertEqual(status["status"], "ok")
        self.assertEqual(status["extractor"], "pypdf")
        self.assertEqual(status["marker"]["status"], "failed")


if __name__ == "__main__":
    unittest.main()
