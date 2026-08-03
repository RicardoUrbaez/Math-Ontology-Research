from __future__ import annotations

import contextlib
import json
import os
import re
import sys
from pathlib import Path


LABEL_PATTERN = re.compile(r"^\s*[\[(]\s*((?:[A-Za-z]+\.)?\d+(?:\.\d+)*)\s*[\])]\s*$")


def _clean_latex(value: str) -> str:
    value = value.strip().strip("$")
    value = re.sub(r"\\mathrm\{([A-Za-z])\}", r"\1", value)
    value = re.sub(r"\{([A-Za-z])\s+([A-Za-z])\}", r"{\1\2}", value)
    return value.rstrip(" ,;")


def recognize(path: Path) -> dict:
    os.environ.setdefault("NO_ALBUMENTATIONS_UPDATE", "1")
    with contextlib.redirect_stdout(sys.stderr):
        from PIL import Image
        from pix2tex.cli import LatexOCR
        from rapidocr import RapidOCR

        image = Image.open(path).convert("RGB")
        detections = RapidOCR()(str(path)).to_json()
        label_detections = []
        formula_detections = []
        for detection in detections:
            match = LABEL_PATTERN.fullmatch(str(detection.get("txt") or ""))
            if match:
                label_detections.append((match.group(1), detection))
            else:
                formula_detections.append(detection)

        crop = image
        bbox = [0.0, 0.0, float(image.width), float(image.height)]
        if formula_detections:
            xs = [float(point[0]) for item in formula_detections for point in item.get("box", [])]
            ys = [float(point[1]) for item in formula_detections for point in item.get("box", [])]
            if xs and ys:
                padding = max(12, round(min(image.width, image.height) * 0.05))
                left = max(0, int(min(xs)) - padding)
                top = max(0, int(min(ys)) - padding)
                right = min(image.width, int(max(xs)) + padding)
                bottom = min(image.height, int(max(ys)) + padding)
                bbox = [float(left), float(top), float(right), float(bottom)]
                crop = image.crop((left, top, right, bottom))

        latex = _clean_latex(LatexOCR()(crop))

    source_label = label_detections[-1][0] if label_detections else ""
    label_confidence = (
        float(label_detections[-1][1].get("score") or 0.0) if label_detections else 0.0
    )
    text_confidences = [float(item.get("score") or 0.0) for item in formula_detections]
    text_confidence = sum(text_confidences) / len(text_confidences) if text_confidences else 0.0
    return {
        "latex": latex,
        "source_label": source_label,
        "label_confidence": round(label_confidence, 4),
        "text_confidence": round(text_confidence, 4),
        "ocr_text": " ".join(str(item.get("txt") or "") for item in detections).strip(),
        "bbox": bbox,
        "image_width": image.width,
        "image_height": image.height,
    }


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: image_equation_ocr_worker.py IMAGE_PATH", file=sys.stderr)
        return 2
    try:
        payload = recognize(Path(sys.argv[1]))
    except Exception as exc:  # noqa: BLE001 - worker serializes errors for the API process.
        print(json.dumps({"status": "failed", "error": f"{type(exc).__name__}: {exc}"}))
        return 1
    print("MATHONTOSPEAK_IMAGE_OCR=" + json.dumps(payload, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
