"""
Front-matter author extractor with support for various formats and edge cases.
"""
import re
from typing import List, Dict, Any, Optional

def extract_authors_from_frontmatter(doc: Dict[str, Any]) -> List[str]:
    """
    Extract authors from document front matter when metadata.authors is empty.
    
    Handles various formats:
    - Comma-separated lists
    - Line-by-line authors
    - Authors with affiliations (superscript markers)
    - Name suffixes (Jr., III, MD, PhD)
    """
    # First check if authors already exist in metadata
    if 'metadata' in doc and 'authors' in doc['metadata']:
        existing = doc['metadata']['authors']
        if existing and any(a.strip() for a in existing if isinstance(a, str)):
            return existing
    
    authors = []
    
    # Look for authors in the first sections of the document
    if 'structure' in doc and 'sections' in doc['structure']:
        # Check first few sections (usually contains author info)
        for i, section in enumerate(doc['structure']['sections'][:3]):
            # Skip if section title suggests it's not author info
            title = section.get('title', '').lower()
            if any(skip in title for skip in ['abstract', 'introduction', 'methods', 'results']):
                continue
            
            if 'paragraphs' in section:
                for para in section['paragraphs']:
                    text = para.get('text', '')
                    extracted = extract_authors_from_text(text)
                    if extracted:
                        authors.extend(extracted)
                        if len(authors) >= 2:  # Reasonable number found
                            break
            
            if authors:
                break
    
    # Also check raw text at beginning of document
    if not authors and 'text' in doc:
        # Check first 2000 characters
        front_text = doc['text'][:2000]
        authors = extract_authors_from_text(front_text)
    
    # Clean and deduplicate
    cleaned_authors = []
    seen = set()
    for author in authors:
        author = clean_author_name(author)
        if author and author.lower() not in seen:
            cleaned_authors.append(author)
            seen.add(author.lower())
    
    return cleaned_authors

def extract_authors_from_text(text: str) -> List[str]:
    """
    Extract author names from text using various patterns.
    """
    authors = []
    
    # Pattern 1: Names with superscript markers (common in papers)
    # e.g., "John Smith1,2, Jane Doe2,3"
    pattern1 = r'([A-Z][a-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][a-z]+)+)(?:\d+[,\d]*)?(?:,|\s+and\s+|\s*$)'
    
    # Pattern 2: Standard name format
    # e.g., "John A. Smith" or "John Smith"
    pattern2 = r'([A-Z][a-z]+(?:\s+[A-Z]\.?)*\s+[A-Z][a-z]+(?:\s+(?:Jr\.|Sr\.|III|IV|MD|PhD|PhD))?)'
    
    # Pattern 3: Names in a line (often after "Authors:" or similar)
    if 'author' in text.lower()[:100]:
        # Look for text after "Authors:" or similar
        author_match = re.search(r'Authors?:?\s*(.+?)(?:\n|\.|Abstract|Introduction|$)', text, re.IGNORECASE)
        if author_match:
            author_text = author_match.group(1)
            # Split by common delimiters
            potential_authors = re.split(r'[,;]|\s+and\s+', author_text)
            for name in potential_authors:
                name = clean_author_name(name)
                if is_valid_author_name(name):
                    authors.append(name)
    
    # Try pattern matching if no authors found yet
    if not authors:
        # Look for pattern1 style names
        matches = re.finditer(pattern1, text[:1000])  # Check first 1000 chars
        for match in matches:
            name = match.group(1)
            if is_valid_author_name(name):
                authors.append(name)
        
        # If still no authors, try pattern2
        if not authors:
            matches = re.finditer(pattern2, text[:1000])
            for match in matches:
                name = match.group(1)
                if is_valid_author_name(name):
                    authors.append(name)
    
    return authors

def clean_author_name(name: str) -> str:
    """
    Clean author name by removing affiliations, numbers, and extra whitespace.
    """
    if not name:
        return ""
    
    # Remove superscript numbers and markers
    name = re.sub(r'[\d†‡§¶*]+', '', name)
    
    # Remove email addresses
    name = re.sub(r'\S+@\S+', '', name)
    
    # Remove institutional affiliations in parentheses
    name = re.sub(r'\([^)]+\)', '', name)
    
    # Remove common noise words if they're alone
    noise = ['and', 'et', 'al', 'corresponding', 'author', 'authors']
    words = name.split()
    words = [w for w in words if w.lower() not in noise or len(words) > 2]
    name = ' '.join(words)
    
    # Clean up whitespace
    name = ' '.join(name.split())
    
    return name.strip()

def is_valid_author_name(name: str) -> bool:
    """
    Check if a string is likely to be a valid author name.
    """
    if not name or len(name) < 3:
        return False
    
    # Must have at least one space (first and last name)
    if ' ' not in name:
        return False
    
    # Must start with capital letter
    if not name[0].isupper():
        return False
    
    # Should not be too long
    if len(name) > 50:
        return False
    
    # Should not contain certain keywords that indicate it's not a name
    non_name_keywords = [
        'university', 'hospital', 'institute', 'department', 'college',
        'abstract', 'introduction', 'keywords', 'correspondence',
        'received', 'accepted', 'published', 'doi', 'copyright'
    ]
    name_lower = name.lower()
    if any(keyword in name_lower for keyword in non_name_keywords):
        return False
    
    # Must contain mostly letters
    letter_ratio = sum(1 for c in name if c.isalpha()) / len(name)
    if letter_ratio < 0.7:
        return False
    
    return True