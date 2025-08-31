#!/usr/bin/env python3
from pathlib import Path
from docling.document_converter import DocumentConverter
import json

pdf = Path("input/AMPLE2.pdf")
if not pdf.exists():
    print(f"PDF not found: {pdf}")
    exit(1)

print(f"Processing: {pdf}")
converter = DocumentConverter()
result = converter.convert(str(pdf))
dl_doc = result.model_dump()

# Check document.pictures structure
doc = dl_doc.get("document", {})
pictures = doc.get("pictures", [])

print(f"\nFound {len(pictures)} pictures")
if pictures:
    print(f"\nFirst picture type: {type(pictures[0])}")
    if isinstance(pictures[0], list):
        print(f"First picture is a list with {len(pictures[0])} items")
        if pictures[0]:
            print(f"First item in list: {type(pictures[0][0])}")
            if isinstance(pictures[0][0], dict):
                print(f"Keys: {list(pictures[0][0].keys())[:10]}")
                print(f"Sample: {json.dumps(pictures[0][0], indent=2, default=str)[:500]}")
    elif isinstance(pictures[0], dict):
        print(f"First picture keys: {list(pictures[0].keys())[:10]}")
        print(f"Sample: {json.dumps(pictures[0], indent=2, default=str)[:500]}")