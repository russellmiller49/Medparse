import re
from typing import List

DOI_RX = re.compile(r"10\.\d{4,9}/\S+", re.I)
TRAILING = ",.;)]}>\"'"


def extract_candidate_dois(text: str) -> List[str]:
    out = []
    for m in DOI_RX.finditer(text):
        doi = m.group(0)
        # strip obvious prefixes and trailing punctuation
        doi = re.sub(r"^doi\s*[:]\s*", "", doi, flags=re.I)
        doi = doi.strip().rstrip(TRAILING)
        out.append(doi.lower())
    # de-dup preserve order
    dedup = []
    seen = set()
    for d in out:
        if d not in seen:
            seen.add(d)
            dedup.append(d)
    return dedup

