#!/usr/bin/env python3
"""
Prepare hardened JSONs for RAG system ingestion by creating cleaner, focused documents.

This script transforms the complex nested JSON structure into a cleaner format
optimized for RAG systems, with options for different chunking strategies.
"""

import json
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional, Iterable
import re
from itertools import chain


DOI_RE = re.compile(r"^10\.\S+$")


def create_citation_string(metadata: Dict[str, Any]) -> str:
    """Generate a formatted citation string from metadata."""
    authors = metadata.get('authors', [])
    if authors:
        # Handle both string and dict authors
        if isinstance(authors[0], str):
            # Authors are already strings
            if len(authors) > 3:
                author_str = f"{authors[0]}, et al."
            else:
                author_str = "; ".join(authors)
        else:
            # Authors are dicts
            if len(authors) > 3 and (authors[0].get('family') or authors[0].get('display')):
                first = authors[0]
                first_fam = first.get('family') or first.get('display') or "Unknown"
                author_str = f"{first_fam}, et al."
            else:
                author_names: List[str] = []
                for a in authors:
                    fam = (a.get('family') or "").strip()
                    giv = (a.get('given') or "").strip()
                    initial = (giv[0] + ".") if giv else ""
                    if fam or initial:
                        author_names.append(f"{fam}, {initial}".strip().strip(","))
                author_str = "; ".join(n for n in author_names if n) or "Unknown"
    else:
        author_str = "Unknown"
    
    year = metadata.get('year', 'n.d.')
    title = metadata.get('title', 'Untitled')
    journal = metadata.get('journal', metadata.get('journal_full', ''))
    volume = metadata.get('volume', '')
    issue = metadata.get('issue', '')
    pages = metadata.get('pages', '')
    doi = metadata.get('doi', '')
    
    # Build citation
    citation = f"{author_str} ({year}). {title}."
    if journal:
        citation += f" {journal}"
        if volume:
            citation += f", {volume}"
            if issue:
                citation += f"({issue})"
        if pages:
            citation += f", {pages}"
    if doi:
        citation += f". https://doi.org/{doi}"
    
    return citation


def _safe_id(raw: Optional[str], fallback: str) -> str:
    """
    Sanitize a document id (prefer DOI if present) so it is filesystem/DB safe.
    """
    base = (raw or fallback).strip()
    # Replace non-alphanumerics with underscores, collapse repeats, lowercase.
    safe = re.sub(r"[^A-Za-z0-9]+", "_", base).strip("_").lower()
    return safe or re.sub(r"[^A-Za-z0-9]+", "_", fallback).strip("_").lower()


def _join_paragraphs(paragraphs: Any) -> str:
    """
    Robustly join paragraphs that may be:
      - list[str]
      - list[dict{ 'text': str, ...}]
      - str
      - None
    """
    if paragraphs is None:
        return ""
    if isinstance(paragraphs, str):
        return paragraphs.strip()
    out: List[str] = []
    for p in paragraphs:
        if isinstance(p, dict):
            t = p.get("text") or p.get("content") or ""
        else:
            t = str(p)
        t = t.strip()
        if t:
            out.append(t)
    return "\n".join(out)


def _collect_references(meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Merge references from any available field without losing information."""
    # Priority 1: enriched (already structured)
    if meta.get('references_enriched'):
        return meta['references_enriched']

    # Priority 2: structured (title/journal/year/doi style)
    if meta.get('references_struct'):
        return meta['references_struct']

    # Priority 3: text blobs -> minimal dicts
    refs = []
    for raw in meta.get('references_text', []):
        # Very light extraction heuristic; keeps the raw string too
        refs.append({'raw': raw})
    return refs


def _dedupe_references(refs: Iterable[Any]) -> List[Dict[str, Any]]:
    """
    Deduplicate and lightly validate references. Prefer entries with plausible DOIs.
    Handle both dict and string references.
    """
    seen: set = set()
    cleaned: List[Dict[str, Any]] = []
    for r in refs:
        if isinstance(r, str):
            # Convert string ref to minimal dict
            r = {"title": r, "year": "", "doi": ""}
        elif not isinstance(r, dict):
            continue
            
        title = (r.get("title") or "").strip().lower()
        year = str(r.get("year") or "").strip()
        doi = (r.get("doi") or "").strip()
        key = (title, year, doi)
        if key in seen:
            continue
        seen.add(key)
        if doi and not DOI_RE.match(doi):
            # Drop clearly malformed DOIs
            r = {**r, "doi": ""}
        cleaned.append(r)
    return cleaned


def clean_for_rag(input_file: Path, mode: str = "full") -> Dict[str, Any]:
    """
    Clean and restructure JSON for RAG ingestion.
    
    Modes:
    - full: Include everything but reorganize
    - article: Focus on article content, minimal references
    - abstract: Just metadata and abstract for initial retrieval
    """
    
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    metadata = data.get('metadata', {})
    structure = data.get('structure', {})
    
    # Create clean metadata
    # Handle authors that may be strings or dicts
    authors_clean = []
    for a in metadata.get('authors', []):
        if isinstance(a, dict):
            authors_clean.append(a.get('display', '') or f"{a.get('given', '')} {a.get('family', '')}".strip())
        elif isinstance(a, str):
            authors_clean.append(a)
    
    clean_meta = {
        'document_id': _safe_id(metadata.get('doi'), input_file.stem),
        'title': metadata.get('title', ''),
        'authors': authors_clean,
        'year': metadata.get('year'),
        'journal': metadata.get('journal', metadata.get('journal_full', '')),
        'doi': metadata.get('doi', ''),
        'volume': metadata.get('volume', ''),
        'issue': metadata.get('issue', ''),
        'pages': metadata.get('pages', ''),
        'citation': create_citation_string(metadata),
        'abstract': metadata.get('abstract', ''),
        'url': metadata.get('url', f"https://doi.org/{metadata.get('doi', '')}" if metadata.get('doi') else '')
    }
    
    # Clean output structure
    output = {
        'metadata': clean_meta,
        'source_file': input_file.name
    }
    
    if mode == "abstract":
        # Minimal version for initial retrieval
        return output
    
    # Add content sections (preserve full text)
    sections = []
    for section in structure.get('sections', []):
        # prefer explicit paragraphs; otherwise fall back to a 'content' or 'text' field
        paras = section.get('paragraphs') or []
        content = _join_paragraphs(paras) if paras else section.get('content') or section.get('text') or ''
        if not content:
            continue
        
        sec_obj = {
            'title': section.get('title', ''),
            'content': content,
            'category': section.get('category', ''),
            'level': section.get('level'),          # keep hierarchy if present
            'page_start': section.get('page_start'),
            'page_end': section.get('page_end'),
            'section_id': section.get('id') or section.get('anchor'),
        }
        # If page numbers exist inside paragraph objects, collect them
        try:
            pages = sorted({int(p.get('page')) for p in (section.get('paragraphs') or []) if isinstance(p, dict) and p.get('page') is not None})
            if pages:
                sec_obj['pages'] = pages
        except Exception:
            pass
        sections.append(sec_obj)
    output['sections'] = sections
    
    # Add tables (preserve data)
    if structure.get('tables'):
        output['tables'] = []
        for t in structure['tables']:
            # Handle captions that may be strings or objects
            captions = t.get('captions', [])
            if captions:
                caption_text = []
                for c in captions:
                    if isinstance(c, dict):
                        caption_text.append(c.get('text', '') or c.get('content', '') or str(c))
                    else:
                        caption_text.append(str(c))
                caption = ' '.join(caption_text)
            else:
                caption = t.get('caption', '')
            
            output['tables'].append({
                'id': t.get('id') or t.get('label'),
                'caption': caption,
                'headers': t.get('headers') or t.get('columns'),
                'rows': t.get('data'),
                'footnotes': t.get('notes') or t.get('footnotes'),
                'page': t.get('page'),
            })
    
    # Add figures
    if structure.get('figures'):
        output['figures'] = []
        for fig in structure['figures']:
            # Handle captions that may be strings, dicts, or lists
            caption = ''
            if fig.get('caption'):
                caption = fig['caption'] if isinstance(fig['caption'], str) else str(fig['caption'])
            elif fig.get('captions'):
                captions = fig.get('captions', [])
                caption_parts = []
                for c in captions:
                    if isinstance(c, str):
                        caption_parts.append(c)
                    elif isinstance(c, dict):
                        caption_parts.append(c.get('text', '') or c.get('content', '') or str(c))
                    else:
                        caption_parts.append(str(c))
                caption = ' '.join(caption_parts)
            
            output['figures'].append({
                'id': fig.get('id') or fig.get('label'),
                'caption': caption,
                'page': fig.get('page'),
            })
    
    # Add key extracted entities
    if data.get('drugs'):
        drugs_clean = []
        for d in data.get('drugs', []):
            if isinstance(d, dict):
                drugs_clean.append(d.get('name', ''))
            elif isinstance(d, str):
                drugs_clean.append(d)
        output['extracted_drugs'] = list(set(filter(None, drugs_clean)))
    
    if data.get('trial_ids'):
        trials_clean = []
        for t in data.get('trial_ids', []):
            if isinstance(t, dict):
                trials_clean.append(t.get('id', ''))
            elif isinstance(t, str):
                trials_clean.append(t)
        output['clinical_trials'] = list(set(filter(None, trials_clean)))
    
    # References: use fallback chain to preserve all references
    refs_raw = _collect_references(metadata)
    refs_clean = _dedupe_references(refs_raw)

    if mode == "article":
        # Include counts and a short list of plausible DOIs
        output['num_references'] = len(refs_clean)
        output['reference_dois'] = [r.get('doi') for r in refs_clean if r.get('doi')][:10]
    elif mode == "full":
        # Include full references (deduped and lightly validated)
        output['references'] = refs_clean
    
    # Add quality indicators (improved)
    validation = data.get('validation', {})
    output['quality'] = {
        'completeness_score': validation.get('completeness_score', 0),
        'has_abstract': bool(clean_meta.get('abstract')),
        'has_doi': bool(clean_meta.get('doi')),
        'has_full_text': bool(output.get('sections')),
        'num_sections': len(output.get('sections', [])),
        'num_tables': len(output.get('tables', [])),
        'num_figures': len(output.get('figures', [])),
        'num_references': len(output.get('references', [])) if 'references' in output else len(refs_clean)
    }
    
    return output


def _sent_split(text: str) -> List[str]:
    """Lightweight sentence splitter; replace with spaCy if you prefer"""
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]


def create_sentence_window_chunks(clean_data: Dict[str, Any], window: int = 2) -> List[Dict[str, Any]]:
    """Create sentence-window chunks for better RAG performance."""
    chunks = []
    base_meta = clean_data['metadata'].copy()
    base_meta['source_file'] = clean_data.get('source_file')

    # Abstract as its own retrieval unit
    if base_meta.get('abstract'):
        chunks.append({
            'chunk_id': f"{base_meta['document_id']}::abstract",
            'type': 'abstract',
            'content': base_meta['abstract'],
            'context_window': base_meta['abstract'],
            'metadata': base_meta
        })

    for i, section in enumerate(clean_data.get('sections', [])):
        sents = _sent_split(section.get('content', ''))
        for j, sent in enumerate(sents):
            lo = max(0, j - window)
            hi = min(len(sents), j + window + 1)
            ctx = ' '.join(sents[lo:hi])

            meta = dict(base_meta)
            meta.update({
                'section_title': section.get('title'),
                'section_category': section.get('category'),
                'section_level': section.get('level'),
                'page_start': section.get('page_start'),
                'page_end': section.get('page_end')
            })

            chunks.append({
                'chunk_id': f"{base_meta['document_id']}::sec{i}::sent{j}",
                'type': 'sentence',
                'section_title': section.get('title'),
                'content': sent,
                'context_window': ctx,
                'metadata': meta
            })

    # Optional: Table rows as chunks (preserve numeric signals)
    for t in clean_data.get('tables', []):
        rows = t.get('rows') or []
        for r_idx, row in enumerate(rows):
            row_text = ' | '.join(str(c) for c in row) if isinstance(row, (list, tuple)) else str(row)
            meta = dict(base_meta)
            meta.update({
                'table_id': t.get('id'),
                'table_caption': t.get('caption'),
                'page': t.get('page'),
            })
            chunks.append({
                'chunk_id': f"{base_meta['document_id']}::table::{t.get('id','idx')}::row{r_idx}",
                'type': 'table_row',
                'section_title': None,
                'content': row_text,
                'context_window': f"{t.get('caption','')} || {row_text}",
                'metadata': meta
            })

    return chunks


def create_chunks(clean_data: Dict[str, Any], chunk_size: int = 1000) -> List[Dict[str, Any]]:
    """
    Create overlapping chunks for RAG ingestion.
    Each chunk includes metadata for context.
    """
    chunks = []
    base_meta = clean_data['metadata'].copy()
    doc_id = base_meta['document_id']
    overlap_words = 100
    step = max(chunk_size - overlap_words, max(1, chunk_size // 2))
    
    # Abstract as first chunk
    if base_meta.get('abstract'):
        chunks.append({
            'chunk_id': f"{doc_id}_abstract",
            'type': 'abstract',
            'content': base_meta['abstract'],
            'metadata': base_meta
        })
    
    # Section chunks
    for i, section in enumerate(clean_data.get('sections', [])):
        content = section.get('content', '')
        if len(content) > chunk_size:
            # Split large sections
            words = content.split()
            for j in range(0, len(words), step):
                chunk_words = words[j:j + chunk_size]
                if not chunk_words:
                    continue
                chunk_content = ' '.join(chunk_words)
                chunk_idx = j // step
                chunks.append({
                    'chunk_id': f"{doc_id}_sec{i}_chunk{chunk_idx}",
                    'type': 'section',
                    'section_title': section.get('title', ''),
                    'section_category': section.get('category', ''),
                    'content': chunk_content,
                    'metadata': base_meta
                })
        else:
            chunks.append({
                'chunk_id': f"{doc_id}_sec{i}",
                'type': 'section', 
                'section_title': section.get('title', ''),
                'section_category': section.get('category', ''),
                'content': content,
                'metadata': base_meta
            })
    
    return chunks


def main():
    parser = argparse.ArgumentParser(description='Prepare hardened JSONs for RAG ingestion')
    parser.add_argument('input', help='Input directory with hardened JSONs')
    parser.add_argument('output', help='Output directory for cleaned JSONs')
    parser.add_argument('--mode', choices=['full', 'article', 'abstract'], 
                       default='article', help='Cleaning mode')
    parser.add_argument('--chunk', action='store_true', 
                       help='Create chunked output for vector databases')
    parser.add_argument('--chunk-size', type=int, default=1000, 
                       help='Chunk size in words (default: 1000)')
    
    args = parser.parse_args()
    
    input_dir = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Process all JSON files
    json_files = list(input_dir.glob('*.json'))
    print(f"Processing {len(json_files)} files in {args.mode} mode...")
    
    for json_file in json_files:
        if json_file.name == 'processing_report.json':
            continue
            
        try:
            clean_data = clean_for_rag(json_file, mode=args.mode)
            
            if args.chunk:
                # Use sentence-window chunking
                chunks = create_sentence_window_chunks(clean_data, window=2)
                output_file = output_dir / f"{json_file.stem}_chunks.json"
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(chunks, f, indent=2, ensure_ascii=False)
                print(f"  {json_file.name} -> {len(chunks)} chunks (sentence-window)")
            else:
                # Single document output
                output_file = output_dir / json_file.name
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(clean_data, f, indent=2, ensure_ascii=False)
                print(f"  {json_file.name} -> cleaned")
                
        except Exception as e:
            print(f"  Error processing {json_file.name}: {e}")
    
    print(f"\nOutput written to {output_dir}")
    print("\nUsage examples:")
    print("  - For vector DB: Use --chunk mode to create overlapping chunks")
    print("  - For document store: Use --mode=article for focused content")
    print("  - For metadata index: Use --mode=abstract for quick retrieval")


if __name__ == '__main__':
    main()