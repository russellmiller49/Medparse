"""
Front-matter author extractor and enrichment helpers.
"""
import re
from difflib import SequenceMatcher
from typing import List, Dict, Any, Optional

from loguru import logger

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
        def _has_name(a) -> bool:
            if isinstance(a, str):
                return bool(a.strip())
            if isinstance(a, dict):
                disp = a.get('display') or a.get('full_name')
                return bool(disp or (a.get('given') and a.get('family')))
            return False
        if existing and any(_has_name(a) for a in existing):
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


def enrich_authors_with_affiliations(
    meta: Dict[str, Any],
    docling_json: Dict[str, Any],
    merged_doc: Dict[str, Any] | None = None,
) -> None:
    """Populate author affiliation mappings using Docling and merged document cues."""
    if not isinstance(meta, dict) or not isinstance(docling_json, dict):
        return

    authors = meta.get("authors")
    if not isinstance(authors, list) or not authors:
        return

    body = docling_json.get("assembled", {}).get("body", [])
    if not isinstance(body, list) or not body:
        return

    # Build map from affiliation index to text
    aff_map: Dict[int, str] = {}

    capture_affs = False
    for elem in body:
        text = (elem.get("text") or "").strip()
        if not text:
            continue
        lower = text.lower()
        if lower == "institutions":
            capture_affs = True
            continue
        if capture_affs:
            label = elem.get("label")
            if label == "section_header" and lower != "institutions":
                if aff_map:
                    break
                capture_affs = False
                continue
            if label == "key_value_region" and not text:
                # Text often stored in children for key_value regions
                for child in elem.get("children", []) or []:
                    child_text = (child.get("text") or "").strip()
                    if not child_text:
                        continue
                    _maybe_store_affiliation(child_text, aff_map)
                continue
            _maybe_store_affiliation(text, aff_map)

    if isinstance(merged_doc, dict):
        sections = merged_doc.get("structure", {}).get("sections", []) or []
        for sec in sections:
            title = (sec.get("title") or "").strip().lower()
            if not title:
                continue
            if "institution" not in title and "acknowledg" not in title:
                continue
            for para in sec.get("paragraphs", []) or []:
                text = (para.get("text") or "").strip()
                if not text:
                    continue
                _maybe_store_affiliation(text, aff_map)

    if not aff_map:
        logger.info("No affiliation map constructed for document")
        return
    logger.info("Affiliation entries detected: {}", len(aff_map))

    # Locate the primary author list (between "Authors" and "Institutions")
    author_chunks: List[str] = []
    capture = False
    for elem in body:
        text = (elem.get("text") or "").strip()
        if not text:
            continue
        lower = text.lower()
        if not capture and lower == "authors":
            capture = True
            continue
        if capture:
            if lower.startswith("institutions"):
                break
            author_chunks.append(text)

    if not author_chunks:
        return

    author_blob = " ".join(author_chunks)
    pattern = re.compile(r"([A-Z][^0-9,]+?)\s*(\d+(?:,\d+)*)")
    doc_entries = []
    for match in pattern.finditer(author_blob):
        raw_name = match.group(1).strip().strip(',;')
        nums = match.group(2)
        if not raw_name or not nums:
            continue
        numbers: List[int] = []
        for part in nums.split(','):
            try:
                num = int(part)
            except ValueError:
                continue
            if num not in numbers:
                numbers.append(num)
        if not numbers:
            continue
        tokens = [tok for tok in raw_name.replace('\xa0', ' ').split() if tok]
        key_full = _normalize_key(raw_name)
        key_first_last = _normalize_key("{} {}".format(tokens[0], tokens[-1])) if len(tokens) >= 2 else key_full
        key_last = _normalize_key(tokens[-1]) if tokens else ""
        doc_entries.append({
            "raw": raw_name,
            "numbers": numbers,
            "keys": {k for k in (key_full, key_first_last, key_last) if k}
        })

    if not doc_entries:
        logger.debug("No author-number entries extracted from front matter")
        return

    def _candidate_keys(author: Dict[str, Any]) -> List[str]:
        keys: List[str] = []
        display = author.get("full_name") or author.get("display")
        if display:
            keys.append(_normalize_key(display))
            parts = [tok for tok in display.split() if tok]
            if len(parts) >= 2:
                keys.append(_normalize_key(f"{parts[0]} {parts[-1]}"))
        given = author.get("given")
        family = author.get("family")
        if given and family:
            keys.append(_normalize_key(f"{given} {family}"))
            keys.append(_normalize_key(f"{given.split()[0]} {family}"))
        if family:
            keys.append(_normalize_key(family))
        return [k for k in keys if k]

    def _apply_numbers(author: Dict[str, Any], numbers: List[int]) -> None:
        if not numbers:
            return
        author["affiliation_ids"] = numbers
        derived_affs = []
        for num in numbers:
            text = aff_map.get(num)
            if not text:
                continue
            derived_affs.append({"text": text})
        if not derived_affs:
            return
        existing_affs: List[Dict[str, Any]] = []
        if isinstance(author.get("affiliations"), list):
            for item in author["affiliations"]:
                if isinstance(item, dict):
                    existing_affs.append(dict(item))
        existing_texts = {(item.get("text") or "").strip().lower() for item in existing_affs if isinstance(item, dict)}

        def _covers(existing_item: Dict[str, Any], text_lower: str) -> bool:
            orgs = existing_item.get("organizations") or []
            existing_text = (existing_item.get("text") or "").strip().lower()
            if existing_text and existing_text == text_lower:
                return True
            if orgs:
                return all(org.lower() in text_lower for org in orgs if org)
            return False

        for aff in derived_affs:
            text_lower = aff["text"].strip().lower()
            if text_lower in existing_texts:
                continue
            if any(_covers(item, text_lower) for item in existing_affs if isinstance(item, dict)):
                continue
            existing_affs.append(aff)
            existing_texts.add(text_lower)
        if existing_affs:
            author["affiliations"] = existing_affs

    def _keys_match(entry_keys: set[str], candidate_keys: List[str]) -> bool:
        for cand in candidate_keys:
            for key in entry_keys:
                if cand == key:
                    return True
                if cand and key and SequenceMatcher(None, cand, key).ratio() >= 0.9:
                    return True
        return False

    unmatched: List[Dict[str, Any]] = []
    assigned: set[int] = set()

    def _entry_id(entry: Dict[str, Any]) -> int:
        return id(entry)

    for author in authors:
        if not isinstance(author, dict):
            continue
        keys = _candidate_keys(author)
        if not keys:
            unmatched.append(author)
            continue
        entry = next((e for e in doc_entries if _entry_id(e) not in assigned and _keys_match(e["keys"], keys)), None)
        if not entry:
            unmatched.append(author)
            continue
        assigned.add(_entry_id(entry))
        _apply_numbers(author, entry["numbers"])

    def _best_entry(author: Dict[str, Any]) -> Dict[str, Any] | None:
        keys = _candidate_keys(author)
        best: Dict[str, Any] | None = None
        best_score = 0.0
        for entry in doc_entries:
            entry_id = _entry_id(entry)
            if entry_id in assigned:
                continue
            score = _max_ratio(keys, entry["keys"])
            if score > best_score:
                best = entry
                best_score = score
        if best and best_score >= 0.82:
            assigned.add(_entry_id(best))
            return best
        return None

    still_unmatched: List[Dict[str, Any]] = []
    for author in unmatched:
        entry = _best_entry(author)
        if entry is None:
            still_unmatched.append(author)
            continue
        _apply_numbers(author, entry["numbers"])

    if len(doc_entries) == len(authors):
        for idx, author in enumerate(authors):
            if not isinstance(author, dict):
                continue
            if author.get("affiliation_ids"):
                continue
            numbers = doc_entries[idx]["numbers"]
            if numbers:
                _apply_numbers(author, numbers)

    for author in still_unmatched:
        name = author.get("display") or author.get("full_name")
        logger.info(
            "No affiliation mapping found for author {}",
            name,
        )

    logger.info(
        "Author affiliation coverage: {}",
        [
            {
                "name": author.get("display") or author.get("full_name"),
                "has_affiliation": bool(author.get("affiliations")),
            }
            for author in authors
            if isinstance(author, dict)
        ],
    )

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

    # Drop trailing punctuation and stray delimiters
    name = name.strip().rstrip(',;:')

    return name

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
def _normalize_key(name: str) -> str:
    if not name:
        return ""
    return re.sub(r'[^a-z0-9]+', '', name.lower())


def _max_ratio(candidate_keys: List[str], entry_keys: set[str]) -> float:
    best = 0.0
    if not candidate_keys or not entry_keys:
        return best
    for cand in candidate_keys:
        for key in entry_keys:
            if not cand or not key:
                continue
            if cand == key:
                return 1.0
            score = SequenceMatcher(None, cand, key).ratio()
            if score > best:
                best = score
    return best
BULLET_PATTERN = re.compile(r"^[●•]\s*")


def _maybe_store_affiliation(text: str, aff_map: Dict[int, str]) -> None:
    if not text:
        return
    text = BULLET_PATTERN.sub("", text).strip()
    match = re.match(r"^(\d{1,2})\s+(.*)$", text)
    if not match:
        return
    try:
        idx = int(match.group(1))
    except ValueError:
        return
    value = match.group(2).strip()
    if not value:
        return
    aff_map.setdefault(idx, value)
