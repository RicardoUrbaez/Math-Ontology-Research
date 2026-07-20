# 5. Evaluation

The evaluation examines MathOntoSpeak as a multi-perspective knowledge graph pipeline: ontology coverage, query performance, gloss-review readiness, TTS artifact generation, and a real-participant within-subjects user study.

The paper figures are organized around the system contribution and evaluation evidence: Figure 1 presents the five-layer architecture, Figure 2 shows the `T` concept graph with four surface forms, Figure 3 reports SPARQL benchmark response times, and Figure 4 shows the user-study comprehension chart with error bars.

## 5.1 Ontology and Metadata Coverage

The merged graph contains 504 ontology classes, 13 declared properties, and 13986 RDF statements. Of the ontology classes, 500 carry provenance-oriented metadata. This supports the central contribution because each speech rendering is tied to a concept node with labels, definitions, provenance, domain tags, and kind/role classification.

Figure 1 summarizes the five-layer architecture: source ontologies and metadata feed the merged knowledge graph, SPARQL/API access, surface-form rendering, and audio/evaluation outputs.

## 5.2 SPARQL Benchmark

The benchmark suite contains 10 representative SPARQL queries over the cleaned 500-concept graph. The local Fuseki `/mathkg500` benchmark completed with a mean response time of 52.359 ms and a maximum response time of 170.884 ms. Figure 3 reports the per-query timing profile and shows that graph lookup is practical for prototype interaction.

## 5.3 Gloss Review and Audio Quality

Gloss quality was evaluated with a 50-record Codex two-pass QC review. The review produced an overall Cohen's kappa of 0.93, with accuracy kappa 0.97, naturalness kappa 0.90, and cross-domain correctness kappa 0.91. This is an internal agreement metric rather than a human mentor review.

The audio artifact check confirms that 4 generated audio sets contain their expected files. The mean TTS audio quality rating is 5.00 on a 0-5 completeness scale.

As an additional ASR intelligibility check, the generated study audio was transcribed with the Whisper `tiny.en` model and compared with the intended notation-only or semantic gloss text. Whisper produced transcripts for 20 of 20 reviewed audio files, with a mean word error rate of 0.220. For the MathOntoSpeak semantic condition, mean concept-keyword recall was 0.883, showing that most generated semantic concept names were recoverable from the audio transcript. The weakest case was the hard finite-series example, where ASR failed to recover the repeated summation structure cleanly; this identifies pacing and equation complexity as useful targets for future audio tuning. The generated evidence is stored in `reports/evaluation/week6_whisper_asr_audio_qc.csv` and `reports/evaluation/week6_whisper_asr_audio_qc.md`.

## 5.4 User Study Results

In the real-participant within-subjects workbook, MathOntoSpeak semantic TTS produced a mean comprehension accuracy of 43.3%, compared with 35.0% for notation-only TTS. The paired t-test was t = 1.627, p = 0.138, with Cohen's dz = 0.514. NASA-TLX workload was 64.2 for MathOntoSpeak semantic TTS and 61.7 for notation-only TTS; the Wilcoxon signed-rank test was W = 19.000, p = 0.734.

The interview coding identified 3 themes: Semantic role clarity, Notation-only cognitive load, Pacing and domain familiarity.

These results come from real participants in the within-subjects study workbook. Figure 4 visualizes the comprehension difference between notation-only TTS and MathOntoSpeak semantic TTS with standard-error bars.

## 5.5 Summary

The completed technical evidence shows that MathOntoSpeak can serialize a provenance-tagged mathematical KG, query it through SPARQL, expose concept records to rendering code, generate multiple audio-oriented surface forms, and report a complete system evaluation table from available project evidence.

Figure 2 illustrates the key knowledge-graph contribution: one `T` concept node can be rendered through four formally named surface forms, allowing concise, pedagogical, expert, and document-role perspectives without duplicating the underlying graph node.
