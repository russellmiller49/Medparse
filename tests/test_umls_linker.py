from medparse.linking.umls_linker import link_umls_spans

def dummy_kb(q):
    # Return an intentionally bad candidate to ensure gates work
    return [{"cui":"C1998444","name":"History of three doses of hepatitis B vaccine", "score":0.99, "semtypes":["PROC"]}]

def test_history_of_three_is_blocked():
    spans = [("History of three", (0,17))]
    out = link_umls_spans(spans, kb_lookup=dummy_kb)
    assert out == [], "Bare 'History of three' must not link to UMLS"