from __future__ import annotations
from typing import List, Dict, Any, Optional

def link_with_quickumls(text: str, quickumls_path: Optional[str] = None) -> List[Dict[str,Any]]:
    try:
        from quickumls import QuickUMLS
    except Exception:
        return []
    if not quickumls_path:
        return []
    matcher = QuickUMLS(quickumls_path, threshold=0.9, best_match=True, similarity_name="jaccard")
    results = matcher.match(text, ignore_syntax=False)
    out = []
    for sent in results:
        for cand in sent:
            c = cand[0]
            out.append({"phrase": c["term"], "cui": c["cui"], "preferred": c.get("preferred",""), "source": "QuickUMLS"})
    return out

def link_with_scispacy(text: str, model: str = "en_core_sci_md") -> List[Dict[str,Any]]:
    try:
        import spacy
        from scispacy.umls_linking import UmlsEntityLinker
    except Exception:
        return []
    nlp = spacy.load(model)
    nlp.add_pipe("abbreviation_detector")
    linker = UmlsEntityLinker(resolve_abbreviations=True, max_entities_per_mention=1)
    nlp.add_pipe(linker)
    doc = nlp(text[:500000])
    out = []
    for ent in doc.ents:
        if not ent._.umls_ents: continue
        cui, score = ent._.umls_ents[0]
        pref = ""
        if hasattr(linker, "umls") and hasattr(linker.umls, "cui_to_entity") and cui in linker.umls.cui_to_entity:
            pref = linker.umls.cui_to_entity[cui].canonical_name
        out.append({"phrase": ent.text, "cui": cui, "preferred": pref, "source": "scispaCy"})
    return out