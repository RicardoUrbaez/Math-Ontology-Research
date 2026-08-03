from scripts.mineru_pdf_worker import content_list_to_chunks


def test_content_list_to_chunks_preserves_heading_equation_page_and_bounds():
    chunks = content_list_to_chunks(
        [
            {
                "type": "text",
                "text": "3.3 Channel Matrix",
                "text_level": 1,
                "page_idx": 6,
                "bbox": [40, 50, 700, 90],
            },
            {
                "type": "text",
                "text": "The propagation channel is characterized by the channel matrix.",
                "page_idx": 6,
                "bbox": [40, 100, 700, 150],
            },
            {
                "type": "equation",
                "text": "$$h_{pn}=\\beta e^{-jkr_{np}}\\frac{\\lambda}{4\\pi r_{np}}$$ (4)",
                "page_idx": 6,
                "bbox": [120, 170, 620, 250],
            },
        ]
    )

    assert [chunk["kind"] for chunk in chunks] == [
        "section_heading",
        "paragraph",
        "equation",
    ]
    equation = chunks[-1]
    assert equation["page"] == 7
    assert equation["bbox"] == [120.0, 170.0, 620.0, 250.0]
    assert equation["source_label"] == "4"
    assert equation["latex"] == r"h_{pn}=\beta e^{-jkr_{np}}\frac{\lambda}{4\pi r_{np}}"
    assert equation["section_heading"] == "3.3 Channel Matrix"


def test_content_list_to_chunks_separates_mineru_latex_tag_from_formula():
    chunks = content_list_to_chunks(
        [
            {
                "type": "equation",
                "text": "$$r_{np}=\\sqrt{D^2+R_t^2+R_r^2}\\tag{A.3}$$",
                "page_idx": 4,
            }
        ]
    )

    assert chunks[0]["source_label"] == "A.3"
    assert chunks[0]["latex"] == r"r_{np}=\sqrt{D^2+R_t^2+R_r^2}"
