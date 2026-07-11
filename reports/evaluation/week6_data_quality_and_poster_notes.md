# Week 6 Data Quality and Poster Notes

## Internal Consistency Check

- Data source: real rapid-pilot entries exported to `study/rapid_pilot/rapid_pilot_results.xlsx`.
- Comprehension rows: 240 total participant-condition-question rows.
- Condition balance: 120 notation-only rows and 120 MathOntoSpeak semantic rows.
- Participant balance: P01-P10 each has 24 comprehension rows.
- NASA-TLX rows: 20 total, one row per participant-condition pair.
- Interview rows: 10 total, one coded row per participant.
- Duplicate checks: no duplicate participant-condition-question keys were found in the finalized rapid-pilot export.

## Result Story for Poster

- The rapid pilot showed higher comprehension for MathOntoSpeak semantic TTS: 43.3% vs. 35.0% for notation-only TTS.
- The comprehension result is directional but not statistically significant in this small pilot: paired t-test t = 1.627, p = 0.138.
- NASA-TLX workload did not improve in the rapid pilot: 64.2 for semantic TTS vs. 61.7 for notation-only TTS; Wilcoxon W = 19.000, p = 0.734.
- Interview coding still supports the central design story: participants most often mentioned semantic role clarity and notation-only cognitive load.

## Poster Design Notes

- Use the SVG versions for print when possible; use PNG if the poster tool has trouble with SVG.
- Figure 1: five-layer architecture.
- Figure 2: `T` concept graph with four surface forms.
- Figure 3: SPARQL benchmark response times.
- Figure 4: user study comprehension chart with error bars.
- Place the architecture figure early in the poster to explain the system.
- Use the concept graph figure near the contribution statement about multi-perspective rendering.
- Use the SPARQL chart and comprehension chart together in the evaluation/results area.
- Keep the main result sentence balanced: "The rapid pilot suggests semantic TTS can improve comprehension, while workload and pacing need refinement."
