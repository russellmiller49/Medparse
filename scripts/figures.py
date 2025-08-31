# scripts/figures.py
"""Figure processing with OCR textuality scoring and EXIF embedding."""

from pathlib import Path
from typing import Dict, Any, List, Optional
from PIL import Image
import piexif
import re

# Optional OCR support
try:
    import pytesseract
    HAS_OCR = True
except ImportError:
    HAS_OCR = False
    print("Warning: pytesseract not installed. OCR textuality scoring disabled.")


def image_has_text(img_path: Path, min_chars: int = 20) -> bool:
    """
    Check if an image contains significant text using OCR.
    
    Args:
        img_path: Path to image file
        min_chars: Minimum characters to consider image as textual
        
    Returns:
        True if image contains significant text
    """
    if not HAS_OCR:
        return False
    
    try:
        img = Image.open(img_path)
        # Convert to RGB if necessary
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Run OCR
        text = pytesseract.image_to_string(img)
        
        # Count non-whitespace characters
        char_count = len("".join(text.split()))
        
        return char_count >= min_chars
    except Exception as e:
        print(f"OCR error for {img_path}: {e}")
        return False


def get_image_text(img_path: Path) -> str:
    """
    Extract text from image using OCR.
    
    Args:
        img_path: Path to image file
        
    Returns:
        Extracted text or empty string
    """
    if not HAS_OCR:
        return ""
    
    try:
        img = Image.open(img_path)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        text = pytesseract.image_to_string(img)
        # Clean up whitespace
        text = " ".join(text.split())
        return text
    except Exception:
        return ""


def embed_caption_exif(img_path: Path, caption: str) -> None:
    """
    Embed caption in image EXIF metadata.
    
    Args:
        img_path: Path to image file
        caption: Caption text to embed
    """
    if not caption:
        return
    
    try:
        img = Image.open(img_path)
        
        # Get existing EXIF data or create new
        try:
            exif_dict = piexif.load(img.info.get("exif", b""))
        except:
            exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}}
        
        # Add caption to ImageDescription field (tag 270)
        # Truncate if too long
        caption_bytes = caption[:512].encode("utf-8", "ignore")
        exif_dict["0th"][piexif.ImageIFD.ImageDescription] = caption_bytes
        
        # Also add software tag
        exif_dict["0th"][piexif.ImageIFD.Software] = b"medparse-docling"
        
        # Convert back to bytes
        exif_bytes = piexif.dump(exif_dict)
        
        # Save with EXIF
        img.save(img_path, exif=exif_bytes)
        
    except Exception as e:
        print(f"Failed to embed EXIF in {img_path}: {e}")


def extract_figure_label(caption: str) -> Optional[str]:
    """
    Extract figure label from caption text.
    
    Args:
        caption: Caption text
        
    Returns:
        Figure label (e.g., "Figure 1", "Fig. 2A") or None
    """
    if not caption:
        return None
    
    # Patterns to match figure labels
    patterns = [
        r'^(Figure\s+\d+[A-Za-z]?)',  # Figure 1, Figure 1A
        r'^(Fig\.?\s+\d+[A-Za-z]?)',   # Fig. 1, Fig 1
        r'^(FIG\.?\s+\d+[A-Za-z]?)',   # FIG. 1
        r'^(Supplementary\s+Figure\s+\d+[A-Za-z]?)',  # Supplementary Figure 1
        r'^(Supp\.?\s+Fig\.?\s+\d+[A-Za-z]?)',  # Supp. Fig. 1
    ]
    
    for pattern in patterns:
        match = re.search(pattern, caption, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return None


def prepare_figures(
    figures: List[Dict[str, Any]], 
    out_dir: Path,
    base_name: Optional[str] = None,
    extract_text: bool = True
) -> List[Dict[str, Any]]:
    """
    Process figures: save images, extract text, embed captions.
    
    Args:
        figures: List of figure dicts from docling_adapter
        out_dir: Output directory for figure images
        base_name: Base name for output files
        extract_text: Whether to extract text using OCR
        
    Returns:
        List of processed figures with metadata
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    prepared = []
    
    for i, fig in enumerate(figures, 1):
        # Skip if no image path
        img_path = fig.get("image_path")
        if not img_path or not Path(img_path).exists():
            continue
        
        # Get caption
        caption = fig.get("caption", "").strip()
        
        # Extract figure label
        label = extract_figure_label(caption)
        
        # Determine output filename
        if label and base_name:
            # Normalize label for filename
            safe_label = re.sub(r'[^A-Za-z0-9]+', '_', label.lower())
            out_name = f"{base_name}_{safe_label}.jpg"
        elif base_name:
            out_name = f"{base_name}_fig{i:03d}.jpg"
        else:
            out_name = f"fig{i:03d}.jpg"
        
        # Copy/convert image to output directory
        out_path = out_dir / out_name
        
        try:
            img = Image.open(img_path)
            # Convert to RGB for JPEG
            if img.mode != 'RGB':
                img = img.convert('RGB')
            img.save(out_path, format="JPEG", quality=95)
        except Exception as e:
            print(f"Failed to save figure {i}: {e}")
            continue
        
        # Embed caption in EXIF
        if caption:
            embed_caption_exif(out_path, caption)
        
        # Check if image contains text
        textual = False
        ocr_text = ""
        if extract_text:
            textual = image_has_text(out_path)
            if textual:
                ocr_text = get_image_text(out_path)
        
        # Build figure metadata
        prepared_fig = {
            "index": i,
            "page": fig.get("page"),
            "bbox": fig.get("bbox"),
            "image_path": str(out_path),
            "original_path": img_path,
            "caption": caption,
            "label": label,
            "textual": textual,
            "ocr_text": ocr_text if textual else None
        }
        
        prepared.append(prepared_fig)
    
    return prepared


def is_likely_watermark(
    bbox: List[float], 
    page: int, 
    page_width: float, 
    page_height: float
) -> bool:
    """
    Check if a figure is likely a publisher watermark.
    
    Args:
        bbox: Bounding box [x0, y0, x1, y1]
        page: Page number (0-indexed)
        page_width: Page width in points
        page_height: Page height in points
        
    Returns:
        True if likely a watermark
    """
    # Watermarks are typically on first page
    if page != 0:
        return False
    
    if not bbox or len(bbox) < 4:
        return False
    
    x0, y0, x1, y1 = bbox[:4]
    width = abs(x1 - x0)
    height = abs(y1 - y0)
    
    # Check if very small
    if width < 100 and height < 50:
        # Check if at top or bottom of page
        if y0 < 100 or y1 > (page_height - 100):
            return True
    
    return False


def filter_watermarks(
    figures: List[Dict[str, Any]], 
    page_dims: Optional[Dict[int, tuple]] = None
) -> List[Dict[str, Any]]:
    """
    Filter out likely publisher watermarks from figures.
    
    Args:
        figures: List of figure dicts
        page_dims: Dict mapping page index to (width, height) in points
        
    Returns:
        Filtered list without watermarks
    """
    if not page_dims:
        # Can't filter without page dimensions
        return figures
    
    filtered = []
    
    for fig in figures:
        page = fig.get("page", 0)
        bbox = fig.get("bbox")
        
        if page in page_dims:
            width, height = page_dims[page]
            if is_likely_watermark(bbox, page, width, height):
                print(f"Filtering likely watermark on page {page + 1}")
                continue
        
        filtered.append(fig)
    
    return filtered