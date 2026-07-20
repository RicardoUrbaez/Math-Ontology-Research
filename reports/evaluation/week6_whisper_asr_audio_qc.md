# Week 6 Whisper ASR Audio QC

This report evaluates whether generated MathOntoSpeak study audio can be transcribed back into text by a Whisper-style ASR model.

## Configuration

- Whisper model: `tiny.en`
- Reviewed audio files: 20
- Successful ASR rows: 20
- Transcripts produced: 20/20
- Mean word error rate: 0.220
- Mean semantic concept keyword recall: 0.883
- CSV output: `reports\evaluation\week6_whisper_asr_audio_qc.csv`

## Interpretation

Whisper is used here as an ASR intelligibility check, not as the MathOntoSpeak TTS engine. The project first generates semantic math audio, then ASR is used to test whether the audio can be recovered as text and whether important mathematical concept words remain recognizable.

## Row Preview

| Audio ID | Condition | Transcript | WER | Concept Recall | Status |
| --- | --- | --- | --- | --- | --- |
| ALG01 | mathontospeak_semantic | R- i-l-g-0-1. Equation x plus 3 equals 7. Matched concepts Variable, addition... | 0.112 | 1.000 | ok |
| ALG02 | mathontospeak_semantic | R- i-v-l-g-0-2. Equation 2x5 equals 9. Matched concepts. Number. Variable. Su... | 0.124 | 1.000 | ok |
| ALG03 | mathontospeak_semantic | R kyval jo3, equation x plus 1, x1, equals x squared 1, matched concepts, var... | 0.125 | 1.000 | ok |
| ALG04 | mathontospeak_semantic | R- i- i- i- i- i- i- i- i- i- i- i- i- i- i- i- i- i- | 0.979 | 0.000 | ok |
| CALC01 | mathontospeak_semantic | R-kind CALC01. Equation limb underscore x-right-pointing arrow 0-6, x-equals ... | 0.147 | 0.833 | ok |
| CALC02 | mathontospeak_semantic | Archive CalCO2, equation d dxx karat 3 equals 3x squared. Matched concepts, d... | 0.085 | 1.000 | ok |
| CALC03 | mathontospeak_semantic | Archive CalCO3, equation underscore zero to the power of 1x squared, matched ... | 0.109 | 1.000 | ok |
| LIN01 | mathontospeak_semantic | R i V l i n 0 1. Equation u plus v equals w. Matched concepts. Variable. Addi... | 0.231 | 1.000 | ok |
| LIN02 | mathontospeak_semantic | R kai vali n02. Equation x equals b. Matched concepts. Variable. Equality. Va... | 0.217 | 1.000 | ok |
| LIN03 | mathontospeak_semantic | Archivalin 03, equation A, equal 0, matched concepts, variable, equality, num... | 0.044 | 1.000 | ok |
