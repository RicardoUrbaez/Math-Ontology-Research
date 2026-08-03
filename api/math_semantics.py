from __future__ import annotations

import html
import json
import os
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from hashlib import sha1
from pathlib import Path
from typing import Any


GREEK_NAMES = {
    "alpha",
    "beta",
    "gamma",
    "delta",
    "epsilon",
    "varepsilon",
    "zeta",
    "eta",
    "theta",
    "vartheta",
    "iota",
    "kappa",
    "lambda",
    "mu",
    "nu",
    "xi",
    "pi",
    "rho",
    "sigma",
    "tau",
    "upsilon",
    "phi",
    "varphi",
    "chi",
    "psi",
    "omega",
}
FUNCTION_NAMES = {
    "cos": "cosine",
    "sin": "sine",
    "tan": "tangent",
    "log": "logarithm",
    "ln": "natural logarithm",
    "exp": "exponential",
}
DECORATOR_NAMES = {"hat": "hat", "tilde": "tilde", "bar": "bar", "vec": "vector"}

_SUBSCRIPT = r"_(?:\{[^{}]+\}|[A-Za-z0-9])"
_ARGUMENT = r"(?:\[[^\]]+\]|\([^()]*\))"
_NAMED_SUPERSCRIPT = r"\^\s*\{\\(?:mathrm|textrm|text|operatorname)\s*\{[^{}]+\}\}"
_TOKEN_PATTERN = re.compile(
    rf"\\(?P<decorator>{'|'.join(DECORATOR_NAMES)})\s*\{{(?P<decorated_base>\\?[A-Za-z]+)\}}"
    rf"(?P<decorated_sub>{_SUBSCRIPT})?(?P<decorated_named_sup>{_NAMED_SUPERSCRIPT})?(?P<decorated_arg>{_ARGUMENT})?"
    rf"|\\(?P<greek>{'|'.join(sorted(GREEK_NAMES, key=len, reverse=True))})"
    rf"(?P<greek_sub>{_SUBSCRIPT})?(?P<greek_named_sup>{_NAMED_SUPERSCRIPT})?(?P<greek_arg>{_ARGUMENT})?"
    rf"|\\(?P<function>{'|'.join(FUNCTION_NAMES)}|sqrt|sum|prod|int)(?![A-Za-z])"
    rf"|\\(?:mathrm|textrm|text|operatorname)\s*\{{(?P<unit>[^{{}}]+)\}}"
    rf"|\\(?P<ignored>[A-Za-z]+)\b"
    rf"|(?P<latin>[A-Za-z])(?P<latin_sub>{_SUBSCRIPT})?(?P<latin_named_sup>{_NAMED_SUPERSCRIPT})?(?P<latin_arg>{_ARGUMENT})?"
    r"|(?P<number>\d+(?:\.\d+)?)"
    r"|(?P<operator>[=+\-*/^])"
)


def split_source_label(latex: str) -> tuple[str, str]:
    """Return equation LaTeX without a printed label and the source label."""

    value = (latex or "").strip()
    tag_match = re.search(r"\\tag\*?\s*\{\s*([^{}]+?)\s*\}\s*$", value)
    if tag_match:
        return value[: tag_match.start()].rstrip(), tag_match.group(1).strip()

    trailing_match = re.search(
        r"(?:\\qquad|\\quad|\s)+\(\s*((?:[A-Za-z]+\.)?\d+(?:\.\d+)*)\s*\)\s*$",
        value,
    )
    if trailing_match:
        return value[: trailing_match.start()].rstrip(), trailing_match.group(1).strip()
    return value, ""


def _subscript_text(raw: str) -> str:
    value = raw.lstrip("_").strip("{} ")
    value = re.sub(r"\\([A-Za-z]+)", r"\1", value)
    if value.lower() in {"max", "min", "avg", "cov", "th", "in", "out"}:
        return value
    if value.isalpha() and len(value) > 1:
        return " ".join(value)
    return " ".join(value)


def _argument_text(raw: str) -> str:
    if not raw:
        return ""
    inner = raw[1:-1].strip()
    inner = re.sub(r"\\(?:mathrm|textrm|text|operatorname)\s*\{([^{}]*)\}", r"\1", inner)
    inner = re.sub(r"\\([A-Za-z]+)", r"\1", inner)
    inner = inner.replace("{", "").replace("}", "").strip()
    if not inner:
        return ""
    if raw.startswith("["):
        return f" at {inner}"
    return f" of {inner}"


def _named_superscript_text(raw: str) -> str:
    match = re.search(r"\\(?:mathrm|textrm|text|operatorname)\s*\{([^{}]+)\}", raw or "")
    return re.sub(r"\s+", " ", match.group(1)).strip() if match else ""


def _symbol_spoken(
    raw: str,
    base: str,
    subscript: str,
    argument: str,
    decorator: str = "",
    named_superscript: str = "",
) -> str:
    base_name = base.lstrip("\\")
    spoken = base_name
    if decorator:
        spoken = f"{spoken} {DECORATOR_NAMES.get(decorator, decorator)}"
    if subscript:
        spoken += f" sub {_subscript_text(subscript)}"
    qualifier = _named_superscript_text(named_superscript)
    if qualifier:
        spoken += f" superscript {qualifier}"
    spoken += _argument_text(argument)
    return re.sub(r"\s+", " ", spoken).strip()


def extract_grouped_expression(latex: str) -> list[dict[str, str]]:
    clean_latex, _label = split_source_label(latex)
    expression: list[dict[str, str]] = []
    for match in _TOKEN_PATTERN.finditer(clean_latex):
        raw = match.group(0)
        if match.group("ignored"):
            continue
        if match.group("decorator"):
            expression.append(
                {
                    "kind": "symbol",
                    "raw": raw,
                    "symbol": raw,
                    "spoken": _symbol_spoken(
                        raw,
                        match.group("decorated_base"),
                        match.group("decorated_sub") or "",
                        match.group("decorated_arg") or "",
                        match.group("decorator"),
                        match.group("decorated_named_sup") or "",
                    ),
                }
            )
        elif match.group("greek"):
            expression.append(
                {
                    "kind": "symbol",
                    "raw": raw,
                    "symbol": raw,
                    "spoken": _symbol_spoken(
                        raw,
                        match.group("greek"),
                        match.group("greek_sub") or "",
                        match.group("greek_arg") or "",
                        named_superscript=match.group("greek_named_sup") or "",
                    ),
                }
            )
        elif match.group("latin"):
            expression.append(
                {
                    "kind": "symbol",
                    "raw": raw,
                    "symbol": raw,
                    "spoken": _symbol_spoken(
                        raw,
                        match.group("latin"),
                        match.group("latin_sub") or "",
                        match.group("latin_arg") or "",
                        named_superscript=match.group("latin_named_sup") or "",
                    ),
                }
            )
        elif match.group("function"):
            name = match.group("function")
            spoken = {
                "sqrt": "square root",
                "sum": "summation",
                "prod": "product",
                "int": "integral",
                **FUNCTION_NAMES,
            }[name]
            expression.append({"kind": "function", "raw": raw, "symbol": raw, "spoken": spoken})
        elif match.group("unit"):
            expression.append({"kind": "unit", "raw": raw, "symbol": raw, "spoken": match.group("unit")})
        elif match.group("number"):
            expression.append({"kind": "number", "raw": raw, "symbol": raw, "spoken": raw})
        elif match.group("operator"):
            spoken = {"=": "equals", "+": "plus", "-": "minus", "*": "times", "/": "divided by", "^": "to the power of"}[raw]
            expression.append({"kind": "operator", "raw": raw, "symbol": raw, "spoken": spoken})
    return expression


def canonical_symbol(raw: str) -> str:
    value = re.sub(r"(?:\[[^\]]*\]|\([^()]*\))$", "", raw.strip())
    decorated = re.match(r"\\(?:hat|tilde|bar|vec)\s*\{(\\?[A-Za-z]+)\}(.*)$", value)
    if decorated:
        value = decorated.group(1) + decorated.group(2)
    value = re.sub(r"_\{([^{}]+)\}", r"_\1", value)
    return value


def _replace_balanced_command(value: str, command: str, prefix: str, suffix: str) -> str:
    marker = f"\\{command}{{"
    while marker in value:
        start = value.rfind(marker)
        content_start = start + len(marker)
        depth = 1
        end = content_start
        while end < len(value) and depth:
            if value[end] == "{":
                depth += 1
            elif value[end] == "}":
                depth -= 1
            end += 1
        if depth:
            break
        inner = value[content_start : end - 1]
        value = value[:start] + f" {prefix} {inner} {suffix} " + value[end:]
    return value


def _replace_fraction_commands(value: str) -> str:
    marker = r"\frac{"
    while marker in value:
        start = value.rfind(marker)
        numerator_start = start + len(marker)
        depth = 1
        numerator_end = numerator_start
        while numerator_end < len(value) and depth:
            if value[numerator_end] == "{":
                depth += 1
            elif value[numerator_end] == "}":
                depth -= 1
            numerator_end += 1
        if depth or numerator_end >= len(value) or value[numerator_end] != "{":
            break
        denominator_start = numerator_end + 1
        depth = 1
        denominator_end = denominator_start
        while denominator_end < len(value) and depth:
            if value[denominator_end] == "{":
                depth += 1
            elif value[denominator_end] == "}":
                depth -= 1
            denominator_end += 1
        if depth:
            break
        numerator = value[numerator_start : numerator_end - 1]
        denominator = value[denominator_start : denominator_end - 1]
        spoken = (
            f" fraction with numerator {numerator} divided by denominator {denominator} end fraction "
        )
        value = value[:start] + spoken + value[denominator_end:]
    return value


def _replace_large_operators(value: str) -> str:
    patterns = {
        "sum": "summation",
        "prod": "product",
    }
    for command, spoken in patterns.items():
        value = re.sub(
            rf"\\{command}\s*_\s*\{{([^{{}}]+)\}}\s*\^\s*\{{([^{{}}]+)\}}",
            lambda match: f" {spoken} from {match.group(1)} to {match.group(2)} of ",
            value,
        )
    return value


def accessible_notation_reading(latex: str) -> str:
    value, _label = split_source_label(latex)
    value = value.replace(r"\left", " ").replace(r"\right", " ")
    value = _replace_fraction_commands(value)
    value = _replace_balanced_command(value, "sqrt", "square root of", "end square root")
    value = _replace_large_operators(value)

    def decorated(match: re.Match[str]) -> str:
        base = match.group(2).lstrip("\\")
        return f" {base} {DECORATOR_NAMES[match.group(1)]} "

    value = re.sub(r"\\(hat|tilde|bar|vec)\s*\{(\\?[A-Za-z]+)\}", decorated, value)
    value = re.sub(
        r"\^\s*\{\\(?:mathrm|textrm|text|operatorname)\s*\{([^{}]+)\}\}",
        lambda match: f" superscript {match.group(1)} ",
        value,
    )
    value = re.sub(r"\^\s*\{?2\}?", " squared ", value)
    value = re.sub(
        r"\^\s*\{([^{}]+)\}",
        lambda match: f" to the power of {match.group(1)} ",
        value,
    )
    value = re.sub(r"\^\s*([A-Za-z0-9]+)", lambda match: f" to the power of {match.group(1)} ", value)
    value = re.sub(
        r"_\s*\{([^{}]+)\}",
        lambda match: f" sub {_subscript_text('_' + match.group(1))} ",
        value,
    )
    value = re.sub(
        r"_\s*([A-Za-z0-9])",
        lambda match: f" sub {_subscript_text('_' + match.group(1))} ",
        value,
    )
    for name, spoken in FUNCTION_NAMES.items():
        value = value.replace(f"\\{name}", f" {spoken} of ")
    for name in sorted(GREEK_NAMES, key=len, reverse=True):
        value = value.replace(f"\\{name}", f" {name} ")
    value = value.replace(r"\in", " is in the set ")
    value = re.sub(r",?\s*\\(?:ldots|cdots)\s*,?", " through ", value)
    value = value.replace(r"\quad", " ").replace(r"\qquad", " ")
    value = value.replace(r"\{", " ").replace(r"\}", " ")
    value = value.replace(r"\sum", " summation of ").replace(r"\prod", " product of ")
    value = value.replace(r"\int", " integral of ")
    value = re.sub(r"\\[A-Za-z]+", " ", value)
    value = value.replace("=", " equals ").replace("+", " plus ").replace("-", " minus ")
    value = value.replace("*", " times ").replace("/", " divided by ")
    value = value.replace("[", " at ").replace("]", " ")
    value = value.replace("(", " open parenthesis ").replace(")", " close parenthesis ")
    value = value.replace("{", " ").replace("}", " ").replace(",", " comma ")
    value = value.replace("'", " prime ").replace("′", " prime ")
    return re.sub(r"\s+", " ", value).strip(" .")


def latex_to_mathml(latex: str) -> tuple[str, str]:
    clean_latex, _label = split_source_label(latex)
    try:
        from latex2mathml.converter import convert

        return convert(clean_latex), "latex2mathml"
    except (ImportError, TypeError, ValueError):
        escaped = html.escape(clean_latex)
        return f'<math xmlns="http://www.w3.org/1998/Math/MathML"><mtext>{escaped}</mtext></math>', "fallback"


def speech_rule_engine_notation_reading(mathml: str) -> tuple[str, dict[str, Any]]:
    def clean_spoken(value: str) -> str:
        value = re.sub(r"\bcap\s+([A-Z])\b", r"\1", value)
        value = re.sub(r"\bsub\s+([A-Z])\s+of\s+([A-Z])\b", r"sub \1 \2", value)
        value = re.sub(r"\bslash\b", "divided by", value)
        value = re.sub(r"\blamda\b", "lambda", value, flags=re.IGNORECASE)
        return re.sub(r"\s+", " ", value).strip()

    node = shutil.which("node")
    frontend_root = Path(__file__).resolve().parents[1] / "demo" / "frontend"
    worker = frontend_root / "scripts" / "speech_rule_engine_worker.cjs"
    package_root = frontend_root / "node_modules" / "speech-rule-engine"
    if not node or not worker.is_file() or not package_root.is_dir():
        return "", {
            "engine": "speech_rule_engine",
            "available": False,
            "detail": "The local Speech Rule Engine runtime is not installed.",
        }
    try:
        ET.register_namespace("", "http://www.w3.org/1998/Math/MathML")
        root = ET.fromstring(mathml)
        for row in root.iter():
            children = list(row)
            if len(children) < 2:
                continue
            if not all(
                child.tag.rsplit("}", 1)[-1] == "mi"
                and child.attrib.get("mathvariant") == "normal"
                and (child.text or "").isalpha()
                for child in children
            ):
                continue
            word = "".join(child.text or "" for child in children)
            for child in children:
                row.remove(child)
            text_node = ET.SubElement(row, "{http://www.w3.org/1998/Math/MathML}mtext")
            text_node.text = " ".join(word) if word.isupper() else word
        mathml = ET.tostring(root, encoding="unicode")
    except ET.ParseError:
        pass
    cache_root = Path(
        os.getenv(
            "MATHONTOSPEAK_CACHE_DIR",
            str(Path.home() / ".cache" / "mathontospeak"),
        )
    )
    cache_path = cache_root / "math_speech" / f"{sha1(mathml.encode('utf-8')).hexdigest()}.json"
    try:
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        spoken = clean_spoken(str(cached["spoken"]))
        if spoken:
            return spoken, {
                "engine": "speech_rule_engine",
                "available": True,
                "detail": "Speech Rule Engine reused a cached ClearSpeak reading.",
                "cache_hit": True,
            }
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        pass
    try:
        result = subprocess.run(
            [node, str(worker)],
            input=mathml,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=frontend_root,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return "", {
            "engine": "speech_rule_engine",
            "available": False,
            "detail": f"Speech Rule Engine failed: {type(exc).__name__}.",
        }
    try:
        payload = json.loads(result.stdout.strip())
        spoken = clean_spoken(str(payload["spoken"]))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        spoken = ""
    if result.returncode != 0 or not spoken:
        return "", {
            "engine": "speech_rule_engine",
            "available": False,
            "detail": (result.stderr or "Speech Rule Engine returned no reading.").strip()[-400:],
        }
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps({"spoken": spoken}), encoding="utf-8")
    except OSError:
        pass
    return spoken, {
        "engine": "speech_rule_engine",
        "available": True,
        "detail": "Speech Rule Engine generated a semantic ClearSpeak notation reading.",
        "cache_hit": False,
    }


def mathcat_notation_reading(mathml: str, fallback: str) -> tuple[str, dict[str, Any]]:
    rules_dir = os.getenv("MATHCAT_RULES_DIR", "").strip()
    try:
        import MathCAT  # type: ignore[import-not-found]

        if rules_dir:
            MathCAT.SetRulesDir(rules_dir)
        MathCAT.SetPreference("Language", "en")
        MathCAT.SetPreference("TTS", "None")
        MathCAT.SetMathML(mathml)
        spoken = str(MathCAT.GetSpokenText()).strip()
        if spoken:
            return spoken, {"engine": "mathcat", "available": True, "detail": "MathCAT generated the notation reading."}
    except (ImportError, AttributeError, RuntimeError, OSError):
        pass
    spoken, sre_status = speech_rule_engine_notation_reading(mathml)
    if spoken:
        return spoken, sre_status
    return fallback, {
        "engine": "grouped_fallback",
        "available": False,
        "detail": "MathCAT and Speech Rule Engine were unavailable; used grouped notation rules.",
    }


def build_speech_segments(spoken_script: str) -> list[dict[str, str]]:
    parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+|(?<=;)\s+", spoken_script or "") if part.strip()]
    segments: list[dict[str, str]] = []
    for index, part in enumerate(parts, start=1):
        lowered = part.lower()
        kind = "context"
        if index == 1:
            kind = "introduction"
        elif lowered.startswith("term by term") or " means " in lowered:
            kind = "terms"
        elif lowered.startswith("now the notation"):
            kind = "notation"
        elif "unresolved" in lowered or "not defined" in lowered:
            kind = "warning"
        segments.append(
            {
                "segment_id": f"speech-{index}-{sha1(part.encode('utf-8')).hexdigest()[:8]}",
                "kind": kind,
                "text": part,
            }
        )
    return segments
