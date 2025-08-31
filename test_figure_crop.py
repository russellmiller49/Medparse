#!/usr/bin/env python3
from pathlib import Path
from docling.document_converter import DocumentConverter
from scripts.figure_cropper import crop_figures
import json

pdf = Path("input/AMPLE2.pdf")
print(f"Processing: {pdf}")

converter = DocumentConverter()
result = converter.convert(str(pdf))
dl_doc = result.model_dump()

print("\nTesting figure cropping...")
fig_stats = crop_figures(pdf, dl_doc, Path("test_figures"))

print(f"\nFigure stats:")
print(f"  Saved: {fig_stats['n_saved']}")
print(f"  Missing bbox: {fig_stats['n_missing_bbox']}")

# Check what's in pictures
doc = dl_doc.get("document", {})
pictures = doc.get("pictures", [])
print(f"\nTotal pictures in document: {len(pictures)}")

if pictures:
    pic = pictures[0]
    print(f"\nFirst picture structure:")
    if isinstance(pic.get("prov"), list) and pic["prov"]:
        prov = pic["prov"][0]
        print(f"  Page no: {prov.get('page_no')}")
        bbox = prov.get("bbox", {})
        print(f"  Bbox: l={bbox.get('l')}, t={bbox.get('t')}, r={bbox.get('r')}, b={bbox.get('b')}")
        print(f"  Coord origin: {bbox.get('coord_origin')}")