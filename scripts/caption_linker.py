"""
Robust caption and footnote linker for tables and figures.
Handles supplementary numbering, multi-page layouts, and footnotes.
"""
import re
from typing import Dict, List, Any, Optional, Tuple

def link_captions(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Link captions and footnotes to tables and figures in the document.
    
    Updates doc['assets'] with 'captions' and 'footnotes' lists for each item.
    """
    # Ensure assets structure exists
    if 'assets' not in doc:
        doc['assets'] = {}
    
    # Merge tables and figures into assets
    assets = doc['assets']
    
    # Process tables
    if 'structure' in doc and 'tables' in doc['structure']:
        if 'tables' not in assets:
            assets['tables'] = []
        
        for table in doc['structure']['tables']:
            asset_table = {
                'type': 'table',
                'content': table,
                'captions': [],
                'footnotes': []
            }
            
            # Extract existing caption if present
            if 'caption' in table:
                asset_table['captions'].append(table['caption'])
            
            # Look for caption in nearby text
            caption = find_caption_for_asset(doc, table, 'table')
            if caption and caption not in asset_table['captions']:
                asset_table['captions'].append(caption)
            
            # Look for footnotes
            footnotes = find_footnotes_for_asset(doc, table)
            asset_table['footnotes'].extend(footnotes)
            
            assets['tables'].append(asset_table)
    
    # Process figures
    if 'structure' in doc and 'figures' in doc['structure']:
        if 'figures' not in assets:
            assets['figures'] = []
        
        for figure in doc['structure']['figures']:
            asset_figure = {
                'type': 'figure',
                'content': figure,
                'captions': [],
                'footnotes': []
            }
            
            # Extract existing caption if present
            if 'caption' in figure:
                asset_figure['captions'].append(figure['caption'])
            
            # Look for caption in nearby text
            caption = find_caption_for_asset(doc, figure, 'figure')
            if caption and caption not in asset_figure['captions']:
                asset_figure['captions'].append(caption)
            
            # Look for footnotes
            footnotes = find_footnotes_for_asset(doc, figure)
            asset_figure['footnotes'].extend(footnotes)
            
            assets['figures'].append(asset_figure)
    
    return doc

def find_caption_for_asset(doc: Dict[str, Any], asset: Dict[str, Any], asset_type: str) -> Optional[str]:
    """
    Find caption for a table or figure using proximity and pattern matching.
    """
    # Caption patterns
    if asset_type == 'table':
        patterns = [
            r'Table\s+([A-Z0-9]+(?:\.[0-9]+)?)[:\.]?\s*(.+?)(?:\n|$)',
            r'TABLE\s+([A-Z0-9]+(?:\.[0-9]+)?)[:\.]?\s*(.+?)(?:\n|$)',
            r'Supplementary\s+Table\s+([A-Z0-9]+)[:\.]?\s*(.+?)(?:\n|$)'
        ]
    else:  # figure
        patterns = [
            r'Figure\s+([A-Z0-9]+(?:\.[0-9]+)?)[:\.]?\s*(.+?)(?:\n|$)',
            r'FIGURE\s+([A-Z0-9]+(?:\.[0-9]+)?)[:\.]?\s*(.+?)(?:\n|$)',
            r'Fig\.\s+([A-Z0-9]+(?:\.[0-9]+)?)[:\.]?\s*(.+?)(?:\n|$)',
            r'Supplementary\s+Figure\s+([A-Z0-9]+)[:\.]?\s*(.+?)(?:\n|$)'
        ]
    
    # Get page number and position if available
    page_num = asset.get('page', asset.get('page_number'))
    bbox = asset.get('bbox', asset.get('bounding_box'))
    
    # Search for captions in the document text
    if 'structure' in doc and 'sections' in doc['structure']:
        for section in doc['structure']['sections']:
            if 'paragraphs' in section:
                for para in section['paragraphs']:
                    text = para.get('text', '')
                    for pattern in patterns:
                        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
                        if match:
                            # Check if this might be the right caption
                            # (could add more sophisticated matching based on number)
                            caption_text = match.group(2).strip()
                            if caption_text:
                                return caption_text
    
    # Also check raw text if available
    if 'text' in doc:
        for pattern in patterns:
            matches = re.finditer(pattern, doc['text'], re.IGNORECASE | re.MULTILINE)
            for match in matches:
                caption_text = match.group(2).strip()
                if caption_text:
                    return caption_text
    
    return None

def find_footnotes_for_asset(doc: Dict[str, Any], asset: Dict[str, Any]) -> List[str]:
    """
    Find footnotes associated with a table or figure.
    """
    footnotes = []
    
    # Common footnote patterns
    footnote_patterns = [
        r'^\*+\s*(.+?)(?:\n|$)',  # Asterisk footnotes
        r'^†+\s*(.+?)(?:\n|$)',   # Dagger footnotes
        r'^‡+\s*(.+?)(?:\n|$)',   # Double dagger
        r'^[a-z]\s*(.+?)(?:\n|$)', # Letter footnotes
        r'^Note:\s*(.+?)(?:\n|$)', # Note footnotes
        r'^Abbreviations:\s*(.+?)(?:\n|$)'  # Abbreviations
    ]
    
    # Get page number if available
    page_num = asset.get('page', asset.get('page_number'))
    
    # Search for footnotes near the asset
    if 'structure' in doc and 'sections' in doc['structure']:
        for section in doc['structure']['sections']:
            if 'paragraphs' in section:
                for para in section['paragraphs']:
                    text = para.get('text', '')
                    # Check if this paragraph might be on the same or next page
                    para_page = para.get('page', para.get('page_number'))
                    if para_page and page_num and abs(para_page - page_num) > 1:
                        continue
                    
                    for pattern in footnote_patterns:
                        match = re.search(pattern, text, re.MULTILINE)
                        if match:
                            footnote_text = match.group(1).strip()
                            if footnote_text and len(footnote_text) > 10:  # Avoid tiny matches
                                footnotes.append(footnote_text)
    
    return footnotes

def classify_asset_type(asset: Dict[str, Any]) -> str:
    """
    Classify whether an asset is truly a table or might be a figure/flowchart.
    """
    # Check for flowchart indicators
    flowchart_indicators = [
        '→', '←', '↓', '↑', '⟶', '⟵',
        'Yes', 'No', 'If', 'Then', 'Start', 'End',
        'Decision', 'Process', 'Flow'
    ]
    
    content_str = str(asset.get('content', ''))
    
    # Count flowchart indicators
    indicator_count = sum(1 for indicator in flowchart_indicators if indicator in content_str)
    
    # Check table structure
    rows = asset.get('rows', [])
    cols = asset.get('columns', [])
    
    # If very few rows/cols and has flowchart indicators, likely a figure
    if len(rows) < 2 or len(cols) < 2:
        if indicator_count >= 2:
            return 'figure'
    
    # If has many flowchart indicators relative to size
    if indicator_count > len(rows) + len(cols):
        return 'figure'
    
    # Default to original type
    return asset.get('type', 'table')