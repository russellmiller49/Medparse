import re
from typing import List, Dict, Any

DOSE = r'(?:\d+(?:\.\d+)?\s*(?:mg|mcg|g|mL|units)(?:/\w+)?(?:\s*(?:qd|q\d+h|bid|tid|qid|qam|qpm|hs|prn))?)'
NAME_SUFFIXES = r'(?:mab|nib|pril|sartan|olol|cillin|azole|avir|mycin|dipine|zumab|lukast|oxetine|aparin|sone|statin)'
PATTERN = re.compile(rf'\b([A-Z][a-zA-Z\-]{{2,}}{NAME_SUFFIXES})\b\s*(?:{DOSE})?', re.IGNORECASE)

def extract_drugs_dosages(text: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for m in PATTERN.finditer(text):
        drug = m.group(1)
        span_end = m.end()
        ctx = text[span_end: span_end+80]
        dose_m = re.search(DOSE, ctx, flags=re.IGNORECASE)
        dose = dose_m.group(0) if dose_m else None
        out.append({"drug": drug, "dose": dose, "span": [m.start(), span_end], "context": text[max(0, m.start()-40): span_end+80]})
    return out