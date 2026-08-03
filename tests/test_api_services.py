import unittest
from unittest.mock import patch

from api.math_semantics import mathcat_notation_reading
from api.services import (
    FusekiClient,
    FusekiStatus,
    MathKGService,
    extract_paper_symbol_definitions,
    marker_structured_context_chunks,
)


class MathKGServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class OfflineFuseki:
            endpoint = "http://localhost:3030/mathkg500/query"
            dataset = "mathkg500"

            def status(self):
                return FusekiStatus(False, self.endpoint, self.dataset, "isolated test suite")

        cls.service = MathKGService(fuseki_client=OfflineFuseki())

    def test_semantic_search_returns_ranked_gloss_records(self):
        results = self.service.semantic_search("matrix linear algebra", limit=5)

        self.assertTrue(results)
        self.assertEqual(results[0]["canonical_label"], "Matrix")
        self.assertIn("linear-algebra", results[0]["domain_tags"])

    def test_half_power_uses_protege_mapped_taking_root_concept(self):
        payload = self.service.analyze_paper(
            title="Threshold energy",
            abstract_or_context=(
                "E sd is the surface-diffusion energy and A is the atomic mass number. "
                "Equation (3) gives the threshold incident energy."
            ),
            equations=[
                r"E_0^{\mathrm{th}}(\mathrm{eV})=(511\mathrm{keV})"
                r"\left\{\left[1+\frac{4AE_{sd}}{561\mathrm{eV}}\right]^{1/2}-1\right\}\tag{3}"
            ],
        )

        equation = payload["equations"][0]
        links = {link["canonical_label"]: link for link in equation["ontology_links"]}

        self.assertIn("Taking root", links)
        self.assertEqual(links["Taking root"]["provenance_type"], "structural_inference")
        self.assertEqual(equation["display_label"], "Equation 3")
        self.assertNotIn("g_(3)", equation["latex"])
        self.assertEqual(equation["structure_validation"]["status"], "valid")
        self.assertEqual(equation["confidence"]["structure"], "high")

    def test_ontology_runtime_reports_local_protege_snapshot_without_fuseki(self):
        class OfflineFuseki:
            endpoint = "http://localhost:3030/mathkg500/query"
            dataset = "mathkg500"

            def status(self):
                from api.services import FusekiStatus

                return FusekiStatus(False, self.endpoint, self.dataset, "offline test")

        payload = MathKGService(fuseki_client=OfflineFuseki()).analyze_paper(
            title="Ontology fallback",
            equations=["x=y+1"],
        )

        self.assertTrue(payload["ontology_runtime"]["available"])
        self.assertEqual(payload["ontology_runtime"]["query_mode"], "local_protege_snapshot")
        self.assertEqual(payload["pipeline"]["ontology"]["status"], "active_local")
        self.assertEqual(payload["ontology_runtime"]["gloss_records"], 500)

    def test_live_fuseki_enriches_equation_links_from_the_graph(self):
        class LiveFuseki:
            endpoint = "http://localhost:3030/mathkg500/query"
            dataset = "mathkg500"

            def status(self):
                return FusekiStatus(True, self.endpoint, self.dataset, "live test graph")

            def describe_concepts(self, concepts):
                taking_root = next(item for item in concepts if item["canonical_label"] == "Taking root")
                return [
                    {
                        "requested_iri": taking_root["concept_iri"],
                        "concept_iri": "http://example.org/mathkg/Takingroot",
                        "canonical_label": "Taking root",
                        "definition": "Taking a root reverses exponentiation for the represented quantity.",
                        "semantic_type": "scalar",
                        "kind_role": "kind",
                        "domain_tags": ["general-mathematics"],
                        "source_ontology": ["OntoMathPRO"],
                        "provenance_note": "Verified in the live Fuseki graph.",
                        "parent_concepts": [
                            {
                                "concept_iri": "http://example.org/mathkg/ScalarConcept",
                                "canonical_label": "Scalar Concept",
                            }
                        ],
                        "exact_matches": [taking_root["concept_iri"]],
                    }
                ]

        payload = MathKGService(fuseki_client=LiveFuseki()).analyze_paper(
            title="Live graph lookup",
            abstract_or_context="Equation (5) defines a distance using a square root.",
            equations=[r"r=\sqrt{x^2+y^2}\tag{5}"],
        )

        equation = payload["equations"][0]
        taking_root = next(
            link for link in equation["ontology_links"] if link["canonical_label"] == "Taking root"
        )
        self.assertEqual(payload["ontology_runtime"]["query_mode"], "live_fuseki")
        self.assertEqual(payload["ontology_runtime"]["live_equation_queries"], 1)
        self.assertEqual(taking_root["concept_iri"], "http://example.org/mathkg/Takingroot")
        self.assertEqual(taking_root["provenance_type"], "ontology_live_graph")
        self.assertIn("reverses exponentiation", taking_root["definition"])
        self.assertEqual(taking_root["parent_concepts"][0]["canonical_label"], "Scalar Concept")

    def test_fuseki_client_prefers_project_graph_node_for_external_exact_match(self):
        client = FusekiClient(timeout_seconds=1)
        result = {
            "results": {
                "bindings": [
                    {
                        "requestedIri": {"value": "http://external.example/root"},
                        "requestedLabel": {"value": "Taking root"},
                        "concept": {"value": "http://example.org/mathkg/Takingroot"},
                        "label": {"value": "Taking root"},
                        "definition": {"value": "A graph-backed square-root concept."},
                        "semanticType": {"value": "scalar"},
                        "kindRole": {"value": "kind"},
                        "domainTag": {"value": "general-mathematics"},
                        "sourceOntology": {"value": "OntoMathPRO"},
                        "provenanceNote": {"value": "Mapped and reviewed."},
                        "parent": {"value": "http://example.org/mathkg/ScalarConcept"},
                        "parentLabel": {"value": "Scalar Concept"},
                        "exactMatch": {"value": "http://external.example/root"},
                    }
                ]
            }
        }
        with patch.object(client, "query", return_value=result) as query:
            records = client.describe_concepts(
                [{"concept_iri": "http://external.example/root", "canonical_label": "Taking root"}]
            )

        self.assertEqual(records[0]["concept_iri"], "http://example.org/mathkg/Takingroot")
        self.assertEqual(records[0]["source_ontology"], ["OntoMathPRO"])
        self.assertEqual(records[0]["parent_concepts"][0]["canonical_label"], "Scalar Concept")
        sparql = query.call_args.args[0]
        self.assertIn("skos:exactMatch", sparql)
        self.assertIn("rdfs:subClassOf", sparql)

    def test_threshold_equation_reuses_definitions_from_earlier_pages(self):
        chunks = [
            {
                "source": "marker",
                "kind": "paragraph",
                "page": 2,
                "reading_order": 56,
                "block_id": "/page/1/Text/13",
                "section_heading": "2.1. Bulk displacement damage",
                "text": "Here A is the atomic mass number of the atom and the incident energy E 0 is in keV.",
            },
            {
                "source": "marker",
                "kind": "paragraph",
                "page": 2,
                "reading_order": 57,
                "block_id": "/page/1/Text/14",
                "section_heading": "2.1. Bulk displacement damage",
                "text": (
                    "There is a threshold incident energy Eth 0 below which displacement cannot occur "
                    "because E is less than E d even for 180 degree scattering."
                ),
            },
            {
                "source": "marker",
                "kind": "paragraph",
                "page": 3,
                "reading_order": 70,
                "block_id": "/page/2/Text/11",
                "section_heading": "2.3. Surface-atom displacement",
                "text": (
                    "For displacement of an atom along a surface, the energy transfer is largest for "
                    "90 degree scattering, so the corresponding threshold is"
                ),
            },
            {
                "source": "marker",
                "kind": "equation",
                "page": 3,
                "reading_order": 71,
                "block_id": "/page/2/Equation/12",
                "section_heading": "2.3. Surface-atom displacement",
                "source_label": "3",
                "latex": (
                    r"E_0^{\mathrm{th}}(\mathrm{eV}) = (511 \mathrm{keV}) "
                    r"\left\{\left[1 + \frac{4 A E_{sd}}{561 \mathrm{eV}}\right]^{1/2} - 1\right\}"
                ),
                "text": "Threshold energy formula (3)",
            },
            {
                "source": "marker",
                "kind": "paragraph",
                "page": 3,
                "reading_order": 73,
                "block_id": "/page/2/Text/13",
                "section_heading": "2.3. Surface-atom displacement",
                "text": "Here Esd is a surface-diffusion energy for displacement of an atom along a surface.",
            },
        ]
        with (
            patch(
                "api.services.extract_document_context",
                return_value=("\n\n".join(chunk["text"] for chunk in chunks), chunks, {"status": "ok", "extractor": "marker"}),
            ),
            patch("api.services.semantic_retrieval_status", return_value={"enabled": False}),
        ):
            payload = self.service.analyze_paper(
                title="Transmission electron microscope threshold energy",
                equations=[],
                pdf_base64="fixture",
                pdf_filename="microscope.pdf",
            )

        equation = payload["equations"][0]
        meanings = {term["symbol"]: term["meaning"] for term in equation["term_explanations"]}

        self.assertIn("atomic mass number", meanings["A"])
        self.assertIn("threshold incident energy", meanings[r"E_0^{\mathrm{th}}"])
        self.assertIn("surface-diffusion energy", meanings["E_sd"])
        self.assertNotIn("A", equation["unresolved_symbols"])

    def test_spaced_pdf_symbol_list_uses_paper_definitions_without_prose_false_positives(self):
        evidence = [
            {
                "evidence_id": "docling-28",
                "text": (
                    "In Fig. 1, D is the distance between the two antennas, P t the transmitted power, "
                    "G t the transmitter antenna gain, P r the received power, G r the receiver antenna "
                    "gain and L FS the free-space losses. In the next section, we derive the result. "
                    "For the array elements, the paper uses patch antennas."
                ),
            }
        ]

        definitions = extract_paper_symbol_definitions(evidence)

        self.assertEqual(definitions["Pr"]["meaning"], "received power")
        self.assertEqual(definitions["Pt"]["meaning"], "transmitted power")
        self.assertEqual(definitions["Gt"]["meaning"], "transmitter antenna gain")
        self.assertEqual(definitions["Gr"]["meaning"], "receiver antenna gain")
        self.assertEqual(definitions["LFS"]["meaning"], "free-space losses")
        self.assertNotIn("In", definitions)
        self.assertNotIn("For", definitions)

    def test_cross_disciplinary_discovery_bridges_from_seed(self):
        payload = self.service.cross_disciplinary_discovery(seed_concept="Matrix", target_domains=["calculus"], limit=5)

        self.assertEqual(payload["seed"]["canonical_label"], "Matrix")
        self.assertTrue(payload["results"])
        self.assertTrue(any("calculus" in result["domain_tags"] for result in payload["results"]))

    def test_concept_recommender_uses_latex_symbols_as_seeds(self):
        payload = self.service.recommend_concepts(latex=r"S=\sum_k a_k X_k", limit=5)
        seed_labels = {seed["canonical_label"] for seed in payload["seeds"]}

        self.assertIn("Equality", seed_labels)
        self.assertIn("Addition", seed_labels)
        self.assertTrue(payload["results"])

    def test_latex_accessibility_gloss_returns_json_tokens(self):
        payload = self.service.latex_accessibility_gloss(r"x \in \mathbb{R}", audience="pedagogical")
        labels = {token["canonical_label"] for token in payload["tokens"]}

        self.assertGreater(payload["resolved_count"], 0)
        self.assertIn("Variable", labels)
        self.assertIn("Real Number", labels)
        self.assertTrue(any("Think of" in token["surface_form"] for token in payload["tokens"]))

    def test_multi_equation_document_batches_semantic_context_ranking(self):
        chunks = [
            {
                "source": "mineru",
                "kind": "paragraph",
                "page": 2,
                "reading_order": 1,
                "block_id": "context-1",
                "text": "Equation (1) defines received power from transmitted power and antenna gain.",
            },
            {
                "source": "mineru",
                "kind": "paragraph",
                "page": 3,
                "reading_order": 2,
                "block_id": "context-2",
                "text": "Equation (2) defines a channel output as a transmitted signal plus additive noise.",
            },
        ]
        batch_scores = [
            [0.95, 0.10],
            [0.05, 0.98],
        ]
        with (
            patch(
                "api.services.extract_document_context",
                return_value=(
                    "\n\n".join(chunk["text"] for chunk in chunks),
                    chunks,
                    {"status": "ok", "extractor": "mineru", "pages_processed": 3},
                ),
            ),
            patch("api.services.semantic_retrieval_status", return_value={"enabled": True}),
            patch(
                "api.services.semantic_similarity_scores_batch",
                return_value=(batch_scores, {"status": "ok", "engine": "sentence_transformers"}),
            ) as semantic_batch,
            patch(
                "api.services.semantic_similarity_scores",
                side_effect=AssertionError("multi-equation analysis must not launch one model worker per equation"),
            ),
        ):
            payload = self.service.analyze_paper(
                title="Two equation paper",
                equations=[r"P_r=P_tG_t\tag{1}", r"y=hx+n\tag{2}"],
                pdf_base64="fixture",
                pdf_filename="two-equations.pdf",
            )

        self.assertEqual(len(payload["equations"]), 2)
        semantic_batch.assert_called_once()
        self.assertEqual(payload["pipeline"]["context_ranking"]["engine"], "sentence_transformers_batch")

    def test_document_analysis_reports_real_progress_stages(self):
        progress_updates = []
        with (
            patch(
                "api.services.extract_document_context",
                return_value=(
                    "Equation context.",
                    [],
                    {"status": "ok", "extractor": "pypdf", "pages_processed": 1},
                ),
            ),
            patch("api.services.semantic_retrieval_status", return_value={"enabled": False}),
        ):
            self.service.analyze_paper(
                title="Progress paper",
                equations=[r"x=1", r"y=2"],
                progress_callback=lambda stage, progress: progress_updates.append((stage, progress)),
            )

        stages = [stage for stage, _progress in progress_updates]
        values = [progress for _stage, progress in progress_updates]
        self.assertIn("ranking_document_evidence", stages)
        self.assertIn("analyzing_equation_1_of_2", stages)
        self.assertIn("analyzing_equation_2_of_2", stages)
        self.assertEqual(stages[-1], "finalizing_results")
        self.assertEqual(values, sorted(values))

    def test_math_speech_uses_speech_rule_engine_when_mathcat_is_unavailable(self):
        with patch(
            "api.math_semantics.speech_rule_engine_notation_reading",
            return_value=(
                "StartFraction a Over b EndFraction",
                {"engine": "speech_rule_engine", "available": True},
            ),
        ) as speech_rule_engine:
            spoken, status = mathcat_notation_reading(
                '<math><mfrac><mi>a</mi><mi>b</mi></mfrac></math>',
                "a divided by b",
            )

        speech_rule_engine.assert_called_once()
        self.assertEqual(spoken, "StartFraction a Over b EndFraction")
        self.assertEqual(status["engine"], "speech_rule_engine")

    def test_paper_analysis_keeps_unknown_symbols_explainable(self):
        payload = self.service.analyze_paper(
            title="Unknown symbol demo",
            abstract_or_context="A short proof introduces a custom operator for a local argument.",
            equations=[r"\mysteryop(z)=q"],
            audience="expert",
        )

        self.assertEqual(len(payload["equations"]), 1)
        equation = payload["equations"][0]
        self.assertEqual(equation["audio"]["status"], "skipped")
        self.assertIn("blind researcher", equation["why_it_helps"])
        self.assertIn("semantic_reading", equation)
        self.assertIn("Variable", equation["concepts"])
        self.assertTrue(equation["spoken_script"].startswith("Next, I am going to explain Equation 1"))
        unresolved = [term for term in equation["term_explanations"] if term["source"] == "unresolved"]
        self.assertTrue(unresolved)
        self.assertTrue(all(term["confidence"] == "low" for term in unresolved))

    def test_wireless_signal_context_builds_contextual_spoken_script(self):
        payload = self.service.analyze_paper(
            title="Wireless Information and Power Transfer",
            abstract_or_context=(
                "The received signal is produced after transmission through a wireless channel. "
                "The channel gain h scales the transmitted signal and additive receiver noise is included. "
                "Where x[k] is a unit-power baseband information signal, P is the average transmit power, "
                "h is the channel gain, n_A[k] is antenna noise, and n_cov[k] is conversion noise."
            ),
            equations=[r"\hat{y}[k]=\sqrt{h}P x[k]+\tilde{n}_A[k]+n_{cov}[k]"],
            audience="pedagogical",
        )

        equation = payload["equations"][0]
        summary = equation["context_summary"].lower()
        self.assertEqual(equation["equation_label"], "Equation 1")
        self.assertIn("signal", summary)
        self.assertIn("channel", summary)
        self.assertIn("noise", summary)
        self.assertTrue(equation["context_evidence"])
        self.assertTrue(equation["spoken_script"].startswith("Next, I am going to explain Equation 1"))
        self.assertIn("Term by term", equation["spoken_script"])
        self.assertTrue(
            any(
                term["symbol"] in {"x", "P", "h", "n_A", "n_cov"} and term["source"] == "paper_context"
                for term in equation["term_explanations"]
            )
        )
        self.assertTrue(any(link["canonical_label"] == "Addition" for link in equation["ontology_links"]))

    def test_plain_pdf_style_equation_text_is_detected_without_latex_delimiters(self):
        payload = self.service.analyze_paper(
            title="Plain PDF extraction",
            abstract_or_context=(
                "The received signal is then given by y[k] = sqrt(h) P x[k] + n_A[k] + n_cov[k], "
                "where x[k] is the information signal and n_A[k] is additive antenna noise."
            ),
            equations=[],
            audience="concise",
        )

        self.assertGreater(payload["extracted_equation_count"], 0)
        equation = payload["equations"][0]
        self.assertIn("=", equation["latex"])
        self.assertEqual(equation["extraction_confidence"], "medium")
        self.assertIn("signal", equation["context_summary"].lower())

    def test_manual_equation_uses_paper_context_when_pdf_equation_recovery_is_empty(self):
        payload = self.service.analyze_paper(
            title="Manual equation fallback",
            abstract_or_context=(
                "This section defines the received signal after channel scaling. "
                "Here x is the information signal and n is additive noise."
            ),
            equations=[r"y=h x+n"],
            audience="concise",
        )

        equation = payload["equations"][0]
        self.assertEqual(payload["extracted_equation_count"], 0)
        self.assertEqual(equation["extraction_confidence"], "user_supplied")
        self.assertTrue(equation["context_evidence"])
        self.assertIn("channel", equation["context_summary"].lower())
        self.assertIn("noise", equation["spoken_script"].lower())

    def test_uploaded_pdf_returns_document_context_preview(self):
        pdf_text = (
            "[Page 1]\nA wireless receiver observes a channel-scaled information signal. "
            "The received waveform also contains antenna and conversion noise."
        )
        pdf_chunks = [
            {
                "source": "pdf",
                "kind": "abstract",
                "text": (
                    "A wireless receiver observes a channel-scaled information signal. "
                    "The received waveform also contains antenna and conversion noise."
                ),
                "page": 1,
                "section_heading": "Abstract",
            }
        ]
        pdf_status = {
            "status": "ok",
            "extractor": "pypdf",
            "context_chunk_count": 1,
        }

        with patch(
            "api.services.extract_document_context",
            return_value=(pdf_text, pdf_chunks, pdf_status),
        ):
            payload = self.service.analyze_paper(
                title="Wireless paper",
                abstract_or_context="",
                equations=[r"y=hx+n"],
                pdf_base64="pdf-payload",
                pdf_filename="wireless.pdf",
            )

        document_context = payload["document_context"]
        self.assertEqual(document_context["source"], "pdf")
        self.assertEqual(document_context["extractor"], "pypdf")
        self.assertIn("wireless receiver", document_context["preview"].lower())
        self.assertNotIn("transformer", document_context["preview"].lower())

    def test_uploaded_pdf_exposes_complete_extracted_context_beyond_preview_limit(self):
        copyright_notice = (
            "This paper is published to AGU Radio Science and is subject to copyright. "
            "The copy of record will be available at the AGU Digital Library."
        )
        first_section = "Antenna and propagation background. " * 90
        final_section = "FINAL SECTION: Equation 12 defines the asymptotic OAM link budget."
        pdf_text = f"[Page 1]\n{copyright_notice}\n\n{first_section}\n\n[Page 32]\n{final_section}"
        pdf_chunks = [
            {
                "source": "marker",
                "kind": "paragraph",
                "text": copyright_notice,
                "page": 1,
                "reading_order": 0,
            },
            {
                "source": "marker",
                "kind": "paragraph",
                "text": first_section,
                "page": 1,
                "reading_order": 1,
            },
            {
                "source": "marker",
                "kind": "paragraph",
                "text": final_section,
                "page": 32,
                "reading_order": 200,
            },
        ]
        with (
            patch(
                "api.services.extract_document_context",
                return_value=(
                    pdf_text,
                    pdf_chunks,
                    {"status": "ok", "extractor": "marker", "pages_processed": 32},
                ),
            ),
            patch("api.services.semantic_retrieval_status", return_value={"enabled": False}),
        ):
            payload = self.service.analyze_paper(
                title="Complete context",
                equations=["x=1"],
                pdf_base64="pdf-payload",
                pdf_filename="long-paper.pdf",
            )

        document_context = payload["document_context"]
        self.assertLessEqual(len(document_context["preview"]), 2400)
        self.assertIn(final_section, document_context["extracted_text"])
        self.assertNotIn("copy of record", document_context["extracted_text"].lower())
        self.assertNotIn("copy of record", document_context["preview"].lower())
        self.assertTrue(document_context["preview_truncated"])
        self.assertEqual(document_context["analysis_scope"], "full_document")
        self.assertEqual(document_context["extracted_character_count"], len(document_context["extracted_text"]))
        self.assertEqual(document_context["pages_processed"], 32)

    def test_backend_audio_receives_the_contextual_spoken_script(self):
        skipped_audio = {
            "status": "skipped",
            "backend": "none",
            "detail": "captured by test",
            "audio_path": "",
        }
        with patch.object(
            self.service,
            "_maybe_generate_equation_audio",
            return_value=skipped_audio,
        ) as audio_generator:
            payload = self.service.analyze_paper(
                title="Audio contract",
                abstract_or_context=(
                    "The received signal is scaled by the channel and includes additive noise. "
                    "Here x is the information signal."
                ),
                equations=[r"y=h x+n"],
            )

        equation = payload["equations"][0]
        audio_arguments = audio_generator.call_args.kwargs
        self.assertEqual(audio_arguments["speech_text"], equation["spoken_script"])
        self.assertEqual(audio_arguments["ssml"], equation["ssml"])
        self.assertIn("Next, I am going to explain Equation 1", audio_arguments["ssml"])

    def test_geometry_equation_preserves_source_label_and_grouped_symbols(self):
        payload = self.service.analyze_paper(
            title="Geometry equation",
            abstract_or_context=(
                "Equation (5) gives the distance between the indexed points. "
                "The paper does not define the individual parameters in this excerpt."
            ),
            equations=[
                r"r_{np}=\sqrt{D^2+R_t^2+R_r^2-2R_tR_r\cos(\theta_{np})}\qquad(5)"
            ],
            audience="pedagogical",
        )

        equation = payload["equations"][0]
        symbols = {term["symbol"] for term in equation["grouped_expression"] if term["kind"] == "symbol"}

        self.assertEqual(equation["source_label"], "5")
        self.assertEqual(equation["display_label"], "Equation 5")
        self.assertEqual(equation["equation_label"], "Equation 5")
        self.assertTrue({"r_{np}", "R_t", "R_r", r"\theta_{np}"}.issubset(symbols))
        self.assertNotIn("R_tR", symbols)
        self.assertIn("r sub n p equals the square root of", equation["plain_notation_reading"].lower())
        self.assertIn("<math", equation["mathml"])
        self.assertEqual(equation["equation_role"]["label"], "geometry_distance")
        self.assertTrue(any(link["canonical_label"] == "Taking root" for link in equation["ontology_links"]))
        self.assertIn("D", equation["unresolved_symbols"])
        self.assertTrue(equation["speech_segments"])
        self.assertTrue(all(segment["text"] for segment in equation["speech_segments"]))

    def test_friis_equation_uses_paper_definitions_and_repairs_flattened_fraction(self):
        chunks = [
            {
                "source": "marker",
                "kind": "paragraph",
                "page": 6,
                "reading_order": 47,
                "block_id": "/page/5/Text/2",
                "section_heading": "2. Theory",
                "text": (
                    "A link budget addresses the efficiency of a communication system. It takes into "
                    "account all gains and losses from the transmitter to the receiver, associated with "
                    "both antennas and the propagation channel."
                ),
            },
            {
                "source": "marker",
                "kind": "paragraph",
                "page": 6,
                "reading_order": 48,
                "block_id": "/page/5/Text/3",
                "section_heading": "2. Theory",
                "text": (
                    "In Fig. 1, D is the distance between the two antennas, P t the transmitted power, "
                    "G t the transmitter antenna gain, P r the received power, G r the receiver antenna "
                    "gain and L FS the free-space losses. In its most concise form, P r is given by the "
                    "Friis transmission equation."
                ),
            },
            {
                "source": "marker",
                "kind": "equation",
                "page": 6,
                "reading_order": 49,
                "block_id": "/page/5/Equation/4",
                "section_heading": "2. Theory",
                "text": "Pr = PtGtGr LFS . (1)",
                "latex": "Pr = PtGtGr LFS .",
                "source_label": "1",
            },
        ]
        with (
            patch(
                "api.services.extract_document_context",
                return_value=("\n\n".join(chunk["text"] for chunk in chunks), chunks, {"status": "ok", "extractor": "marker"}),
            ),
            patch("api.services.semantic_retrieval_status", return_value={"enabled": False}),
        ):
            payload = self.service.analyze_paper(
                title="OAM link budget",
                equations=[],
                pdf_base64="fixture",
                pdf_filename="1504.00289v3-2.pdf",
            )

        equation = payload["equations"][0]
        meanings = {term["symbol"]: term["meaning"] for term in equation["term_explanations"]}

        self.assertEqual(equation["display_label"], "Equation 1")
        self.assertEqual(equation["equation_role"]["label"], "link_budget")
        self.assertIn(r"\frac{P_t G_t G_r}{L_{FS}}", equation["latex"])
        self.assertIn("friis transmission equation", equation["context_summary"].lower())
        self.assertIn("received power", equation["context_summary"].lower())
        self.assertIn("received power", meanings["P_r"].lower())
        self.assertIn("transmitted power", meanings["P_t"].lower())
        self.assertIn("transmitter antenna gain", meanings["G_t"].lower())
        self.assertIn("receiver antenna gain", meanings["G_r"].lower())
        self.assertIn("free-space losses", meanings["L_FS"].lower())
        self.assertNotIn("geometry", equation["context_summary"].lower())
        self.assertTrue(equation["formula_repairs"])
        self.assertIn("fraction with numerator", equation["plain_notation_reading"].lower())
        self.assertIn("denominator", equation["plain_notation_reading"].lower())

    def test_bfn_equation_recovers_fourier_sum_and_paper_defined_compound_symbols(self):
        chunks = [
            {
                "source": "marker",
                "kind": "paragraph",
                "page": 7,
                "reading_order": 120,
                "block_id": "/page/6/Text/5",
                "section_heading": "3.1. System configuration",
                "text": (
                    "In Fig. 2, aOAM l and b OAM l' are the complex input and output amplitudes "
                    "of each transmitted or received mode, respectively. Furthermore, a feed n "
                    "and b feed p are the wave amplitudes feeding the transmitter array or "
                    "collected at the receiver array, respectively."
                ),
            },
            {
                "source": "marker",
                "kind": "paragraph",
                "page": 8,
                "reading_order": 151,
                "block_id": "/page/7/Text/7",
                "section_heading": "3.2. BFN Matrix",
                "text": (
                    "On the one hand, to transmit several OAM modes of order l and amplitude "
                    "aOAM l, the antenna elements must be fed by"
                ),
            },
            {
                "source": "marker",
                "kind": "equation",
                "page": 8,
                "reading_order": 152,
                "block_id": "/page/7/Equation/8",
                "section_heading": "3.2. BFN Matrix",
                "source_label": "2",
                "latex": "a feed n = 1 sqrt N N X-1 l=0 a OAM l e -j2pi ln N, n in {0, ..., N - 1}",
                "text": "a feed n = 1 sqrt N N X-1 l=0 a OAM l e -j2pi ln N, n in {0, ..., N - 1} (2)",
            },
            {
                "source": "marker",
                "kind": "paragraph",
                "page": 8,
                "reading_order": 153,
                "block_id": "/page/7/Text/9",
                "section_heading": "3.2. BFN Matrix",
                "text": (
                    "with n the element index at the transmitter. This formulation defines an ideal "
                    "BFN that has N input ports associated with the transmission of OAM modes of "
                    "order l in {0, ..., N - 1}."
                ),
            },
            {
                "source": "marker",
                "kind": "paragraph",
                "page": 9,
                "reading_order": 170,
                "block_id": "/page/8/Text/3",
                "text": (
                    "From (2), the transmitter BFN matrix that relates the outputs a feed n to the "
                    "inputs aOAM l is the matrix of the Discrete Fourier Transform of size N."
                ),
            },
        ]
        with (
            patch(
                "api.services.extract_document_context",
                return_value=("\n\n".join(chunk["text"] for chunk in chunks), chunks, {"status": "ok", "extractor": "marker"}),
            ),
            patch("api.services.semantic_retrieval_status", return_value={"enabled": False}),
        ):
            payload = self.service.analyze_paper(
                title="OAM BFN matrix",
                equations=[],
                pdf_base64="fixture",
                pdf_filename="1504.00289v3-2.pdf",
            )

        equation = payload["equations"][0]
        meanings = {term["symbol"]: term["meaning"] for term in equation["term_explanations"]}

        self.assertEqual(equation["display_label"], "Equation 2")
        self.assertEqual(equation["equation_role"]["label"], "beamforming_transform")
        self.assertEqual(
            equation["latex"],
            r"a_n^{\mathrm{feed}} = \frac{1}{\sqrt{N}} \sum_{l=0}^{N-1} "
            r"a_l^{\mathrm{OAM}} e^{-j 2\pi l n/N}, \quad n \in \{0,\ldots,N-1\}",
        )
        self.assertIn("transmitter", equation["context_summary"].lower())
        self.assertIn("normalized sum", equation["context_summary"].lower())
        self.assertIn("wave amplitude feeding the transmitter array", meanings[r"a_n^{\mathrm{feed}}"].lower())
        self.assertIn("complex input amplitude", meanings[r"a_l^{\mathrm{OAM}}"].lower())
        self.assertIn("element index at the transmitter", meanings["n"].lower())
        self.assertFalse({"f", "e", "d", "O", "A", "M", "X"}.intersection(equation["unresolved_symbols"]))
        self.assertTrue(equation["formula_repairs"])
        self.assertIn("sum from l equals 0 to N minus 1", equation["plain_notation_reading"])
        self.assertIn("n is a member of the set", equation["plain_notation_reading"])

    def test_channel_matrix_equation_restores_structure_and_teaches_from_paper_evidence(self):
        chunks = [
            {
                "source": "marker",
                "kind": "paragraph",
                "page": 9,
                "reading_order": 169,
                "block_id": "/page/8/Text/5",
                "section_heading": "3.3. Channel Matrix",
                "text": (
                    "The propagation channel of this system can be characterized by the channel matrix H. "
                    "Its terms hpn correspond to the propagation from the phase center of the n-th element "
                    "of the transmitter to the phase center of the p-th element of the receiver."
                ),
            },
            {
                "source": "marker",
                "kind": "equation",
                "page": 9,
                "reading_order": 173,
                "block_id": "/page/8/Equation/6",
                "section_heading": "3.3. Channel Matrix",
                "source_label": "4",
                "latex": "hpn = beta e - jkrnp lambda 4pi rnp",
                "text": "hpn = beta e - jkrnp lambda 4pi rnp, (4)",
            },
            {
                "source": "marker",
                "kind": "paragraph",
                "page": 9,
                "reading_order": 175,
                "block_id": "/page/8/Text/7",
                "section_heading": "3.3. Channel Matrix",
                "text": (
                    "This gives the point-to-point link without coupling terms. "
                    "The distance between each antenna element is given by Equation (5)."
                ),
            },
            {
                "source": "marker",
                "kind": "paragraph",
                "page": 9,
                "reading_order": 179,
                "block_id": "/page/8/Text/11",
                "section_heading": "3.3. Channel Matrix",
                "text": (
                    "The free space losses are 4 pi rnp over lambda, the propagation term is the exponent, "
                    "lambda is the wavelength of the carrier."
                ),
            },
            {
                "source": "marker",
                "kind": "paragraph",
                "page": 10,
                "reading_order": 180,
                "block_id": "/page/9/Text/2",
                "section_heading": "3.3. Channel Matrix",
                "text": (
                    "Beta contains all the variables associated with the antenna system configuration. "
                    "For large distances it is related to the axial antenna gains."
                ),
            },
        ]
        with (
            patch(
                "api.services.extract_document_context",
                return_value=("\n\n".join(chunk["text"] for chunk in chunks), chunks, {"status": "ok", "extractor": "marker"}),
            ),
            patch("api.services.semantic_retrieval_status", return_value={"enabled": False}),
        ):
            payload = self.service.analyze_paper(
                title="OAM channel matrix",
                equations=[],
                pdf_base64="fixture",
                pdf_filename="1504.00289v3-2.pdf",
            )

        equation = payload["equations"][0]
        meanings = {term["symbol"]: term["meaning"] for term in equation["term_explanations"]}

        self.assertEqual(equation["display_label"], "Equation 4")
        self.assertEqual(equation["equation_role"]["label"], "channel_coefficient")
        self.assertEqual(
            equation["latex"],
            r"h_{pn} = \beta e^{-j k r_{np}} \frac{\lambda}{4\pi r_{np}}",
        )
        self.assertIn("transmitter element n", equation["context_summary"].lower())
        self.assertIn("receiver element p", equation["context_summary"].lower())
        self.assertIn("three factors", equation["conceptual_structure"].lower())
        self.assertIn("channel-matrix coefficient", meanings["h_pn"].lower())
        self.assertIn("antenna system configuration", meanings[r"\beta"].lower())
        self.assertIn("wavelength of the carrier", meanings[r"\lambda"].lower())
        self.assertIn("distance", meanings["r_np"].lower())
        self.assertIn("does not explicitly define k", meanings["k"].lower())
        self.assertIn("conceptually", equation["spoken_script"].lower())
        self.assertIn("over 4 pi", equation["plain_notation_reading"].lower())
        self.assertTrue(equation["formula_repairs"])

    def test_distance_equation_recovers_root_powers_and_compound_symbols_generically(self):
        chunks = [
            {
                "source": "marker",
                "kind": "paragraph",
                "page": 9,
                "reading_order": 91,
                "block_id": "/page/8/Text/7",
                "section_heading": "Channel Matrix",
                "text": "The distance between each antenna element is given by",
            },
            {
                "source": "marker",
                "kind": "equation",
                "page": 9,
                "reading_order": 92,
                "block_id": "/page/8/Equation/8",
                "section_heading": "Channel Matrix",
                "source_label": "5",
                "latex": "rnp = q D 2 + R 2 t + R 2 r - 2 RtR r cos (theta np)",
                "text": "rnp = q D 2 + R 2 t + R 2 r - 2 RtR r cos (theta np), (5)",
            },
            {
                "source": "marker",
                "kind": "paragraph",
                "page": 9,
                "reading_order": 93,
                "block_id": "/page/8/Text/9",
                "section_heading": "Channel Matrix",
                "text": "with theta np = 2 pi times the difference between n and p divided by N.",
            },
        ]
        with (
            patch(
                "api.services.extract_document_context",
                return_value=("\n\n".join(chunk["text"] for chunk in chunks), chunks, {"status": "ok", "extractor": "marker"}),
            ),
            patch("api.services.semantic_retrieval_status", return_value={"enabled": False}),
        ):
            payload = self.service.analyze_paper(
                title="Unrelated geometry paper",
                equations=[],
                pdf_base64="fixture",
                pdf_filename="arbitrary-upload.pdf",
            )

        equation = payload["equations"][0]
        self.assertEqual(
            equation["latex"],
            r"r_{np} = \sqrt{D^2 + R_t^2 + R_r^2 - 2 R_t R_r \cos(\theta_{np})}",
        )
        self.assertEqual(equation["structure_validation"]["status"], "valid")
        self.assertTrue(any(item["kind"] == "root_geometry_structure" for item in equation["formula_repairs"]))
        self.assertIn("square root", equation["plain_notation_reading"].lower())
        self.assertIn("distance between each antenna element", equation["context_summary"].lower())

    def test_grounded_provider_rejects_claims_with_unknown_evidence(self):
        class UnsupportedProvider:
            name = "test-provider"

            def explain(self, _packet):
                return {
                    "context_summary": "Equation 1 definitely measures orbital velocity.",
                    "evidence_ids": ["evidence-that-does-not-exist"],
                    "term_explanations": [
                        {
                            "symbol": "q",
                            "meaning": "orbital velocity",
                            "evidence_ids": ["evidence-that-does-not-exist"],
                        }
                    ],
                }

        service = MathKGService(explanation_provider=UnsupportedProvider())
        payload = service.analyze_paper(
            title="Grounding guard",
            abstract_or_context="The paper introduces q as an otherwise unspecified quantity.",
            equations=["y=q+1"],
        )

        equation = payload["equations"][0]
        self.assertNotIn("orbital velocity", equation["context_summary"])
        self.assertTrue(any(term["symbol"] == "q" and term["source"] == "unresolved" for term in equation["term_explanations"]))
        self.assertEqual(equation["explanation_provider"]["status"], "rejected")

    def test_manual_wireless_equation_matches_its_paper_location_before_global_definitions(self):
        chunks = [
            {
                "source": "pdf",
                "kind": "paragraph",
                "page": 2,
                "reading_order": 1,
                "block_id": "page-2-definitions",
                "text": (
                    "The complex baseband signal x(t) is a narrow-band signal with unit power. "
                    "P is the average transmit power. The transmitted signal propagates through a wireless "
                    "channel with channel gain h. The noise nA(t) after the receiving antenna is antenna noise."
                ),
            },
            {
                "source": "pdf",
                "kind": "paragraph",
                "page": 3,
                "reading_order": 2,
                "block_id": "page-3-equation-1",
                "text": (
                    "Corrupted by antenna noise, the received signal y(t) is given by y(t)=sqrt(2)Re(ytilde(t)). "
                    "The complex signal ytilde(t)=sqrt(hP)x(t)exp(j(2 pi f t+theta))+nA(t)exp(j2 pi f t). (1)"
                ),
            },
            {
                "source": "pdf",
                "kind": "paragraph",
                "page": 6,
                "reading_order": 3,
                "block_id": "page-6-other-equation",
                "text": "For Equation (25), X denotes the signal power and Y denotes the channel output.",
            },
        ]
        pdf_text = "\n\n".join(chunk["text"] for chunk in chunks)
        with patch(
            "api.services.extract_document_context",
            return_value=(pdf_text, chunks, {"status": "ok", "extractor": "pypdf"}),
        ):
            payload = self.service.analyze_paper(
                title="Wireless paper",
                equations=[r"\tilde{y}(t)=\sqrt{hP}x(t)e^{j(2\pi ft+\theta)}+\tilde{n}_A(t)e^{j2\pi ft}\tag{1}"],
                pdf_base64="fixture",
                pdf_filename="wireless.pdf",
            )

        equation = payload["equations"][0]
        meanings = {term["symbol"]: term["meaning"] for term in equation["term_explanations"]}
        self.assertEqual(equation["page"], 3)
        self.assertEqual(equation["extraction_method"], "manual_equation_matched_to_paper")
        self.assertIn("narrow-band signal", meanings["x"])
        self.assertIn("channel gain", meanings["h"])
        self.assertNotIn("signal power", " ".join(meanings.values()))

    def test_marker_equation_uses_local_paper_definitions_instead_of_other_columns(self):
        marker_payload = [
            {
                "id": "/page/0/Text/31",
                "block_type": "Text",
                "html": (
                    '<p block-type="Text">Use of the de Broglie relation shows that an electron '
                    "wavelength is sufficient for atomic resolution.</p>"
                ),
                "polygon": [[40, 511], [295, 511], [295, 587], [40, 587]],
            },
            {
                "id": "/page/1/SectionHeader/9",
                "block_type": "SectionHeader",
                "html": '<h2 block-type="SectionHeader">2.1. Bulk displacement damage</h2>',
                "polygon": [[298, 311], [419, 311], [419, 324], [298, 324]],
            },
            {
                "id": "/page/1/Text/10",
                "block_type": "Text",
                "html": (
                    '<p block-type="Text">The energy that an electron can lose by elastic scattering '
                    "through an angle is E=Emax sin squared theta over two, where Emax is the maximum "
                    "energy transfer that corresponds to a scattering angle of 180 degrees, which is "
                    "given in eV by</p>"
                ),
                "polygon": [[298, 332], [556, 332], [556, 377], [298, 377]],
            },
            {
                "id": "/page/1/Equation/12",
                "block_type": "Equation",
                "html": '<p block-type="Equation">EmaxðeVÞ¼ð1:1=AÞ½2þE0=ð511 keVÞE0ðkeVÞð1Þ</p>',
                "polygon": [[299, 378], [556, 378], [556, 392], [299, 392]],
            },
            {
                "id": "/page/1/Text/13",
                "block_type": "Text",
                "html": (
                    '<p block-type="Text">Here A is the atomic mass number of the atom and the incident '
                    "energy E<sup>0</sup> is in keV.</p>"
                ),
                "polygon": [[298, 396], [555, 396], [555, 419], [298, 419]],
            },
        ]
        chunks = marker_structured_context_chunks(marker_payload)
        paper_text = "\n\n".join(chunk["text"] for chunk in chunks)

        with patch(
            "api.services.extract_document_context",
            return_value=(paper_text, chunks, {"status": "ok", "extractor": "marker"}),
        ):
            payload = self.service.analyze_paper(
                title="Choice of operating voltage for a transmission electron microscope",
                equations=[],
                pdf_base64="fixture",
                pdf_filename="electron-microscope.pdf",
            )

        equation = payload["equations"][0]
        meanings = {term["symbol"]: term["meaning"] for term in equation["term_explanations"]}
        evidence_text = " ".join(item["text"] for item in equation["context_evidence"])

        self.assertEqual(equation["display_label"], "Equation 1")
        self.assertNotIn("block-type", equation["latex"])
        self.assertIn("E_{max}", equation["latex"])
        self.assertIn("E_0", equation["latex"])
        self.assertIn("1.1/A", equation["latex"])
        self.assertIn("maximum energy transfer", equation["context_summary"].lower())
        self.assertIn("elastic scattering", equation["context_summary"].lower())
        self.assertIn("maximum energy transfer", meanings["E_max"].lower())
        self.assertIn("atomic mass number", meanings["A"].lower())
        self.assertIn("incident energy", meanings["E_0"].lower())
        self.assertNotIn("de broglie", evidence_text.lower())
        self.assertNotIn("type equals equation", equation["plain_notation_reading"].lower())
        self.assertIn("1.1 divided by A", equation["plain_notation_reading"])
        self.assertIn("E sub max of eV", equation["spoken_script"])
        self.assertNotIn("mathrm", equation["spoken_script"])

    def test_automatic_unlabeled_formula_is_not_mislabeled_as_printed_equation_one(self):
        chunks = [
            {
                "source": "marker",
                "kind": "equation",
                "text": "x = y + 1",
                "latex": "x=y+1",
                "page": 1,
                "reading_order": 1,
                "block_id": "/page/0/Equation/1",
            }
        ]
        with patch(
            "api.services.extract_document_context",
            return_value=("x = y + 1", chunks, {"status": "ok", "extractor": "marker"}),
        ):
            payload = self.service.analyze_paper(
                equations=[],
                pdf_base64="fixture",
                pdf_filename="unlabeled.pdf",
            )

        equation = payload["equations"][0]
        self.assertEqual(equation["source_label"], "")
        self.assertEqual(equation["display_label"], "Unnumbered equation 1")


if __name__ == "__main__":
    unittest.main()
