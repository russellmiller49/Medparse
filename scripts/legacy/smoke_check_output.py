import json, sys
from pathlib import Path

def main(p: Path):
    data = json.loads(p.read_text(encoding="utf-8"))
    if data.get("schema_name") == "DoclingDocument":
        raise SystemExit("❌ Output is a DoclingDocument (raw). Expected merged pipeline JSON.")
    for req in ("metadata","structure"):
        if req not in data:
            raise SystemExit(f"❌ Missing required top-level key: {req}")
    # Heuristic: reject base64-embedded images in the final JSON
    txt = p.read_text(encoding="utf-8")
    if "data:image" in txt:
        raise SystemExit("❌ Found base64 inline images in final JSON; figures should be file refs, not embedded.")
    size_mb = p.stat().st_size / (1024*1024)
    if size_mb > 8:
        raise SystemExit(f"❌ Output looks too large ({size_mb:.1f} MB). Likely raw Docling slipped in.")
    print("✅ Smoke check passed:", p)

if __name__ == "__main__":
    main(Path(sys.argv[1]))

