import os, json, glob
from PIL import Image
from pathlib import Path

def print_exif(path: Path):
    try:
        im = Image.open(path)
        exif = im.getexif()
        if exif:
            # 270: ImageDescription
            desc = exif.get(270, "")
            print(f"EXIF ImageDescription: {desc}")
        else:
            print("No EXIF found.")
    except Exception as e:
        print(f"EXIF read error: {e}")

def main():
    print("Python OK.")
    # Check outputs if present
    js = sorted(Path("out/json").glob("*.json"))
    if js:
        with open(js[0], "r", encoding="utf-8") as f:
            data = json.load(f)
        print("Sample JSON keys:", list(data.keys()))
        print("Validation:", data.get("validation", {}))
        print("Statistics count:", len(data.get("statistics", [])))
        print("Trial IDs:", data.get("trial_ids", []))
        print("Enriched refs:", len(data.get("references_enriched", [])))
    figs = sorted(Path("out/figures").glob("*.jpg"))
    if figs:
        print(f"Found {len(figs)} figure crops; checking EXIF on first:")
        print_exif(figs[0])
    refs = sorted(Path("out/references").glob("*.csv"))
    if refs:
        print("Found references CSV:", refs[0])
    print("Smoke test done.")

if __name__ == "__main__":
    main()

