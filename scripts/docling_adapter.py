# scripts/docling_adapter.py
from pathlib import Path
from typing import Dict, Any, List, Optional
import base64
from io import BytesIO
from PIL import Image

from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions


def convert_pdf(pdf_path: Path) -> Dict[str, Any]:
    """
    Converts PDF to normalized structure using Docling >= 2.48.
    
    Returns a uniform dict structure:
      {
        "texts": List[{"page": int, "bbox": [x0,y0,x1,y1], "text": str}],
        "figures": List[{"page": int, "bbox": [...], "image_path": str, "caption": str}],
        "tables":  List[{"page": int, "bbox": [...], "cells": [...], "caption": str}],
        "sections": List[{"title": str, "paragraphs": [str]}]
      }
    """
    # Configure Docling to generate images
    pdf_options = PdfFormatOption(
        pipeline_options=PdfPipelineOptions(
            generate_picture_images=True,
            generate_table_images=True,
            do_ocr=False  # We'll do OCR separately if needed
        )
    )
    
    converter = DocumentConverter(format_options={'pdf': pdf_options})
    result = converter.convert(str(pdf_path))
    
    # Get the raw docling output
    docling_data = result.model_dump()
    doc = docling_data.get("document", {})
    
    out = {"texts": [], "figures": [], "tables": [], "sections": []}
    
    # Extract sections from assembled body
    if "assembled" in docling_data:
        body = docling_data["assembled"].get("body", [])
        current_section = {"title": "", "paragraphs": []}
        
        for elem in body:
            label = elem.get("label", "")
            text = elem.get("text", "")
            
            if label == "section_header":
                # Save previous section if it has content
                if current_section["paragraphs"]:
                    out["sections"].append(current_section)
                current_section = {"title": text, "paragraphs": []}
            elif label in ["text", "list_item", "paragraph"]:
                if text.strip():
                    current_section["paragraphs"].append(text)
                    # Also add to texts with page info if available
                    page_no = elem.get("page_no", 0)
                    bbox = None
                    if "cluster" in elem and "bbox" in elem["cluster"]:
                        bbox_data = elem["cluster"]["bbox"]
                        bbox = [bbox_data.get("l"), bbox_data.get("t"), 
                               bbox_data.get("r"), bbox_data.get("b")]
                    out["texts"].append({
                        "page": page_no,
                        "bbox": bbox,
                        "text": text
                    })
        
        # Don't forget the last section
        if current_section["paragraphs"]:
            out["sections"].append(current_section)
    
    # Fallback if no sections found: create one from all texts
    if not out["sections"] and out["texts"]:
        out["sections"].append({
            "title": "",
            "paragraphs": [t["text"] for t in out["texts"]]
        })
    
    # Extract figures with captions
    media_dir = pdf_path.parent / "docling_media" / pdf_path.stem
    media_dir.mkdir(parents=True, exist_ok=True)
    
    pictures = doc.get("pictures", [])
    
    # Try to associate captions from assembled body
    figure_captions = _extract_figure_captions(docling_data)
    
    for i, pic in enumerate(pictures):
        page_no = 0
        bbox = None
        
        # Extract page and bbox from prov
        if isinstance(pic.get("prov"), list) and pic["prov"]:
            prov_item = pic["prov"][0]
            page_no = prov_item.get("page_no", 1) - 1  # Convert to 0-based
            bbox_data = prov_item.get("bbox", {})
            if bbox_data:
                bbox = [bbox_data.get("l"), bbox_data.get("t"),
                       bbox_data.get("r"), bbox_data.get("b")]
        
        # Get caption - first from our extraction, then from pic data
        caption = ""
        if i < len(figure_captions):
            caption = figure_captions[i]
        elif pic.get("caption_text"):
            caption = pic["caption_text"]
        elif isinstance(pic.get("captions"), list) and pic["captions"]:
            first_caption = pic["captions"][0]
            if isinstance(first_caption, dict):
                caption = first_caption.get("text", "")
            elif isinstance(first_caption, str):
                caption = first_caption
        
        # Save image if available
        img_path = None
        if pic.get("image"):
            img_ref = pic["image"]
            if hasattr(img_ref, "uri") and str(img_ref.uri).startswith("data:"):
                # Extract base64 image data
                try:
                    data_url = str(img_ref.uri)
                    header, encoded = data_url.split(",", 1)
                    img_data = base64.b64decode(encoded)
                    img = Image.open(BytesIO(img_data))
                    img_path = media_dir / f"page{page_no+1}_fig{i+1:03d}.png"
                    img.save(str(img_path))
                except Exception as e:
                    print(f"Failed to save figure {i}: {e}")
        
        out["figures"].append({
            "page": page_no,
            "bbox": bbox,
            "image_path": str(img_path) if img_path else None,
            "caption": caption
        })
    
    # Extract tables with captions
    tables = doc.get("tables", [])
    table_captions = _extract_table_captions(docling_data)
    
    for i, table in enumerate(tables):
        page_no = 0
        bbox = None
        
        # Extract page and bbox from prov
        if isinstance(table.get("prov"), list) and table["prov"]:
            prov_item = table["prov"][0]
            page_no = prov_item.get("page_no", 1) - 1  # Convert to 0-based
            bbox_data = prov_item.get("bbox", {})
            if bbox_data:
                bbox = [bbox_data.get("l"), bbox_data.get("t"),
                       bbox_data.get("r"), bbox_data.get("b")]
        
        # Get caption
        caption = ""
        if i < len(table_captions):
            caption = table_captions[i]
        elif table.get("caption_text"):
            caption = table["caption_text"]
        
        # Extract table data
        table_data = table.get("data", [])
        
        out["tables"].append({
            "page": page_no,
            "bbox": bbox,
            "cells": table_data,
            "caption": caption
        })
    
    return out


def _extract_figure_captions(docling_data: Dict) -> List[str]:
    """Extract figure captions from assembled body."""
    captions = []
    if "assembled" in docling_data:
        body = docling_data["assembled"].get("body", [])
        for i in range(len(body) - 1):
            elem = body[i]
            next_elem = body[i + 1]
            if elem.get("label") == "picture":
                if next_elem.get("label") == "caption":
                    captions.append(next_elem.get("text", ""))
                else:
                    captions.append("")
    return captions


def _extract_table_captions(docling_data: Dict) -> List[str]:
    """Extract table captions from assembled body."""
    captions = []
    if "assembled" in docling_data:
        body = docling_data["assembled"].get("body", [])
        for i in range(len(body) - 1):
            elem = body[i]
            next_elem = body[i + 1]
            if elem.get("label") == "table":
                if next_elem.get("label") == "caption":
                    captions.append(next_elem.get("text", ""))
                else:
                    captions.append("")
    return captions