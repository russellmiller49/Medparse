from scripts.authors_fallback import enrich_authors_with_affiliations


def _make_docling_body() -> dict:
    return {
        "assembled": {
            "body": [
                {"label": "section_header", "text": "Authors"},
                {
                    "label": "text",
                    "text": (
                        "Peter Vilmann 1 , Paul Frost Clementsen 2,11 , "
                        "Enrique Vazquez-Sequeiros 8"
                    ),
                },
                {"label": "section_header", "text": "Institutions"},
                {
                    "label": "text",
                    "text": (
                        "1 Department of Surgical Gastroenterology, Endoscopy Unit, "
                        "Copenhagen University Hospital Herlev, Copenhagen, Denmark"
                    ),
                },
                {
                    "label": "text",
                    "text": (
                        "2 Department of Pulmonary Medicine, Gentofte University Hospital, "
                        "Hellerup, Denmark"
                    ),
                },
                {
                    "label": "text",
                    "text": (
                        "8 Department of Gastroenterology, University Hospital Ramón y Cajal, "
                        "Universidad de Alcala, Madrid, Spain"
                    ),
                },
                {
                    "label": "text",
                    "text": (
                        "11 Centre for Clinical Education, University of Copenhagen and the "
                        "Capital Region of Denmark, Copenhagen, Denmark"
                    ),
                },
            ]
        }
    }


def test_enrich_authors_adds_missing_affiliations():
    meta = {
        "authors": [
            {
                "display": "Peter Vilmann",
                "affiliations": [
                    {
                        "text": (
                            "Department of Surgical Gastroenterology, Endoscopy Unit, "
                            "Copenhagen University Hospital Herlev, Copenhagen, Denmark"
                        )
                    }
                ],
            },
            {"display": "Paul Clementsen"},
            {"display": "Enrique Vasquez-Sequeiros"},
        ]
    }

    docling = _make_docling_body()

    enrich_authors_with_affiliations(meta, docling)

    paul = meta["authors"][1]
    enrique = meta["authors"][2]

    assert paul.get("affiliation_ids") == [2, 11]
    assert enrique.get("affiliation_ids") == [8]

    paul_affs = [aff.get("text") for aff in paul.get("affiliations", [])]
    enrique_affs = [aff.get("text") for aff in enrique.get("affiliations", [])]

    assert any("Pulmonary Medicine" in (text or "") for text in paul_affs)
    assert any("Centre for Clinical Education" in (text or "") for text in paul_affs)
    assert any("Ramón y Cajal" in (text or "") for text in enrique_affs)

