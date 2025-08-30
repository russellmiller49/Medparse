MEDICAL_SECTION_MAP = {
    "abstract": ["abstract", "summary", "synopsis"],
    "introduction": ["introduction", "background", "rationale"],
    "methods": ["methods", "methodology", "materials and methods", "study design", "participants"],
    "results": ["results", "findings", "outcomes", "efficacy"],
    "discussion": ["discussion", "interpretation", "implications"],
    "limitations": ["limitations", "study limitations", "caveats"],
    "conclusion": ["conclusion", "conclusions", "summary and conclusions"]
}

def classify_section(title: str) -> str:
    t = (title or "").lower().strip()
    for cat, pats in MEDICAL_SECTION_MAP.items():
        if any(p in t for p in pats):
            return cat
    return "other"