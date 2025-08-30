from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Tuple
import math, piexif
from PIL import Image
import pypdfium2 as pdfium

def _ensure_dir(p: Path) -> None: p.mkdir(parents=True, exist_ok=True)
def _is_norm(b: List[float]) -> bool: return all(0.0 <= v <= 1.0 for v in b)
def _clip(v, lo, hi): return max(lo, min(hi, v))

def _bbox_to_pixels(b, w_pt, h_pt, scale):
    x0,y0,x1,y1 = b
    if _is_norm(b): x0*=w_pt; x1*=w_pt; y0*=h_pt; y1*=h_pt
    pad=6; x0-=pad; y0-=pad; x1+=pad; y1+=pad
    x0=_clip(x0,0,w_pt); x1=_clip(x1,0,w_pt); y0=_clip(y0,0,h_pt); y1=_clip(y1,0,h_pt)
    left=int(math.floor(x0*scale)); right=int(math.ceil(x1*scale))
    top=int(math.floor((h_pt-y1)*scale)); bottom=int(math.ceil((h_pt-y0)*scale))
    return left,top,right,bottom

def _exif_bytes(caption: str, page: int, fig_id: str) -> bytes:
    zeroth = {
        piexif.ImageIFD.ImageDescription: caption.encode("utf-8","ignore"),
        piexif.ImageIFD.Artist: b"Docling Pipeline",
        piexif.ImageIFD.Software: b"medparse-figure-cropper",
        piexif.ImageIFD.ImageUniqueID: f"page{page}_fig{fig_id}".encode("utf-8"),
        piexif.ImageIFD.XPTitle: f"Figure: {fig_id}".encode("utf-16le"),
    }
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
    
    saved=0; missing=0
    for i, fig in enumerate(figs, start=1):
        # Get bounding box and page info
        bbox = fig.get("prov", {}).get("bbox") or fig.get("bbox") or fig.get("box")
        page_idx = fig.get("prov", {}).get("page") or fig.get("page") or fig.get("page_index")
        
        if bbox is None or page_idx is None:
            missing += 1; continue
            
        pi = int(page_idx)
        # accept both 0-based and 1-based page indices
        if pi >= len(pdf) and (pi-1) >= 0 and (pi-1) < len(pdf):
            pi = pi - 1
        
        page = pdf[pi]; w_pt, h_pt = page.get_size()
        pil = page.render(scale=scale).to_pil()
        left,top,right,bottom = _bbox_to_pixels(bbox, w_pt, h_pt, scale)
        left=_clip(left,0,pil.width); right=_clip(right,0,pil.width); top=_clip(top,0,pil.height); bottom=_clip(bottom,0,pil.height)
        
        if right-left<8 or bottom-top<8: missing+=1; continue
        
        crop = pil.crop((left,top,right,bottom))
        cap = fig.get("caption", {}).get("text", "") if isinstance(fig.get("caption"), dict) else (fig.get("caption") or fig.get("title") or "")
        out_path = out_dir / f"{base}_fig_{i:03d}.jpg"
        exif = _exif_bytes(cap, int(pi)+1, str(i))
        crop.save(out_path, format="JPEG", quality=95, subsampling=0, exif=exif)
        saved+=1
    
    return {"n_saved": saved, "n_missing_bbox": missing}