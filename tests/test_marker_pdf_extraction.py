import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from api.services import (
    extract_pdf_context,
    extract_pdf_context_with_marker,
    marker_executable_path,
)


class MarkerPdfExtractionTests(unittest.TestCase):
    def test_marker_executable_uses_explicit_environment_path(self):
        expected = Path(r"C:\Tools\marker_single.exe")

        with patch.dict("os.environ", {"MARKER_SINGLE_PATH": str(expected)}):
            self.assertEqual(marker_executable_path(), expected)

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
