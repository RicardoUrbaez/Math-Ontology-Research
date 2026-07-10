from src.mathontospeak.corpus_ner import (
    SymbolFrequency,
    clean_text,
    concept_for_symbol,
    find_symbol_mentions,
)
from src.mathontospeak.gloss_record import GlossRecord


def test_single_letter_symbols_are_limited_to_formula_contexts():
    text = "This is a sentence with a normal article. In $a_n = x + 1$, a is a variable."
    symbols = [
        SymbolFrequency(rank=1, symbol="a", frequency=10),
        SymbolFrequency(rank=2, symbol="x", frequency=8),
    ]

    mentions = find_symbol_mentions(text, symbols)

    assert [mention.symbol for mention in mentions] == ["a", "x"]
    assert all("$a_n = x + 1$" in mention.usage_context for mention in mentions)


def test_latex_command_symbols_match_outside_formula_spans():
    text = r"The notation \mathbb{R} is used for a standard number set."
    mentions = find_symbol_mentions(text, [SymbolFrequency(rank=1, symbol=r"\mathbb", frequency=5)])

    assert len(mentions) == 1
    assert mentions[0].symbol == r"\mathbb"
    assert mentions[0].matched_text == r"\mathbb"


def test_direct_symbol_to_gloss_mapping_uses_existing_records():
    records = [
        GlossRecord(
            concept_iri="http://example.org/mathkg/Matrix",
            local_name="Matrix",
            canonical_label="Matrix",
            canonical_gloss="Matrix gloss",
            domain_tags=["linear-algebra"],
        )
    ]

    concept = concept_for_symbol("M", records)

    assert concept is not None
    assert concept.canonical_label == "Matrix"


def test_uppercase_symbol_maps_to_variable_record():
    records = [
        GlossRecord(
            concept_iri="http://example.org/mathkg/Variable",
            local_name="Variable",
            canonical_label="Variable",
            canonical_gloss="Variable gloss",
            domain_tags=["general-mathematics"],
        )
    ]

    concept = concept_for_symbol("X", records)

    assert concept is not None
    assert concept.canonical_label == "Variable"


def test_clean_text_collapses_whitespace():
    assert clean_text(" one\n\n two\tthree ") == "one two three"
