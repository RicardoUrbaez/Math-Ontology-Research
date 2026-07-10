# Manual Study Runbook

Use this checklist for the two study bullet points:

1. prepare the study stimuli and audio conditions;
2. administer the within-subjects study and enter the results.

## What Is Already Prepared

- 10 study expressions are ready in `study/stimuli/study_stimuli.csv`.
- The expression split is complete:
  - Algebra: 4 expressions.
  - Calculus: 3 expressions.
  - Linear algebra: 3 expressions.
- The notation-only audio condition is ready in `study/audio/notation_only/mp3/`.
- The MathOntoSpeak semantic audio condition is ready in `study/audio/mathontospeak_semantic/equation_gtts/`.
- The 40-item MCQ test is ready in `study/instruments/mcq_comprehension_test.csv`.
- The NASA-TLX form is ready in `study/instruments/nasa_tlx_form.md`.
- The interview guide is ready in `study/instruments/post_study_interview_guide.md`.
- The counterbalance schedule is ready in `study/protocol/counterbalance_schedule.csv`.
- The analysis workbook is ready at `study/analysis/mathontospeak_study_analysis_template.xlsx`.

## Manual Step 1: Professor Review

Before running anyone through the study, show the professor these files:

- `study/stimuli/study_stimuli.csv`
- `study/instruments/mcq_comprehension_test.csv`
- `study/instruments/nasa_tlx_form.md`
- `study/instruments/post_study_interview_guide.md`
- `study/protocol/study_protocol.md`

Ask the professor to confirm:

- whether the expressions are acceptable;
- whether the MCQ questions are fair;
- whether this is only a class demo/pilot or needs consent/IRB handling;
- whether the same participant may answer the same MCQs after both audio conditions.

Do not collect real participant data until this is settled.

## Manual Step 2: Open The Study Workbook

Open:

`study/analysis/mathontospeak_study_analysis_template.xlsx`

Use it during or after each session to enter:

- participant ID;
- assigned order, AB or BA;
- condition label;
- MCQ answers/scores;
- NASA-TLX ratings;
- interview notes and codes.

## Manual Step 3: Assign Participant Order

Open:

`study/protocol/counterbalance_schedule.csv`

Use the next available participant row:

- AB means Condition A first, then Condition B.
- BA means Condition B first, then Condition A.

Condition labels:

- Condition A: notation-only TTS.
- Condition B: MathOntoSpeak semantic TTS.

## Manual Step 4: Run Condition A Or B First

If the participant is assigned Condition A first, play files from:

`study/audio/notation_only/mp3/`

If the participant is assigned Condition B first, play files from:

`study/audio/mathontospeak_semantic/equation_gtts/`

Play the 10 files in stimulus order:

1. ALG01
2. ALG02
3. ALG03
4. ALG04
5. CALC01
6. CALC02
7. CALC03
8. LIN01
9. LIN02
10. LIN03

After each expression, ask the 4 matching MCQ questions from:

`study/instruments/mcq_comprehension_test.csv`

Record the answers in the workbook.

## Manual Step 5: NASA-TLX After First Condition

After the first 10-expression condition is finished, administer:

`study/instruments/nasa_tlx_form.md`

Enter the six NASA-TLX ratings into the workbook under the matching participant and condition.

## Manual Step 6: Run The Second Condition

Play the other audio condition.

Use the same stimulus order:

1. ALG01
2. ALG02
3. ALG03
4. ALG04
5. CALC01
6. CALC02
7. CALC03
8. LIN01
9. LIN02
10. LIN03

Again, ask the 4 matching MCQ questions after each expression.

Record those answers in the workbook under the second condition.

## Manual Step 7: NASA-TLX After Second Condition

After the second condition is finished, administer NASA-TLX again.

Enter the six ratings into the workbook under the participant's second condition.

## Manual Step 8: Five-Minute Interview

Use:

`study/instruments/post_study_interview_guide.md`

Ask the short interview questions after both conditions are done.

Record notes in the workbook's interview coding sheet or in a separate transcript file.

## Manual Step 9: Transcribe And Code

After sessions are complete:

1. Transcribe each interview response.
2. Add short codes/themes in the workbook.
3. Mark whether comments favor notation-only audio, semantic audio, both, or neither.
4. Add any clear usability issues or confusing expressions.

## Manual Step 10: Check Data Entry

Before analysis, confirm:

- each participant has both conditions entered;
- each condition has 10 expression rows;
- each expression has 4 MCQ responses;
- each condition has one NASA-TLX row;
- each participant has interview notes/codes.

The workbook summary formulas update after data is entered.

## What You Do Not Need To Run Manually

You do not need to regenerate the audio unless the professor changes the stimuli.

You do not need Fuseki or FastAPI to run the participant study. Those are only needed for a live technical demo of the API/SPARQL system.

## If The Professor Changes Stimuli

If the professor edits the expressions or questions, regenerate the affected audio and update the workbook before running participants.

