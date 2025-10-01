"""Utilities to build structured table payloads from Docling output."""
from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_TABLE_LABEL_RE = re.compile(r"^(table\s*\d+[a-z]?)", re.IGNORECASE)


def extract_structured_tables(
    tables: List[Dict[str, Any]],
    asset_tables: Optional[List[Dict[str, Any]]],
    tables_dir: Path,
    pdf_stem: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Return structured table manifests and enriched structure/asset lists."""
    if tables_dir:
        tables_dir.mkdir(parents=True, exist_ok=True)

    asset_tables = asset_tables or []
    table_infos: List[Dict[str, Any]] = []
    enriched_tables: List[Dict[str, Any]] = []
    enriched_assets: List[Dict[str, Any]] = []

    for idx, table in enumerate(tables):
        table_entry = dict(table)
        asset_entry = asset_tables[idx] if idx < len(asset_tables) else None

        caption = _resolve_caption(table_entry, asset_entry)
        table_id = _derive_table_id(caption, idx)
        page = _extract_page(table_entry)
        rows = _build_table_matrix(table_entry)

        csv_path = None
        if rows and tables_dir:
            csv_path = tables_dir / f"{_sanitize_filename(pdf_stem)}_{table_id}.csv"
            _write_csv(rows, csv_path)

        footnotes = []
        if asset_entry:
            footnotes = [ft for ft in asset_entry.get("footnotes", []) if ft]

        table_info = {
            "kind": "table",
            "id": table_id,
            "caption": caption,
            "page": page,
            "rows": rows,
            "footnotes": footnotes,
        }
        if csv_path:
            table_info["csv_path"] = str(csv_path)
        table_infos.append(table_info)

        table_entry["caption"] = caption
        table_entry["page"] = page
        table_entry["cells"] = rows
        table_entry["local_id"] = table_id
        if csv_path:
            table_entry["csv_path"] = str(csv_path)
        enriched_tables.append(table_entry)

        if asset_entry:
            new_asset = dict(asset_entry)
            new_asset["content"] = table_entry
            captions = [cap for cap in asset_entry.get("captions", []) if cap]
            if caption:
                if caption not in captions:
                    captions.insert(0, caption)
            new_asset["captions"] = captions
            new_asset["footnotes"] = footnotes
        else:
            new_asset = {
                "type": "table",
                "content": table_entry,
                "captions": [caption] if caption else [],
                "footnotes": footnotes,
            }
        enriched_assets.append(new_asset)

    return table_infos, enriched_tables, enriched_assets


def _resolve_caption(table: Dict[str, Any], asset_entry: Optional[Dict[str, Any]]) -> Optional[str]:
    if asset_entry:
        captions = [cap for cap in asset_entry.get("captions", []) if cap]
        if captions:
            return captions[0]
    if table.get("caption_text"):
        return table["caption_text"].strip()
    if isinstance(table.get("caption"), dict):
        return (table["caption"].get("text") or "").strip()
    if isinstance(table.get("caption"), str):
        return table["caption"].strip()
    return None


def _derive_table_id(caption: Optional[str], idx: int) -> str:
    if caption:
        match = _TABLE_LABEL_RE.match(caption.strip())
        if match:
            return re.sub(r"[^a-z0-9]+", "", match.group(1).lower())
    return f"table{idx+1:02d}"


def _extract_page(table: Dict[str, Any]) -> Optional[int]:
    prov = table.get("prov")
    if isinstance(prov, list) and prov:
        page_no = prov[0].get("page_no")
        if page_no:
            return int(page_no)
    if isinstance(prov, dict) and prov.get("page"):
        return int(prov["page"])
    return table.get("page")


def _build_table_matrix(table: Dict[str, Any]) -> List[List[Dict[str, Any]]]:
    data = table.get("data", {}) or {}
    cells = data.get("table_cells") or []
    if not cells:
        return []

    max_row = max((cell.get("end_row_offset_idx", 0) for cell in cells), default=0)
    max_col = max((cell.get("end_col_offset_idx", 0) for cell in cells), default=0)
    if max_row == 0 or max_col == 0:
        return []

    matrix: List[List[Dict[str, Any]]] = [[{"text": ""} for _ in range(max_col)] for _ in range(max_row)]

    for cell in cells:
        sr = cell.get("start_row_offset_idx", 0)
        er = cell.get("end_row_offset_idx", sr + 1)
        sc = cell.get("start_col_offset_idx", 0)
        ec = cell.get("end_col_offset_idx", sc + 1)
        text = (cell.get("text") or "").strip()
        row_span = max(1, er - sr)
        col_span = max(1, ec - sc)

        entry = {
            "text": text,
        }
        if row_span > 1:
            entry["row_span"] = row_span
        if col_span > 1:
            entry["col_span"] = col_span
        if cell.get("column_header"):
            entry["header"] = "column"
        if cell.get("row_header"):
            header_val = entry.get("header")
            entry["header"] = "row" if not header_val else header_val

        matrix[sr][sc] = entry

        for rr in range(sr, er):
            for cc in range(sc, ec):
                if rr == sr and cc == sc:
                    continue
                matrix[rr][cc] = {"text": "", "placeholder": True}

    return matrix


def _write_csv(rows: List[List[Dict[str, Any]]], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        for row in rows:
            writer.writerow([cell.get("text", "") for cell in row])


def _sanitize_filename(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", value).strip("_") or "table"


__all__ = ["extract_structured_tables"]
