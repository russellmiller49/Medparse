from typing import Any, Dict, Optional


def add_patch(obj: Dict[str, Any], path: str, old: Any, new: Any, source: str, confidence: float = 0.9) -> None:
    prov = obj.setdefault("provenance", {})
    patches = prov.setdefault("patches", [])
    patches.append({
        "path": path,
        "op": "set",
        "from": old,
        "to": new,
        "source": source,
        "confidence": confidence,
    })

