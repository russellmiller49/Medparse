import json
from pathlib import Path

def _sanity_check(obj: dict):
    # Never allow the raw Docling document to be written as final output
    if isinstance(obj, dict) and obj.get("schema_name") == "DoclingDocument":
        raise RuntimeError("Attempted to write Docling raw document; expected merged pipeline JSON.")
    for k in ("metadata", "structure"):
        if k not in obj:
            raise RuntimeError(f"Merged JSON missing required key: '{k}'")

def safe_write_json(obj: dict, out_path: Path, indent: int = 2) -> Path:
    _sanity_check(obj)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=indent)
    return out_path