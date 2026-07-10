# Study Data Entry and Coding Status

Date: 2026-07-10

## Current Status

The study data-entry structure has been started, but no real participant data has been collected yet.

The analysis workbook now includes pre-filled rows for the planned study design:

- 10 planned participants from `study/protocol/counterbalance_schedule.csv`.
- 2 conditions per participant:
  - `notation_only`
  - `mathontospeak_semantic`
- 10 expressions per condition.
- 4 MCQ questions per expression.
- 800 pre-filled comprehension-entry rows total.
- 20 pre-filled NASA-TLX rows total.
- 10 pre-filled interview-coding rows total.

## Files To Use

- Main analysis workbook: `study/analysis/mathontospeak_study_analysis_template.xlsx`
- MCQ answer key: `study/instruments/mcq_comprehension_test.csv`
- NASA-TLX form: `study/instruments/nasa_tlx_form.md`
- Interview guide: `study/instruments/post_study_interview_guide.md`
- Study runbook: `study/protocol/manual_study_runbook.md`

## How To Complete This Bullet After Sessions

For each participant:

1. Enter each MCQ response in the `Comprehension Scores` sheet.
2. Mark `Correct` as `Yes` or `No`; the `Score` column calculates automatically.
3. Enter NASA-TLX ratings in the `NASA TLX` sheet after each condition.
4. Paste or summarize interview responses in the `Interview Coding` sheet.
5. Add short qualitative codes, such as:
   - `semantic_clarity`
   - `notation_confusion`
   - `audio_preference_semantic`
   - `audio_preference_notation`
   - `cognitive_load_high`
   - `cognitive_load_low`
   - `symbol_role_helpful`
   - `pacing_issue`

## Important Note

Do not invent scores or interview responses. Real values should only be added after participant sessions are actually run.

