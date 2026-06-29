from __future__ import annotations

import re
from typing import Any


KNOWN_COMMANDS = {
    r"\frac",
    r"\sum",
    r"\int",
    r"\sin",
    r"\cos",
    r"\tan",
    r"\lim",
    r"\det",
    r"\cdot",
}

VARIABLES = set("xyzTPABCX")
TOKEN_PATTERN = re.compile(
    r"\\begin\{(?:p?matrix|bmatrix|vmatrix|smallmatrix|array)\}"
    r"|\\(?:mathbf|vec)\{[A-Za-z]\}"
    r"|Var(?=\s*\()"
    r"|E(?=\s*\[)"
    r"|f(?=\s*\()"
    r"|\\[A-Za-z]+"
    r"|[+\-*/=]"
    r"|[A-Za-z]"
)


def _normalized(raw: str) -> str:
    if raw == r"\cdot":
        return "*"
    if raw.startswith(r"\mathbf{") or raw.startswith(r"\vec{"):
        return raw
    return raw


def _symbol_type(raw: str, latex: str) -> str:
    if raw.startswith(r"\begin"):
        return "matrix_hint"
    if raw.startswith(r"\mathbf") or raw.startswith(r"\vec"):
        return "vector_hint"
    if raw in KNOWN_COMMANDS or raw.startswith("\\"):
        return "latex_command"
    if raw in "+-*/=":
        return "operator"
    if raw in {"E", "Var"}:
        return "statistic_notation"
    if raw == "f":
        return "function_notation"
    if raw in VARIABLES:
        if raw in "ABC" and re.search(r"\\begin\{(?:p?matrix|bmatrix|vmatrix|smallmatrix|array)\}", latex):
            return "matrix_variable"
        return "variable"
    return "identifier"


def _parser_note(latex: str) -> str:
    try:
        from pylatexenc.latexwalker import LatexWalker

        LatexWalker(latex).get_latex_nodes()
        return "parsed with pylatexenc available; regex token extraction used for MVP symbol stream"
    except Exception:
        return "regex fallback parser"


def parse_latex_symbols(latex: str) -> list[dict[str, Any]]:
    """Parse a small, ordered symbol stream from LaTeX."""

    note = _parser_note(latex)
    symbols: list[dict[str, Any]] = []
    for order, match in enumerate(TOKEN_PATTERN.finditer(latex), start=1):
        raw = match.group(0)
        symbol_type = _symbol_type(raw, latex)
        token_note = note
        if symbol_type == "matrix_hint":
            token_note = "matrix environment hint"
        elif symbol_type == "vector_hint":
            token_note = "bold or vector notation hint"
        elif raw == "T":
            token_note = "ambiguous: T may be a variable, transpose marker, or transformation depending on context"
        symbols.append(
            {
                "raw": raw,
                "normalized": _normalized(raw),
                "symbol_type": symbol_type,
                "position": match.start(),
                "order": order,
                "notes": token_note,
            }
        )
    return symbols
