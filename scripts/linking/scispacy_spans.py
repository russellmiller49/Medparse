# scripts/linking/scispacy_spans.py
"""ScispaCy-based entity span detection."""

from typing import List, Dict, Optional
import spacy
from spacy.language import Language

# Cache the loaded model
_nlp_cache: Optional[Language] = None


def get_nlp_model(model_name: str = "en_core_sci_lg") -> Language:
    """Load and cache the spaCy model."""
    global _nlp_cache
    if _nlp_cache is None:
        try:
            _nlp_cache = spacy.load(model_name)
            # Disable unnecessary components for speed
            _nlp_cache.disable_pipes(["parser", "lemmatizer"])
        except Exception as e:
            print(f"Failed to load {model_name}, trying en_core_sci_md: {e}")
            try:
                _nlp_cache = spacy.load("en_core_sci_md")
                _nlp_cache.disable_pipes(["parser", "lemmatizer"])
            except Exception as e2:
                print(f"Failed to load en_core_sci_md, trying en_core_sci_sm: {e2}")
                _nlp_cache = spacy.load("en_core_sci_sm")
                _nlp_cache.disable_pipes(["parser", "lemmatizer"])
    return _nlp_cache


def get_spans(text: str, max_length: int = 1000000) -> List[Dict]:
    """
    Use scispaCy to propose entity mention spans.
    
    Args:
        text: Text to analyze
        max_length: Maximum text length to process at once
        
    Returns:
        List of entity spans with text, start, end, and label
    """
    if not text or not text.strip():
        return []
    
    # Handle very long texts by chunking
    if len(text) > max_length:
        spans = []
        for i in range(0, len(text), max_length):
            chunk = text[i:i + max_length]
            chunk_spans = get_spans(chunk, max_length)
            # Adjust spans for chunk offset
            for span in chunk_spans:
                span["start"] += i
                span["end"] += i
            spans.extend(chunk_spans)
        return spans
    
    try:
        nlp = get_nlp_model()
        doc = nlp(text)
    except Exception as e:
        print(f"Error processing text with scispaCy: {e}")
        return []
    
    spans = []
    seen = set()  # Avoid duplicates
    
    for ent in doc.ents:
        # Skip very short or very long entities
        if len(ent.text) < 2 or len(ent.text) > 100:
            continue
        
        # Skip if just numbers or punctuation
        if not any(c.isalpha() for c in ent.text):
            continue
        
        # Create unique key to avoid duplicates
        key = (ent.start_char, ent.end_char)
        if key in seen:
            continue
        seen.add(key)
        
        spans.append({
            "text": ent.text,
            "start": ent.start_char,
            "end": ent.end_char,
            "label": ent.label_
        })
    
    return spans


def get_noun_phrases(text: str) -> List[Dict]:
    """
    Extract noun phrases as additional entity candidates.
    
    Args:
        text: Text to analyze
        
    Returns:
        List of noun phrase spans
    """
    if not text or not text.strip():
        return []
    
    try:
        nlp = get_nlp_model()
        # Enable parser for noun chunks
        if "parser" in nlp.pipe_names:
            nlp.enable_pipe("parser")
        doc = nlp(text)
    except Exception as e:
        print(f"Error extracting noun phrases: {e}")
        return []
    
    phrases = []
    seen = set()
    
    for chunk in doc.noun_chunks:
        # Skip very short or very long phrases
        if len(chunk.text) < 3 or len(chunk.text) > 50:
            continue
        
        # Skip if just determiners or common words
        if chunk.text.lower() in {"the", "a", "an", "this", "that", "these", "those"}:
            continue
        
        key = (chunk.start_char, chunk.end_char)
        if key in seen:
            continue
        seen.add(key)
        
        phrases.append({
            "text": chunk.text,
            "start": chunk.start_char,
            "end": chunk.end_char,
            "label": "NOUN_PHRASE"
        })
    
    # Disable parser again for speed
    if "parser" in nlp.pipe_names:
        nlp.disable_pipes(["parser"])
    
    return phrases