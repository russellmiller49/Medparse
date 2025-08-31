from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import math, piexif, re
from PIL import Image
import pypdfium2 as pdfium

def _ensure_dir(p: Path) -> None: p.mkdir(parents=True, exist_ok=True)
def _is_norm(b: List[float]) -> bool: return all(0.0 <= v <= 1.0 for v in b)
def _clip(v, lo, hi): return max(lo, min(hi, v))

def _extract_figure_label(caption: str) -> Optional[str]:
    """Extract figure label like 'Figure 1' or 'Fig. 2' from caption text."""
    if not caption:
        return None
    
    # Look for patterns like "Figure 1", "Fig. 1", "Figure 1:", "Fig 1."
    patterns = [
        r'^(Figure\s+\d+[A-Za-z]?)',  # Figure 1, Figure 1A
        r'^(Fig\.?\s+\d+[A-Za-z]?)',   # Fig. 1, Fig 1, Fig. 1A
        r'^(FIG\.?\s+\d+[A-Za-z]?)',   # FIG. 1, FIG 1
    ]
    
    for pattern in patterns:
        match = re.search(pattern, caption, re.IGNORECASE)
        if match:
            label = match.group(1)
            # Normalize: "Figure 1", "Fig. 1" -> "fig1"
            label = re.sub(r'[^0-9A-Za-z]+', '', label.lower())
            return label
    
    return None

def _is_likely_watermark(bbox: List[float], page_idx: int, w_pt: float, h_pt: float, coord_origin: str = "TOPLEFT") -> bool:
    """Check if a figure is likely a publisher watermark."""
    # Watermarks are typically:
    # 1. On the first page (page_idx == 0)
    # 2. Very small (< 80pt width AND < 30pt height)
    # 3. At the top of the page
    
    if page_idx != 0:
        return False
    
    x0, y0, x1, y1 = bbox[:4]
    width = abs(x1 - x0)
    height = abs(y1 - y0)
    
    # Check if very small (both width AND height must be small)
    if width < 80 and height < 30:
        # Check position based on coordinate system
        if coord_origin == "BOTTOMLEFT":
            # In BOTTOMLEFT, y increases upward
            # Top of page is high y value
            distance_from_top = h_pt - max(y0, y1)
            if distance_from_top < 150:  # Within 150pt of top
                return True
        else:  # TOPLEFT
            # In TOPLEFT, y increases downward
            # Top of page is low y value
            if min(y0, y1) < 150:  # Within 150pt of top
                return True
    
    return False

def _bbox_to_pixels(b, w_pt, h_pt, scale, coord_origin="TOPLEFT"):
    # b is expected to be [left, top, right, bottom]
    left, top, right, bottom = b
    
    # Handle normalized coordinates
    if _is_norm(b): 
        left *= w_pt
        right *= w_pt
        top *= h_pt
        bottom *= h_pt
    
    # Add padding
    pad = 6
    left -= pad
    right += pad
    
    # Padding for top/bottom depends on coordinate system
    if coord_origin == "BOTTOMLEFT":
        # In BOTTOMLEFT, top > bottom, so expand upward and downward
        top += pad  # Expand upward (increase y)
        bottom -= pad  # Expand downward (decrease y)
    else:
        # In TOPLEFT, bottom > top, so expand normally
        top -= pad  # Expand upward (decrease y)
        bottom += pad  # Expand downward (increase y)
    
    # Clip to page bounds  
    left = _clip(left, 0, w_pt)
    right = _clip(right, 0, w_pt)
    top = _clip(top, 0, h_pt)
    bottom = _clip(bottom, 0, h_pt)
    
    # Convert to pixels
    left_px = int(math.floor(left * scale))
    right_px = int(math.ceil(right * scale))
    
    # Handle different coordinate origins
    if coord_origin == "BOTTOMLEFT":
        # In BOTTOMLEFT: y increases upward from bottom
        # top > bottom in PDF coordinates
        # Convert to image coordinates where (0,0) is top-left
        top_px = int(math.floor((h_pt - top) * scale))
        bottom_px = int(math.ceil((h_pt - bottom) * scale))
    else:  # TOPLEFT
        # In TOPLEFT: y increases downward from top
        # bottom > top in PDF coordinates
        top_px = int(math.floor(top * scale))
        bottom_px = int(math.ceil(bottom * scale))
    
    return left_px, top_px, right_px, bottom_px

def _exif_bytes(caption: str, page: int, fig_id: str) -> bytes:
    zeroth = {
        piexif.ImageIFD.ImageDescription: caption.encode("utf-8","ignore"),
        piexif.ImageIFD.Artist: b"Docling Pipeline",
        piexif.ImageIFD.Software: b"medparse-figure-cropper",
    }
    # Add Windows-specific tags if available
    try:
        zeroth[piexif.ImageIFD.XPTitle] = f"Figure: {fig_id}".encode("utf-16le")
    except:
        pass
    return piexif.dump({"0th": zeroth})

def crop_figures(pdf_path: Path, docling_json: Dict[str, Any], out_dir: Path, dpi: int = 220) -> Dict[str, Any]:
    _ensure_dir(out_dir)
    base = pdf_path.stem
    pdf = pdfium.PdfDocument(str(pdf_path))
    scale = dpi/72.0
    
    # Handle new docling 2.48.0 structure
    figs = []
    if "document" in docling_json:
        figs = docling_json["document"].get("pictures", [])
    if not figs:
        # Fallback to old structure
        figs = (docling_json.get("figures", []) or 
                docling_json.get("structure", {}).get("figures", []))
    
    # Pre-extract captions from assembled body
    figure_captions = []
    if "assembled" in docling_json:
        body = docling_json["assembled"].get("body", [])
        for i in range(len(body) - 1):
            elem = body[i]
            next_elem = body[i + 1]
            if elem.get("label") == "picture" and next_elem.get("label") == "caption":
                figure_captions.append(next_elem.get("text", ""))
            elif elem.get("label") == "picture":
                figure_captions.append("")  # No caption for this figure
    
    saved=0; missing=0; skipped_watermarks=0
    print(f"DEBUG: Processing {len(figs)} figures")
    figure_counter = 0  # Track actual figure number (excluding watermarks)
    
    for i, fig in enumerate(figs, start=1):
        # Get bounding box and page info from prov (which is a list in docling 2.48.0)
        bbox = None
        page_idx = None
        
        # Handle prov as a list
        coord_origin = "TOPLEFT"  # Default
        if isinstance(fig.get("prov"), list) and fig["prov"]:
            prov_item = fig["prov"][0]  # Take first provenance item
            bbox_data = prov_item.get("bbox", {})
            if bbox_data:
                # Convert from l,t,r,b format to list format
                bbox = [bbox_data.get("l"), bbox_data.get("t"), 
                       bbox_data.get("r"), bbox_data.get("b")]
                # Get coordinate origin if specified
                coord_origin = str(bbox_data.get("coord_origin", "TOPLEFT")).split(".")[-1]
            page_idx = prov_item.get("page_no")
            if page_idx is not None:
                page_idx = page_idx - 1  # Convert to 0-based index
            print(f"DEBUG: Fig {i}: bbox={bbox[:2] if bbox else None}..., page_idx={page_idx}, origin={coord_origin}")
        # Fallback to old structure
        elif isinstance(fig.get("prov"), dict):
            bbox = fig["prov"].get("bbox")
            page_idx = fig["prov"].get("page")
        else:
            bbox = fig.get("bbox") or fig.get("box")
            page_idx = fig.get("page") or fig.get("page_index")
        
        if bbox is None or page_idx is None or None in bbox:
            print(f"DEBUG: Figure {i} missing bbox or page_idx. bbox={bbox}, page_idx={page_idx}")
            missing += 1
            continue
            
        pi = int(page_idx)
        # Check if page index is valid
        if pi < 0 or pi >= len(pdf):
            missing += 1
            continue
        
        page = pdf[pi]; w_pt, h_pt = page.get_size()
        
        # Check if this is likely a watermark
        if _is_likely_watermark(bbox, pi, w_pt, h_pt, coord_origin):
            print(f"DEBUG: Skipping likely watermark at index {i} on page {pi+1}")
            skipped_watermarks += 1
            continue
        
        figure_counter += 1  # Increment only for real figures
        
        pil = page.render(scale=scale).to_pil()
        left,top,right,bottom = _bbox_to_pixels(bbox, w_pt, h_pt, scale, coord_origin)
        left=_clip(left,0,pil.width); right=_clip(right,0,pil.width); top=_clip(top,0,pil.height); bottom=_clip(bottom,0,pil.height)
        
        if right-left<8 or bottom-top<8: missing+=1; continue
        
        crop = pil.crop((left,top,right,bottom))
        
        # Get caption - first try from pre-extracted captions, then from figure data
        cap = ""
        
        # Try to get caption from pre-extracted list (accounting for skipped watermarks)
        actual_fig_idx = i - 1 - skipped_watermarks
        if actual_fig_idx < len(figure_captions):
            cap = figure_captions[actual_fig_idx]
        
        # If no caption from assembled body, try figure's own caption data
        if not cap:
            if isinstance(fig.get("captions"), list) and fig["captions"]:
                # Extract text from first caption
                first_caption = fig["captions"][0]
                if isinstance(first_caption, dict) and "text" in first_caption:
                    cap = first_caption["text"]
                elif isinstance(first_caption, str):
                    cap = first_caption
            elif isinstance(fig.get("caption"), dict):
                cap = fig["caption"].get("text", "")
            elif isinstance(fig.get("caption"), str):
                cap = fig["caption"]
            else:
                cap = fig.get("title", "")
        
        # Extract figure label from caption
        fig_label = _extract_figure_label(cap)
        if fig_label:
            # Use extracted label (e.g., "fig1", "fig2a")
            out_path = out_dir / f"{base}_{fig_label}.jpg"
        else:
            # Fallback to numbered sequence
            out_path = out_dir / f"{base}_fig{figure_counter:02d}.jpg"
        
        exif = _exif_bytes(cap, int(pi)+1, str(figure_counter))
        crop.save(out_path, format="JPEG", quality=95, subsampling=0, exif=exif)
        saved+=1
    
    print(f"DEBUG: Saved {saved} figures, skipped {skipped_watermarks} watermarks, {missing} missing bbox")
    return {"n_saved": saved, "n_missing_bbox": missing, "n_watermarks_skipped": skipped_watermarks}