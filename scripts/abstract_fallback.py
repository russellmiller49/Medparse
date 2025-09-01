"""
Extract abstract from document structure when not available in metadata.
Scans first 2 pages for "Abstract" section and captures until Introduction/Keywords.
"""
import re
from typing import Dict, Any, Optional

def extract_abstract(doc: Dict[str, Any]) -> Optional[str]:
    """
    Extract abstract from document structure.
    
    Looks for Abstract section in first 2 pages and captures text
    until hitting Introduction, Keywords, or similar section.
    
    Args:
        doc: Document dictionary with structure.sections
        
    Returns:
        Abstract text if found, None otherwise
    """
    structure = doc.get("structure", {})
    sections = structure.get("sections", [])
    
    if not sections:
        return None
    
    abstract_text = []
    found_abstract = False
    
    # Common abstract section titles
    abstract_patterns = [
        r'^abstract\s*$',
        r'^summary\s*$',
        r'^synopsis\s*$',
        r'^overview\s*$'
    ]
    
    # Stop when we hit these sections
    stop_patterns = [
        r'^introduction',
        r'^keywords',
        r'^key\s*words',
        r'^background',
        r'^methods',
        r'^materials',
        r'^1\.\s*introduction',
        r'^i\.\s*introduction'
    ]
    
    for section in sections:
        title = section.get("title", "").strip().lower()
        
        # Check if this is the abstract section
        if not found_abstract:
            for pattern in abstract_patterns:
                if re.match(pattern, title):
                    found_abstract = True
                    break
            
            # Also check if abstract is in the first untitled section
            if not found_abstract and not title:
                # Check first paragraph for "Abstract" label
                paragraphs = section.get("paragraphs", [])
                if paragraphs:
                    first_text = ""
                    if isinstance(paragraphs[0], dict):
                        first_text = paragraphs[0].get("text", "")
                    else:
                        first_text = str(paragraphs[0])
                    
                    if re.match(r'^abstract\b', first_text.lower()):
                        found_abstract = True
                        # Skip the "Abstract" label itself
                        if len(paragraphs) > 1:
                            paragraphs = paragraphs[1:]
        
        # If we found abstract, collect text
        if found_abstract:
            # Check if we should stop
            should_stop = False
            for pattern in stop_patterns:
                if re.match(pattern, title):
                    should_stop = True
                    break
            
            if should_stop and abstract_text:
                # We've collected abstract and hit next section
                break
            
            # Collect paragraphs
            if not should_stop or not abstract_text:
                paragraphs = section.get("paragraphs", [])
                for para in paragraphs:
                    if isinstance(para, dict):
                        text = para.get("text", "").strip()
                    else:
                        text = str(para).strip()
                    
                    if text:
                        # Skip if this looks like a keyword line
                        if re.match(r'^keywords?\s*:', text.lower()):
                            break
                        abstract_text.append(text)
                
                # Only check first 2-3 sections after finding abstract
                if len(abstract_text) > 0 and title:
                    # If we have a titled section after abstract, might be done
                    if not any(re.match(p, title) for p in abstract_patterns):
                        break
    
    # Alternative: Look for abstract in metadata-like first section
    if not abstract_text and sections:
        # Check first section for abstract-like content
        first_section = sections[0]
        paragraphs = first_section.get("paragraphs", [])
        
        in_abstract = False
        for para in paragraphs[:20]:  # Check first 20 paragraphs
            if isinstance(para, dict):
                text = para.get("text", "").strip()
            else:
                text = str(para).strip()
            
            # Look for Abstract: or ABSTRACT: prefix
            if re.match(r'^abstract\s*:\s*', text.lower()):
                in_abstract = True
                # Remove the prefix
                text = re.sub(r'^abstract\s*:\s*', '', text, flags=re.IGNORECASE).strip()
                if text:
                    abstract_text.append(text)
            elif in_abstract:
                # Stop at keywords or next section
                if re.match(r'^(keywords?|introduction|background|methods)\s*:', text.lower()):
                    break
                if text:
                    abstract_text.append(text)
    
    if abstract_text:
        # Join paragraphs with space
        full_abstract = " ".join(abstract_text)
        
        # Clean up common artifacts
        full_abstract = re.sub(r'\s+', ' ', full_abstract)  # Normalize whitespace
        full_abstract = re.sub(r'^\W+|\W+$', '', full_abstract)  # Trim punctuation
        
        # Ensure reasonable length (not too short, not entire paper)
        if 50 < len(full_abstract) < 5000:
            return full_abstract
    
    return None

def extract_abstract_from_raw_text(text: str) -> Optional[str]:
    """
    Fallback: Extract abstract from raw text using patterns.
    
    Args:
        text: Raw document text
        
    Returns:
        Abstract if found
    """
    # Look for abstract section
    abstract_match = re.search(
        r'(?:^|\n)\s*(?:ABSTRACT|Abstract|Summary)\s*[\n:]\s*(.+?)(?=\n\s*(?:Keywords?|KEYWORDS?|Introduction|INTRODUCTION|Background|BACKGROUND|1\.\s*Introduction))',
        text,
        re.DOTALL | re.MULTILINE
    )
    
    if abstract_match:
        abstract = abstract_match.group(1).strip()
        # Clean up
        abstract = re.sub(r'\s+', ' ', abstract)
        abstract = re.sub(r'^\W+|\W+$', '', abstract)
        
        if 50 < len(abstract) < 5000:
            return abstract
    
    return None