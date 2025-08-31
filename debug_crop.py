#!/usr/bin/env python3
from pathlib import Path
import pypdfium2 as pdfium
from docling.document_converter import DocumentConverter

pdf_path = Path("input/AMPLE2.pdf")
pdf = pdfium.PdfDocument(str(pdf_path))

print(f"PDF pages: {len(pdf)}")
page = pdf[0]
w_pt, h_pt = page.get_size()
print(f"Page 0 size: {w_pt} x {h_pt} points")

# Get docling output
converter = DocumentConverter()
result = converter.convert(str(pdf_path))
dl_doc = result.model_dump()

doc = dl_doc.get("document", {})
pictures = doc.get("pictures", [])

if pictures:
    pic = pictures[0]
    if isinstance(pic.get("prov"), list) and pic["prov"]:
        prov = pic["prov"][0]
        bbox_data = prov.get("bbox", {})
        
        print(f"\nFirst picture bbox:")
        print(f"  l={bbox_data.get('l')}, t={bbox_data.get('t')}")
        print(f"  r={bbox_data.get('r')}, b={bbox_data.get('b')}")
        print(f"  origin: {bbox_data.get('coord_origin')}")
        
        # Try conversion
        bbox = [bbox_data.get("l"), bbox_data.get("t"), 
               bbox_data.get("r"), bbox_data.get("b")]
        
        print(f"\nChecking for None values: {None in bbox}")
        print(f"Bbox list: {bbox}")
        
        # Check coordinate validity
        if None not in bbox:
            l, t, r, b = bbox
            print(f"\nCoordinate check:")
            print(f"  Width: {r - l}")
            print(f"  Height: {abs(b - t)}")
            print(f"  Valid box: {r > l and abs(b - t) > 0}")