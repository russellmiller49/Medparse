#\!/usr/bin/env python3
import math

def _clip(v, lo, hi): 
    return max(lo, min(hi, v))

def test_bbox_transform():
    # Test case from AMPLE2.pdf
    bbox = [483.951416015625, 680.9680480957031, 560.5543823242188, 654.4055633544922]
    w_pt = 595.2760009765625
    h_pt = 799.3699951171875
    scale = 220/72.0  # dpi/72
    coord_origin = "BOTTOMLEFT"
    
    x0, y0, x1, y1 = bbox
    pad = 6
    
    print(f"Original bbox: {bbox}")
    print(f"Page size: {w_pt} x {h_pt}")
    print(f"Coordinate origin: {coord_origin}")
    
    # Add padding
    x0 -= pad
    y0 -= pad  
    x1 += pad
    y1 += pad
    
    # Clip to page bounds
    x0 = _clip(x0, 0, w_pt)
    x1 = _clip(x1, 0, w_pt)
    y0 = _clip(y0, 0, h_pt)
    y1 = _clip(y1, 0, h_pt)
    
    print(f"\nAfter padding and clipping:")
    print(f"x0={x0}, y0={y0}, x1={x1}, y1={y1}")
    
    # Convert to pixels
    left = int(math.floor(x0 * scale))
    right = int(math.ceil(x1 * scale))
    
    if coord_origin == "BOTTOMLEFT":
        # In BOTTOMLEFT: y0 is bottom, y1 is top (y1 > y0)
        # We need to convert to image coordinates where top < bottom
        # Image coordinates: (0,0) is top-left
        # So: top = page_height - y1, bottom = page_height - y0
        top = int(math.floor((h_pt - y1) * scale))
        bottom = int(math.ceil((h_pt - y0) * scale))
        print(f"\nBOTTOMLEFT conversion:")
        print(f"  y0 (bottom in PDF) = {y0} -> bottom in image = {bottom}")
        print(f"  y1 (top in PDF) = {y1} -> top in image = {top}")
    else:  # TOPLEFT
        top = int(math.floor(y0 * scale))
        bottom = int(math.ceil(y1 * scale))
    
    print(f"\nFinal pixel coordinates:")
    print(f"left={left}, top={top}, right={right}, bottom={bottom}")
    print(f"Width: {right - left}, Height: {bottom - top}")
    print(f"Valid crop: {right > left and bottom > top}")

test_bbox_transform()
