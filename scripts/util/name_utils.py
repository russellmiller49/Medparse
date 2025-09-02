import re
from typing import Optional, Dict

try:
    from nameparser import HumanName  # type: ignore
except Exception:  # pragma: no cover
    HumanName = None  # fallback


DEG_RX = re.compile(r"\b(MD|DO|PhD|DPhil|MPH|MS|MSc|RN|FCCP|FRCP|FACP)\b\.?", re.I)
ACK_TOKENS = (
    "author contributions",
    "contribution",
    "guarantor",
    "ethic",
    "conflict of interest",
    "acknowledg",
    "funding",
    "data availability",
    "investigator list",
    "supplementary",
)
GROUP_TOKENS = ("group", "consortium", "investigator", "investigators", "collaboration")


def is_ack_like(s: str) -> bool:
    s = s.lower()
    return any(t in s for t in ACK_TOKENS)


def classify_entry(s: str) -> Dict[str, bool]:
    lower = s.lower()
    if is_ack_like(lower):
        return {"drop": True, "group": False}
    if any(t in lower for t in GROUP_TOKENS):
        return {"drop": False, "group": True}
    return {"drop": False, "group": False}


def _simple_split_person(author_str: str) -> Optional[dict]:
    # minimal parser if nameparser is unavailable
    raw = author_str.strip()
    parts = [p for p in re.split(r"\s+", re.sub(DEG_RX, "", raw)) if p]
    if len(parts) == 1:
        given, family = "", parts[0]
    elif len(parts) >= 2:
        given, family = " ".join(parts[:-1]), parts[-1]
    else:
        return None
    return {
        "given": given.strip(),
        "family": family.strip(),
        "suffix": None,
        "degrees": [],
        "display": raw,
    }


def to_person(author_str: str) -> Optional[dict]:
    raw = author_str.strip()
    degs = DEG_RX.findall(raw)
    clean = DEG_RX.sub("", raw)

    if HumanName is None:
        base = _simple_split_person(raw)
    else:
        hn = HumanName(clean)
        given = " ".join(x for x in [hn.first, hn.middle] if x).strip()
        fam = (hn.last or "").strip()
        if not (given or fam):
            base = None
        else:
            base = {
                "given": given or "",
                "family": fam or "",
                "suffix": (hn.suffix or None) or None,
                "degrees": [],
                "display": raw,
            }

    if base is None:
        return None
    if degs:
        base["degrees"] = list(dict.fromkeys([d.upper().replace(".", "") for d in degs]))
    return base

