import re
from typing import Dict, Any, List

RE_TABLE_HDR = re.compile(r'^\s*Table\s+(\d+)\s*[:.]\s*(.+)', re.I)
RE_FIG_HDR   = re.compile(r'^\s*Figure\s+(\d+)\s*[:.]\s*(.+)', re.I)
RE_FOOTNOTE  = re.compile(r'^\s*([*†‡])\s+')

def _collect_caption(lines: List[str], start_idx: int) -> tuple[str, int]:
    """Collect contiguous caption lines until blank or footnote marker."""
    buf = []
    i = start_idx
    while i < len(lines):
        line = lines[i].rstrip()
        if not line or RE_FOOTNOTE.match(line):
            break
        buf.append(line)
        i += 1
    return (" ".join(buf).strip(), i)

def attach_captions(pages: List[Dict[str, Any]], assets: Dict[str, Any]) -> None:
    """
    pages: list of { 'page_number': int, 'lines': [str, ...] }  # text lines in order
    assets: dict with 'tables' and 'figures', each item may have 'page' and will receive 'caption'/'footnote'
    """
    # Build per-page captions registry from text
    per_page_caps = {"table": {}, "figure": {}}
    for p in pages:
        lines = p.get("lines", [])
        i = 0
        while i < len(lines):
            line = lines[i]
            m_t = RE_TABLE_HDR.match(line)
            m_f = RE_FIG_HDR.match(line)
            if m_t:
                num = m_t.group(1)
                cap, j = _collect_caption(lines, i)
                per_page_caps["table"].setdefault(p["page_number"], {})[num] = {"caption": cap}
                # collect footnote if any immediately after caption block
                if j < len(lines) and RE_FOOTNOTE.match(lines[j]):
                    per_page_caps["table"][p["page_number"]][num]["footnote"] = lines[j].strip()
                i = j + 1
                continue
            if m_f:
                num = m_f.group(1)
                cap, j = _collect_caption(lines, i)
                per_page_caps["figure"].setdefault(p["page_number"], {})[num] = {"caption": cap}
                if j < len(lines) and RE_FOOTNOTE.match(lines[j]):
                    per_page_caps["figure"][p["page_number"]][num]["footnote"] = lines[j].strip()
                i = j + 1
                continue
            i += 1

    # Attach to assets by matching on page + ordinal number if available
    for kind in ("tables", "figures"):
        for item in assets.get(kind, []):
            page = item.get("page")
            num  = str(item.get("number") or item.get("ordinal") or "")
            if not page or not num:
                continue
            bank = per_page_caps["table" if kind=="tables" else "figure"].get(page, {})
            if num in bank:
                item["caption"] = bank[num].get("caption")
                if "footnote" in bank[num]:
                    item["footnote"] = bank[num]["footnote"]