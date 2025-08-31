# scripts/fig_ocr.py
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)

def ocr_if_textual(image_path: Path, threshold: float = 0.1) -> Optional[str]:
    """
    Run OCR on image if it contains text (not just graphical elements).
    Returns OCR text if textual content detected, None otherwise.
    """
    try:
        import pytesseract
        from PIL import Image
        
        img = Image.open(image_path)
        
        # Quick textuality check using OCR confidence
        ocr_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        
        # Count words with confidence > 30
        confident_words = sum(1 for conf in ocr_data['conf'] if isinstance(conf, int) and conf > 30)
        total_boxes = len([c for c in ocr_data['conf'] if isinstance(c, int)])
        
        if total_boxes == 0:
            return None
            
        textuality_score = confident_words / total_boxes
        
        if textuality_score >= threshold:
            # Extract full text
            text = pytesseract.image_to_string(img).strip()
            if len(text) > 10:  # Minimum text length
                logger.debug(f"OCR extracted {len(text)} chars from {image_path.name}")
                return text
        
        return None
        
    except ImportError:
        logger.warning("pytesseract not installed, skipping OCR")
        return None
    except Exception as e:
        logger.error(f"OCR failed for {image_path}: {e}")
        return None