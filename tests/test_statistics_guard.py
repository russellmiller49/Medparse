from medparse.extract.statistics import extract_statistics

def test_grant_id_not_stat():
    text = "Funding: NIH grant 1U54HL119810-03 supported this work."
    stats = extract_statistics(text)
    assert stats == [], "Grant identifiers must not be parsed as statistics"

def test_citation_tuple_not_stat():
    text = "Prior studies (3,4) described this phenomenon."
    stats = extract_statistics(text)
    assert stats == [], "Reference citations like (3,4) must not be parsed as statistics"

def test_ci_with_cue_is_captured():
    text = "The risk decreased (95% CI: 0.80–0.95; p=0.01) in the treatment arm."
    stats = extract_statistics(text)
    assert any(s["type"]=="ci" for s in stats)
    assert any(s["type"]=="p_value" for s in stats)