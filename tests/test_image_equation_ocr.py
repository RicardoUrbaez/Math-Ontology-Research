import base64
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from api.image_equation_ocr import OCR_RESULT_PREFIX, extract_equation_image_context, is_equation_image
from api.services import MathKGService


class ImageEquationOcrTests(unittest.TestCase):
    def test_png_jpg_and_jpeg_are_supported_image_inputs(self):
        self.assertTrue(is_equation_image("equation.png"))
        self.assertTrue(is_equation_image("equation.jpg"))
        self.assertTrue(is_equation_image("equation.jpeg"))
        self.assertFalse(is_equation_image("paper.pdf"))

    def test_image_ocr_preserves_latex_label_crop_and_source_image(self):
        worker_payload = {
            "latex": r"r_{np}=\sqrt{D^2+R_t^2+R_r^2-2R_tR_r\cos(\theta_{np})}",
            "source_label": "5",
            "label_confidence": 0.9999,
            "text_confidence": 0.94,
            "ocr_text": "r np equals square root expression (5)",
            "bbox": [40.0, 20.0, 520.0, 120.0],
        }
        completed = subprocess.CompletedProcess(
            ["image-ocr"],
            0,
            stdout=OCR_RESULT_PREFIX + json.dumps(worker_payload),
            stderr="",
        )
        encoded = base64.b64encode(b"fake-png-image").decode("ascii")

        with tempfile.TemporaryDirectory() as cache_dir:
            with (
                patch("api.image_equation_ocr.subprocess.run", return_value=completed),
                patch.dict("os.environ", {"MATHONTOSPEAK_CACHE_DIR": cache_dir}),
            ):
                text, chunks, status = extract_equation_image_context(
                    encoded,
                    filename="equation-5.png",
                    media_type="image/png",
                )

        self.assertEqual(status["status"], "ok")
        self.assertEqual(status["input_type"], "image")
        self.assertEqual(status["extractor"], "latex_ocr")
        self.assertEqual(chunks[0]["source_label"], "5")
        self.assertEqual(chunks[0]["bbox"], [40.0, 20.0, 520.0, 120.0])
        self.assertEqual(chunks[0]["latex"], worker_payload["latex"])
        self.assertTrue(chunks[0]["equation_image"].startswith("data:image/png;base64,"))
        self.assertIn("square root", text)

    def test_image_equation_flows_through_ontology_and_spoken_script(self):
        latex = r"r_{np}=\sqrt{D^2+R_t^2+R_r^2-2R_tR_r\cos(\theta_{np})}"
        chunks = [
            {
                "source": "image_ocr",
                "kind": "equation",
                "text": f"$${latex}$$ (5)",
                "latex": latex,
                "source_label": "5",
                "page": 1,
                "bbox": [0, 0, 700, 150],
                "block_id": "image-equation-5",
                "method": "latex_ocr_image",
                "confidence": "medium",
                "equation_image": "data:image/png;base64,fixture",
            }
        ]
        status = {
            "status": "ok",
            "input_type": "image",
            "extractor": "latex_ocr",
            "document_id": "image-fixture",
        }
        service = MathKGService()

        with patch("api.services.extract_document_context", return_value=(latex, chunks, status)):
            payload = service.analyze_paper(
                title="Equation screenshot",
                document_base64="fixture",
                document_filename="equation-5.png",
                document_media_type="image/png",
            )

        equation = payload["equations"][0]
        ontology_labels = {link["canonical_label"] for link in equation["ontology_links"]}
        self.assertEqual(equation["display_label"], "Equation 5")
        self.assertEqual(equation["extraction_method"], "latex_ocr_image")
        self.assertIn("Taking root", ontology_labels)
        self.assertIn("Cosine", ontology_labels)
        self.assertTrue(equation["spoken_script"].startswith("Next, I am going to explain Equation 5"))
        self.assertEqual(payload["document"]["input_type"], "image")
        self.assertIn("Protege OWL", payload["ontology_runtime"]["source"])


if __name__ == "__main__":
    unittest.main()
