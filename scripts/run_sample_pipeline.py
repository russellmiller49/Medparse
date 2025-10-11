"""Minimal batch runner for structuring PDFs with Medparse extractors."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from docling.document_converter import DocumentConverter
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import PdfFormatOption

from medparse.extractors import infer_doc_type, run_structured_extractors
from medparse.layout.cleaning import sanitize_sections
from medparse.layout.page_map import build_full_text_with_spans


def build_sections(body: List[Dict]) -> List[Dict]:
    sections: List[Dict] = []
    current: Dict[str, object] = {"title": "", "paragraphs": [], "category": None}

    for element in body:
        label = element.get("label")
        text = (element.get("text") or "").strip()
        if label == "section_header":
            if current["paragraphs"]:
                sections.append(current)
            current = {"title": text, "paragraphs": [], "category": None}
        elif label in {"text", "paragraph", "list_item"} and text:
            paragraphs = current.setdefault("paragraphs", [])  # type: ignore[assignment]
            paragraphs.append({"text": text})  # type: ignore[attr-defined]
    if current["paragraphs"]:
        sections.append(current)
    return sections


def process_pdf(converter: DocumentConverter, pdf_path: Path, output_dir: Path, doc_type: str | None = None) -> Path:
    result = converter.convert(str(pdf_path))
    data = result.model_dump()
    body = data.get("assembled", {}).get("body", [])
    sections = build_sections(body)

    structure = {"sections": sections}
    sanitize_sections(structure)
    structure["sections"] = [sec for sec in structure["sections"] if sec.get("paragraphs")]

    full_text, page_map = build_full_text_with_spans(structure["sections"], docling_body=body)

    payload = {
        "doc_id": pdf_path.stem,
        "metadata": {"title": data.get("document", {}).get("name") or pdf_path.stem},
        "structure": structure,
        "full_text": full_text,
        "page_map": page_map,
    }

    doc_type_hint = infer_doc_type(payload, doc_id=pdf_path.stem, explicit=doc_type)
    if doc_type_hint:
        payload["metadata"]["doc_type"] = doc_type_hint

    structured = run_structured_extractors(
        doc_id=pdf_path.stem,
        payload=payload,
        full_text=full_text,
        page_map=page_map,
        doc_type=doc_type_hint,
    )
    if structured:
        payload["doc_specific"] = structured

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{pdf_path.name}.json"
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Medparse structured extraction on PDFs.")
    parser.add_argument("input", type=Path, help="Directory containing PDF files")
    parser.add_argument("--output", type=Path, default=Path("out"), help="Directory for JSON outputs")
    parser.add_argument("--doc-type", type=str, default=None, help="Optional doc type hint (ifu/guideline/article/chapter)")
    args = parser.parse_args()

    if not args.input.is_dir():
        raise SystemExit(f"Input directory not found: {args.input}")

    pdfs = sorted(p for p in args.input.glob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"No PDFs found in {args.input}")

    pdf_options = PdfFormatOption(pipeline_options=PdfPipelineOptions(generate_picture_images=False, generate_table_images=False, do_ocr=False))
    converter = DocumentConverter(format_options={"pdf": pdf_options})

    for pdf in pdfs:
        out_path = process_pdf(converter, pdf, args.output, doc_type=args.doc_type)
        print(f"Saved {out_path}")


if __name__ == "__main__":
    main()
