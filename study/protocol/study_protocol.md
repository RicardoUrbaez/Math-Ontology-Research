# Within-Subjects Study Protocol

## Purpose

Compare notation-only TTS audio with MathOntoSpeak semantic TTS audio for mathematical expression comprehension.

## Design

- Within-subjects design.
- Two conditions:
  - Condition A: notation-only TTS.
  - Condition B: MathOntoSpeak semantic TTS.
- Ten expressions per condition.
- Four MCQ comprehension questions per expression.
- NASA-TLX completed after each condition.
- Five-minute post-study interview after both conditions.
- Counterbalanced condition order: AB or BA.

## Session Flow

1. Assign participant ID and condition order from `protocol/counterbalance_schedule.csv`.
2. Explain that the participant will hear two audio versions of mathematical expressions.
3. Condition 1:
   - Play the 10 audio files in stimulus order.
   - After each expression, administer the 4 MCQ items for that expression.
   - After all 10 expressions, administer NASA-TLX for Condition 1.
4. Short pause.
5. Condition 2:
   - Repeat the same 10 expressions using the other audio condition.
   - Administer the same 4 MCQ items after each expression.
   - Administer NASA-TLX for Condition 2.
6. Conduct the 5-minute post-study interview.
7. Enter comprehension scores, NASA-TLX ratings, and interview codes into the analysis spreadsheet.

## Manual Approval Note

Before collecting real participant data, confirm with the professor whether the activity is a class demonstration, pilot usability test, or human-subjects research requiring consent or IRB review.

