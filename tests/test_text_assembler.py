from scripts.text_assembler import (
    assemble_sections,
    build_full_text,
    compute_page_text_ratio,
)


def _make_docling_body(entries):
    return {
        "document": {},
        "assembled": {"body": entries},
    }


def test_assemble_sections_prefers_tei_and_adds_missing_titles():
    tei = """
    <TEI xmlns=\"http://www.tei-c.org/ns/1.0\">
      <text><body>
        <div><head>Background</head><p>Primary background content.</p></div>
        <div><head>Conclusions</head><p>Summary of findings.</p></div>
      </body></text>
    </TEI>
    """

    docling = _make_docling_body([
        {"label": "section_header", "text": "Background"},
        {"label": "text", "text": "Primary background content."},
        {"label": "section_header", "text": "Appendix"},
        {"label": "text", "text": "Additional appendix material."},
    ])

    sections = assemble_sections(tei, docling)
    titles = [sec.get("title") for sec in sections]

    assert "Background" in titles
    assert "Appendix" in titles  # appended from Docling fallback

    background = next(sec for sec in sections if sec.get("title") == "Background")
    assert len(background["paragraphs"]) == 1
    assert background["paragraphs"][0]["text"] == "Primary background content."


def test_assemble_sections_extends_when_tei_is_sparse():
    tei = """
    <TEI xmlns=\"http://www.tei-c.org/ns/1.0\">
      <text><body>
        <div><head>Introduction</head><p>Short overview.</p></div>
      </body></text>
    </TEI>
    """

    docling = _make_docling_body([
        {"label": "section_header", "text": "Introduction"},
        {"label": "text", "text": "Short overview."},
        {"label": "text", "text": "Extended context and objectives."},
    ])

    sections = assemble_sections(tei, docling)
    intro = next(sec for sec in sections if sec.get("title") == "Introduction")

    texts = [p["text"] for p in intro["paragraphs"]]
    assert "Short overview." in texts
    assert "Extended context and objectives." in texts


def test_page_text_ratio_uses_docling_sections():
    docling = _make_docling_body([
        {"label": "section_header", "text": "Intro"},
        {"label": "text", "text": "Alpha Beta"},
        {"label": "text", "text": "Gamma"},
    ])
    sections = assemble_sections(None, docling)
    full_text = build_full_text(sections)

    ratio = compute_page_text_ratio(docling, full_text)
    assert ratio == 1.0


def test_inline_hyphenation_is_smoothed():
    docling = _make_docling_body([
        {"label": "section_header", "text": "Body"},
        {"label": "text", "text": "Neth-erlands mediastinosco-py follow-up"},
    ])

    sections = assemble_sections(None, docling)
    body = next(sec for sec in sections if sec.get("title") == "Body")
    text = " ".join(para["text"] for para in body["paragraphs"])

    assert "Netherlands" in text
    assert "mediastinoscopy" in text
    # Legitimate hyphenated words remain
    assert "follow-up" in text
