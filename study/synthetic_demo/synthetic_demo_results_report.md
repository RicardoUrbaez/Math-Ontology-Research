# Synthetic Demo Study Results

**Important:** This report uses synthetic/demo responses only. It is a dry-run analysis for presentation and pipeline testing. It is not real participant evidence.

## Dataset

- Planned/demo participants: 10
- Conditions: notation-only TTS and MathOntoSpeak semantic TTS
- Expressions per condition: 10
- MCQ items per expression: 4
- Synthetic comprehension rows: 800
- Synthetic NASA-TLX rows: 20
- Synthetic interview summaries: 10

## Comprehension Dry-Run

- Notation-only mean accuracy: 73.0% (SD 4.8%)
- MathOntoSpeak semantic mean accuracy: 84.7% (SD 4.2%)
- Mean difference: 11.7% in favor of semantic TTS
- Paired t-test: t = 7.224, p = 0.000
- Wilcoxon signed-rank: W = 0.000, p = 0.004
- Cohen dz: 2.284

## NASA-TLX Dry-Run

- Notation-only mean workload: 50.6 (SD 3.6)
- MathOntoSpeak semantic mean workload: 34.1 (SD 1.8)
- Mean difference: -16.5; negative values favor semantic TTS because lower workload is better
- Paired t-test: t = -14.689, p = 0.000
- Wilcoxon signed-rank: W = 0.000, p = 0.002
- Cohen dz: -4.645

## Synthetic Interview Themes

1. Semantic audio improved symbol-role clarity, especially for limits, vectors, and matrix expressions.
2. Notation-only audio was shorter, but participants in the synthetic set more often described it as requiring guessing.
3. Semantic audio was preferred for unfamiliar material, while some synthetic responses noted pacing should be faster for familiar algebra.

## Code Frequencies

- semantic_clarity: 5
- audio_preference_semantic: 5
- symbol_role_helpful: 3
- notation_concise: 3
- notation_confusion: 3
- cognitive_load_high: 3
- pacing_issue: 2
- domain_familiarity: 2
- calculus_helpful: 2
- matrix_helpful: 2

## Safe Wording

Use: "A synthetic pilot dataset was generated to test the analysis workflow and illustrate expected outputs. Real participant results remain to be collected if required."

Do not use: "Participants showed improvement" unless real participant sessions are completed.

## Files

- `study/synthetic_demo/synthetic_comprehension_scores.csv`
- `study/synthetic_demo/synthetic_nasa_tlx.csv`
- `study/synthetic_demo/synthetic_interview_coding.csv`
- `study/analysis/mathontospeak_synthetic_demo_analysis.xlsx`
- `study/synthetic_demo/synthetic_demo_results_summary.json`
