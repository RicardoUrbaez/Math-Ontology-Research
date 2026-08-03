from __future__ import annotations

import re


_LEGACY_SYMBOLS = {
    "\u00f0": "(",
    "\u00de": ")",
    "\u00bc": "=",
    "\u00fe": "+",
    "\u00bd": "[",
    "\u2013": "-",
    "\u2212": "-",
}


def _extract_source_label(value: str, source_label: str) -> tuple[str, str]:
    label = source_label.strip()
    tag_match = re.search(r"\\tag\*?\s*\{\s*([^{}]+?)\s*\}\s*$", value)
    if tag_match:
        return value[: tag_match.start()].rstrip(), label or tag_match.group(1).strip()

    trailing_match = re.search(
        r"(?:(?:\\qquad|\\quad)\s*|\s+)\(\s*((?:[A-Za-z]+\.)?\d+(?:\.\d+)*)\s*\)\s*$",
        value,
    )
    if trailing_match:
        return value[: trailing_match.start()].rstrip(), label or trailing_match.group(1)
    return value, label


def _restore_named_scripts(value: str) -> str:
    # Font extraction often flattens E sub 0 superscript th into "Eth 0".
    value = re.sub(
        r"\b([A-Z])\s*(th)\s+([A-Za-z0-9])(?=\s*\()",
        lambda match: rf"{match.group(1)}_{match.group(3)}^{{\mathrm{{{match.group(2)}}}}}",
        value,
    )
    value = re.sub(r"\b([A-Za-z])max\b", r"\1_{max}", value)
    value = re.sub(r"\b([A-Za-z])min\b", r"\1_{min}", value)
    value = re.sub(
        r"E(sd|sub|surf|d)(?=\b)",
        lambda match: f"E_{match.group(1)}" if len(match.group(1)) == 1 else f"E_{{{match.group(1)}}}",
        value,
    )
    value = re.sub(r"\b([A-Za-z])([0-9])\b", r"\1_\2", value)
    return value


def _restore_units(value: str) -> str:
    value = re.sub(r"(?<![A-Za-z{])keV\b", r"\\mathrm{keV}", value)
    return re.sub(r"(?<![A-Za-z{])eV\b", r"\\mathrm{eV}", value)


def _restore_parenthesized_fraction(value: str) -> str:
    pattern = re.compile(
        r"(?P<numerator>(?:\d+\s*)?(?:[A-Z](?:_\{[^{}]+\}|_[A-Za-z0-9]+)?\s*)+)"
        r"/\s*\((?P<denominator>[^()]+)\)"
    )

    def replace(match: re.Match[str]) -> str:
        numerator = re.sub(r"\s+", " ", match.group("numerator")).strip()
        denominator = re.sub(r"\s+", " ", match.group("denominator")).strip()
        return rf"\frac{{{numerator}}}{{{denominator}}}"

    return pattern.sub(replace, value)


def normalize_extracted_equation(value: str, source_label: str = "") -> tuple[str, str]:
    """Recover common structure lost by scientific-PDF font extraction.

    This normalizer is deliberately based on recurring font/layout damage rather than
    equation numbers or paper titles. Domain-specific symbol meanings are left to the
    paper-evidence and ontology stages.
    """

    text = re.sub(r"\s+", " ", value or "").strip(" ,;")
    legacy_encoded = any(symbol in text for symbol in _LEGACY_SYMBOLS)
    for damaged, replacement in _LEGACY_SYMBOLS.items():
        text = text.replace(damaged, replacement)
    text = re.sub(r"(?<=\d):(?=\d)", ".", text)

    if legacy_encoded and "=" in text:
        lhs, rhs = text.split("=", 1)
        text = f"{lhs}={rhs.replace('=', '/')}"

    if legacy_encoded:
        attached_label = re.search(
            r"\(\s*((?:[A-Za-z]+\.)?\d+(?:\.\d+)*)\s*\)\s*$",
            text,
        )
        if attached_label:
            source_label = source_label.strip() or attached_label.group(1)
            text = text[: attached_label.start()].rstrip()

    if re.search(r"(?<![A-Za-z])f\s*\[", text):
        legacy_label = re.search(
            r"g(?:_?\s*)\(\s*((?:[A-Za-z]+\.)?\d+(?:\.\d+)*)\s*\)\s*$",
            text,
        )
        if legacy_label:
            source_label = source_label.strip() or legacy_label.group(1)
            text = text[: legacy_label.start()] + "g"

    text, source_label = _extract_source_label(text, source_label)
    text = _restore_named_scripts(text)

    # In several legacy math fonts, printed curly braces decode as f and g.
    legacy_brace_group = bool(re.search(r"(?<![A-Za-z])f\s*\[", text)) and bool(
        re.search(r"g\s*$", text)
    )
    if legacy_brace_group:
        text = re.sub(r"(?<![A-Za-z])f\s*\[", r"\\left\\{\\left[", text, count=1)
        text = re.sub(r"g\s*$", r"\\right\\}", text, count=1)
        if "]" not in text:
            text = re.sub(
                r"(\\left\[[^\]]+\))(?=\s*1\s*/\s*2)",
                r"\1]",
                text,
                count=1,
            )

    text = _restore_units(text)
    text = re.sub(r"(?<=\d)(?=\\mathrm)", " ", text)
    text = re.sub(r"(?<=\d)(?=[A-Z])", " ", text)
    text = re.sub(r"(?<=[A-Z])(?=E_(?:\{|[A-Za-z0-9]))", " ", text)
    text = _restore_parenthesized_fraction(text)

    if legacy_brace_group:
        text = re.sub(
            r"\]\s*(?:\^\s*)?1\s*/\s*2",
            r"\\right]^{1/2}",
            text,
            count=1,
        )

    text = re.sub(r"\s*=\s*", " = ", text)
    text = re.sub(r"\s*\+\s*", " + ", text)
    text = re.sub(r"\s*-\s*", " - ", text)
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"\s+\)", ")", text)
    text = re.sub(r"(\^\{\\mathrm\{[^{}]+\}\})\s+(?=\()", r"\1", text)
    text = re.sub(r"\)(?=\\left\\\{)", r") ", text)
    text = re.sub(r"\s+", " ", text).strip(" ,;")
    return text, source_label


def validate_equation_structure(latex: str) -> dict[str, object]:
    """Return a source-independent quality assessment for extracted notation."""

    value = (latex or "").strip()
    issues: list[str] = []
    details: list[str] = []
    severe_issues: set[str] = set()

    if not value or not re.search(r"[A-Za-z0-9\\]", value):
        issues.append("empty_or_nonmathematical")
        details.append("No recognizable mathematical content was found.")
        severe_issues.add("empty_or_nonmathematical")

    stack: list[tuple[str, int]] = []
    pairs = {")": "(", "]": "[", "}": "{"}
    openings = set(pairs.values())
    for index, character in enumerate(value):
        if character in "{}" and index > 0 and value[index - 1] == "\\":
            continue
        if character in openings:
            stack.append((character, index))
        elif character in pairs:
            if not stack or stack[-1][0] != pairs[character]:
                issues.append("unbalanced_delimiters")
                details.append(f"Unexpected closing delimiter {character} at position {index}.")
                severe_issues.add("unbalanced_delimiters")
                break
            stack.pop()
    if stack and "unbalanced_delimiters" not in issues:
        issues.append("unbalanced_delimiters")
        details.append("One or more mathematical groups are not closed.")
        severe_issues.add("unbalanced_delimiters")

    if re.search(r"\\tag\*?\s*\{|g_?\s*\(\s*\d+(?:\.\d+)*\s*\)\s*$", value):
        issues.append("label_contamination")
        details.append("A printed equation label appears to remain inside the formula.")
        severe_issues.add("label_contamination")

    if any(symbol in value for symbol in _LEGACY_SYMBOLS) or re.search(
        r"(?<![A-Za-z])f\s*\[|g\s*$", value
    ):
        issues.append("legacy_font_artifact")
        details.append("The formula still contains symbols associated with damaged PDF math fonts.")
        severe_issues.add("legacy_font_artifact")

    if re.search(r"block-type|type\s*=\s*equation|<\/?(?:p|span|math)\b", value, re.IGNORECASE):
        issues.append("markup_contamination")
        details.append("Document markup appears inside the extracted formula.")
        severe_issues.add("markup_contamination")

    flattened_root = re.search(
        r"=\s*(?:q|√|sqrt)\s+[A-Za-z\\]+\s+\d+(?:\s*\+\s*[A-Za-z\\]+\s+\d+){1,}",
        value,
        re.IGNORECASE,
    )
    flattened_functions = (
        "\\" not in value
        and bool(re.search(r"\b(?:cos|sin|tan|exp|sqrt|sum|theta|lambda|beta)\b", value, re.IGNORECASE))
        and len(re.findall(r"\b[A-Za-z]+\s+\d+\b", value)) >= 2
    )
    if flattened_root or flattened_functions:
        issues.append("flattened_math_structure")
        details.append(
            "The PDF text layer appears to have flattened roots, powers, functions, or compound symbols."
        )
        severe_issues.add("flattened_math_structure")

    issues = list(dict.fromkeys(issues))
    score = max(0.0, 1.0 - (0.35 * len(severe_issues)) - (0.1 * (len(issues) - len(severe_issues))))
    status = "invalid" if severe_issues else "warning" if issues else "valid"
    confidence = "low" if status == "invalid" else "medium" if status == "warning" else "high"
    return {
        "status": status,
        "confidence": confidence,
        "score": round(score, 2),
        "issues": issues,
        "details": details,
    }
