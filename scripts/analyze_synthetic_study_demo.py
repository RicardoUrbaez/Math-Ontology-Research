"""Analyze the clearly labeled synthetic MathOntoSpeak study demo data.

The output is a dry-run report only. It must not be represented as real
participant evidence.
"""

from __future__ import annotations

import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from scipy import stats


ROOT = Path(__file__).resolve().parents[1]
DEMO_DIR = ROOT / "study" / "synthetic_demo"
REPORT_PATH = DEMO_DIR / "synthetic_demo_results_report.md"
JSON_PATH = DEMO_DIR / "synthetic_demo_results_summary.json"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def mean(values: list[float]) -> float:
    return sum(values) / len(values)


def sample_sd(values: list[float]) -> float:
    m = mean(values)
    return math.sqrt(sum((value - m) ** 2 for value in values) / (len(values) - 1))


def paired_by_condition(rows: list[dict[str, str]], value_field: str) -> dict[str, dict[str, float]]:
    grouped: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        grouped[row["participant_id"]][row["condition"]].append(float(row[value_field]))
    return {
        participant_id: {condition: mean(values) for condition, values in conditions.items()}
        for participant_id, conditions in grouped.items()
    }


def paired_stats(paired: dict[str, dict[str, float]]) -> dict[str, float]:
    participants = sorted(paired)
    notation = [paired[p]["notation_only"] for p in participants]
    semantic = [paired[p]["mathontospeak_semantic"] for p in participants]
    diffs = [semantic_value - notation_value for semantic_value, notation_value in zip(semantic, notation)]
    t_stat, t_p = stats.ttest_rel(semantic, notation)
    try:
        w_stat, w_p = stats.wilcoxon(semantic, notation, zero_method="wilcox")
    except ValueError:
        w_stat, w_p = float("nan"), float("nan")
    return {
        "n": len(participants),
        "notation_mean": mean(notation),
        "notation_sd": sample_sd(notation),
        "semantic_mean": mean(semantic),
        "semantic_sd": sample_sd(semantic),
        "mean_difference_semantic_minus_notation": mean(diffs),
        "paired_t_statistic": float(t_stat),
        "paired_t_p_value": float(t_p),
        "wilcoxon_statistic": float(w_stat),
        "wilcoxon_p_value": float(w_p),
        "cohens_dz": mean(diffs) / sample_sd(diffs),
    }


def code_counts(rows: list[dict[str, str]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for row in rows:
        for field in ["code_1", "code_2", "code_3"]:
            if row[field]:
                counts[row[field]] += 1
    return counts


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def fmt(value: float) -> str:
    if math.isnan(value):
        return "n/a"
    return f"{value:.3f}"


def main() -> None:
    comprehension = read_csv(DEMO_DIR / "synthetic_comprehension_scores.csv")
    nasa = read_csv(DEMO_DIR / "synthetic_nasa_tlx.csv")
    interviews = read_csv(DEMO_DIR / "synthetic_interview_coding.csv")

    comprehension_stats = paired_stats(paired_by_condition(comprehension, "score"))
    nasa_stats = paired_stats(paired_by_condition(nasa, "raw_tlx_mean"))
    codes = code_counts(interviews)
    valence = Counter(row["valence"] for row in interviews)
    condition_mentions = Counter(row["condition_mentioned"] for row in interviews)

    summary = {
        "data_status": "synthetic_demo_not_real_participant_data",
        "comprehension": comprehension_stats,
        "nasa_tlx": nasa_stats,
        "interview_code_counts": dict(codes),
        "interview_valence_counts": dict(valence),
        "interview_condition_mentions": dict(condition_mentions),
    }
    JSON_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    top_codes = codes.most_common()
    lines = [
        "# Synthetic Demo Study Results",
        "",
        "**Important:** This report uses synthetic/demo responses only. It is a dry-run analysis for presentation and pipeline testing. It is not real participant evidence.",
        "",
        "## Dataset",
        "",
        "- Planned/demo participants: 10",
        "- Conditions: notation-only TTS and MathOntoSpeak semantic TTS",
        "- Expressions per condition: 10",
        "- MCQ items per expression: 4",
        "- Synthetic comprehension rows: 800",
        "- Synthetic NASA-TLX rows: 20",
        "- Synthetic interview summaries: 10",
        "",
        "## Comprehension Dry-Run",
        "",
        f"- Notation-only mean accuracy: {pct(comprehension_stats['notation_mean'])} (SD {pct(comprehension_stats['notation_sd'])})",
        f"- MathOntoSpeak semantic mean accuracy: {pct(comprehension_stats['semantic_mean'])} (SD {pct(comprehension_stats['semantic_sd'])})",
        f"- Mean difference: {pct(comprehension_stats['mean_difference_semantic_minus_notation'])} in favor of semantic TTS",
        f"- Paired t-test: t = {fmt(comprehension_stats['paired_t_statistic'])}, p = {fmt(comprehension_stats['paired_t_p_value'])}",
        f"- Wilcoxon signed-rank: W = {fmt(comprehension_stats['wilcoxon_statistic'])}, p = {fmt(comprehension_stats['wilcoxon_p_value'])}",
        f"- Cohen dz: {fmt(comprehension_stats['cohens_dz'])}",
        "",
        "## NASA-TLX Dry-Run",
        "",
        f"- Notation-only mean workload: {nasa_stats['notation_mean']:.1f} (SD {nasa_stats['notation_sd']:.1f})",
        f"- MathOntoSpeak semantic mean workload: {nasa_stats['semantic_mean']:.1f} (SD {nasa_stats['semantic_sd']:.1f})",
        f"- Mean difference: {nasa_stats['mean_difference_semantic_minus_notation']:.1f}; negative values favor semantic TTS because lower workload is better",
        f"- Paired t-test: t = {fmt(nasa_stats['paired_t_statistic'])}, p = {fmt(nasa_stats['paired_t_p_value'])}",
        f"- Wilcoxon signed-rank: W = {fmt(nasa_stats['wilcoxon_statistic'])}, p = {fmt(nasa_stats['wilcoxon_p_value'])}",
        f"- Cohen dz: {fmt(nasa_stats['cohens_dz'])}",
        "",
        "## Synthetic Interview Themes",
        "",
        "1. Semantic audio improved symbol-role clarity, especially for limits, vectors, and matrix expressions.",
        "2. Notation-only audio was shorter, but participants in the synthetic set more often described it as requiring guessing.",
        "3. Semantic audio was preferred for unfamiliar material, while some synthetic responses noted pacing should be faster for familiar algebra.",
        "",
        "## Code Frequencies",
        "",
    ]
    for code, count in top_codes:
        lines.append(f"- {code}: {count}")
    lines += [
        "",
        "## Safe Wording",
        "",
        "Use: \"A synthetic pilot dataset was generated to test the analysis workflow and illustrate expected outputs. Real participant results remain to be collected if required.\"",
        "",
        "Do not use: \"Participants showed improvement\" unless real participant sessions are completed.",
        "",
        "## Files",
        "",
        "- `study/synthetic_demo/synthetic_comprehension_scores.csv`",
        "- `study/synthetic_demo/synthetic_nasa_tlx.csv`",
        "- `study/synthetic_demo/synthetic_interview_coding.csv`",
        "- `study/analysis/mathontospeak_synthetic_demo_analysis.xlsx`",
        "- `study/synthetic_demo/synthetic_demo_results_summary.json`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(REPORT_PATH)
    print(JSON_PATH)


if __name__ == "__main__":
    main()
