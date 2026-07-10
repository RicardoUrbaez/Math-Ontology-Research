"""Generate clearly labeled synthetic study responses for workbook testing.

This script does not create real participant data. It creates a deterministic
demo dataset so the analysis workbook can be exercised before the actual study.
"""

from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "study" / "synthetic_demo"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


NOTATION_CORRECT_TARGETS = [26, 28, 30, 31, 29, 27, 32, 30, 28, 31]
SEMANTIC_CORRECT_TARGETS = [33, 34, 35, 31, 36, 32, 35, 34, 33, 36]


def wrong_question_indices(participant_index: int, condition: str, total_questions: int) -> set[int]:
    """Pick deterministic wrong-answer positions with participant variability."""
    targets = SEMANTIC_CORRECT_TARGETS if condition == "mathontospeak_semantic" else NOTATION_CORRECT_TARGETS
    correct_target = targets[(participant_index - 1) % len(targets)]
    wrong_needed = total_questions - correct_target
    ranked = sorted(
        range(1, total_questions + 1),
        key=lambda question_index: (
            ((participant_index * 37) + (question_index * 19) + (11 if condition == "mathontospeak_semantic" else 0)) % 101,
            question_index,
        ),
    )
    return set(ranked[:wrong_needed])


def response_for(participant_index: int, question_index: int, wrong_indices: set[int]) -> tuple[str, str, int]:
    """Return response, correctness label, and numeric score."""
    if question_index not in wrong_indices:
        return "A", "Yes", 1

    wrong_choices = ["B", "C", "D"]
    return wrong_choices[(participant_index + question_index) % len(wrong_choices)], "No", 0


def nasa_values(participant_index: int, condition: str) -> dict[str, int]:
    if condition == "mathontospeak_semantic":
        base = 35 + (participant_index % 4) * 3
        return {
            "mental": base + 5,
            "physical": 18 + (participant_index % 3) * 2,
            "temporal": base - 2,
            "performance": 28 + (participant_index % 5) * 2,
            "effort": base + 4,
            "frustration": 24 + (participant_index % 4) * 2,
        }

    base = 48 + (participant_index % 5) * 4
    return {
        "mental": base + 8,
        "physical": 22 + (participant_index % 4) * 3,
        "temporal": base + 3,
        "performance": 42 + (participant_index % 5) * 3,
        "effort": base + 6,
        "frustration": 38 + (participant_index % 4) * 4,
    }


def make_interview_rows(schedule: list[dict[str, str]]) -> list[dict[str, object]]:
    templates = [
        (
            "Participant said the semantic version made it easier to tell what the symbols were doing, especially for vectors and limits.",
            "semantic_clarity",
            "symbol_role_helpful",
            "audio_preference_semantic",
            "positive",
            "mathontospeak_semantic",
        ),
        (
            "Participant found notation-only audio shorter, but said it was harder to remember the purpose of each expression.",
            "notation_concise",
            "notation_confusion",
            "cognitive_load_high",
            "mixed",
            "notation_only",
        ),
        (
            "Participant preferred semantic audio for new material but wanted slightly faster pacing for familiar algebra examples.",
            "audio_preference_semantic",
            "pacing_issue",
            "domain_familiarity",
            "mixed",
            "mathontospeak_semantic",
        ),
        (
            "Participant said both conditions were understandable, but the semantic version reduced guessing on calculus and matrix items.",
            "semantic_clarity",
            "calculus_helpful",
            "matrix_helpful",
            "positive",
            "both",
        ),
    ]

    rows: list[dict[str, object]] = []
    for idx, participant in enumerate(schedule):
        summary, code1, code2, code3, valence, condition = templates[idx % len(templates)]
        rows.append(
            {
                "participant_id": participant["participant_id"],
                "excerpt_summary": summary,
                "code_1": code1,
                "code_2": code2,
                "code_3": code3,
                "valence": valence,
                "condition_mentioned": condition,
                "researcher_notes": "Synthetic demo response; replace with real transcript after participant session.",
            }
        )
    return rows


def main() -> None:
    schedule = read_csv(ROOT / "study" / "protocol" / "counterbalance_schedule.csv")
    questions = read_csv(ROOT / "study" / "instruments" / "mcq_comprehension_test.csv")

    comprehension_rows: list[dict[str, object]] = []
    for p_idx, participant in enumerate(schedule, start=1):
        for condition in [participant["condition_1"], participant["condition_2"]]:
            wrong_indices = wrong_question_indices(p_idx, condition, len(questions))
            for q_idx, question in enumerate(questions, start=1):
                response, correct, score = response_for(p_idx, q_idx, wrong_indices)
                comprehension_rows.append(
                    {
                        "participant_id": participant["participant_id"],
                        "condition": condition,
                        "stimulus_id": question["stimulus_id"],
                        "question_id": question["question_id"],
                        "response": response,
                        "correct_choice": question["correct_choice"],
                        "correct": correct,
                        "score": score,
                        "demo_note": "synthetic_demo_not_real_participant_data",
                    }
                )

    nasa_rows: list[dict[str, object]] = []
    for p_idx, participant in enumerate(schedule, start=1):
        for condition in [participant["condition_1"], participant["condition_2"]]:
            values = nasa_values(p_idx, condition)
            mean = round(sum(values.values()) / len(values), 2)
            nasa_rows.append(
                {
                    "participant_id": participant["participant_id"],
                    "condition": condition,
                    **values,
                    "notes": "Synthetic demo NASA-TLX rating; replace with real participant rating.",
                    "raw_tlx_mean": mean,
                }
            )

    interview_rows = make_interview_rows(schedule)

    write_csv(
        OUT_DIR / "synthetic_comprehension_scores.csv",
        [
            "participant_id",
            "condition",
            "stimulus_id",
            "question_id",
            "response",
            "correct_choice",
            "correct",
            "score",
            "demo_note",
        ],
        comprehension_rows,
    )
    write_csv(
        OUT_DIR / "synthetic_nasa_tlx.csv",
        [
            "participant_id",
            "condition",
            "mental",
            "physical",
            "temporal",
            "performance",
            "effort",
            "frustration",
            "notes",
            "raw_tlx_mean",
        ],
        nasa_rows,
    )
    write_csv(
        OUT_DIR / "synthetic_interview_coding.csv",
        [
            "participant_id",
            "excerpt_summary",
            "code_1",
            "code_2",
            "code_3",
            "valence",
            "condition_mentioned",
            "researcher_notes",
        ],
        interview_rows,
    )
    (OUT_DIR / "README.md").write_text(
        "\n".join(
            [
                "# Synthetic Demo Study Responses",
                "",
                "These files are synthetic demo data for testing the analysis workbook.",
                "",
                "They are not real participant responses and must not be reported as collected human-subjects data.",
                "",
                "Files:",
                "",
                "- `synthetic_comprehension_scores.csv`",
                "- `synthetic_nasa_tlx.csv`",
                "- `synthetic_interview_coding.csv`",
                "",
                "Use the real study workbook for actual participant sessions.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote synthetic demo responses to {OUT_DIR}")


if __name__ == "__main__":
    main()
