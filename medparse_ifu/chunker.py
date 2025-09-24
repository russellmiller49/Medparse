"""
RAG-ready chunking for IFU documents.

Creates chunks with:
- Section-aware splitting
- Dense provenance metadata
- Configurable chunk sizes
- Overlap for context preservation
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from medparse_ifu.schema import IFURecord, IFUSection

logger = logging.getLogger(__name__)


@dataclass
class IFUChunk:
    """Represents a single chunk for RAG indexing."""
    doc_id: str
    chunk_id: str
    text: str
    section_key: str
    section_title: str
    chunk_index: int
    total_chunks: int
    
    # Provenance
    source_path: str
    sha256: str
    page_range: List[int]
    
    # Metadata for filtering
    manufacturer: Optional[str]
    trade_name: Optional[str]
    device_family: Optional[str]
    revision_id: Optional[str]
    revision_date: Optional[str]
    
    # Regulatory identifiers
    udi_di: Optional[List[str]]
    catalog_numbers: Optional[List[str]]
    model_numbers: Optional[List[str]]
    product_codes: Optional[List[str]]
    
    # Additional context
    language: str = "en"
    country_scope: Optional[List[str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), default=str)


def estimate_tokens(text: str) -> int:
    """
    Rough estimation of token count.
    
    Args:
        text: Text to estimate
        
    Returns:
        Estimated token count
    """
    # Simple heuristic: ~1 token per 4 characters
    return len(text) // 4


def split_text_by_tokens(
    text: str,
    max_tokens: int = 1000,
    overlap_tokens: int = 100
) -> List[str]:
    """
    Split text into chunks by estimated token count.
    
    Args:
        text: Text to split
        max_tokens: Maximum tokens per chunk
        overlap_tokens: Number of overlapping tokens between chunks
        
    Returns:
        List of text chunks
    """
    if not text:
        return []
    
    # Split by paragraphs first
    paragraphs = text.split('\n\n')
    
    chunks = []
    current_chunk = []
    current_tokens = 0
    
    for para in paragraphs:
        para_tokens = estimate_tokens(para)
        
        # If single paragraph is too large, split it
        if para_tokens > max_tokens:
            # Split by sentences
            sentences = para.replace('. ', '.\n').split('\n')
            for sent in sentences:
                sent_tokens = estimate_tokens(sent)
                
                if current_tokens + sent_tokens > max_tokens:
                    # Save current chunk
                    if current_chunk:
                        chunks.append('\n\n'.join(current_chunk))
                        
                        # Start new chunk with overlap
                        if overlap_tokens > 0 and current_chunk:
                            # Take last few sentences for overlap
                            overlap_text = '\n\n'.join(current_chunk[-2:])
                            if estimate_tokens(overlap_text) <= overlap_tokens:
                                current_chunk = [overlap_text]
                                current_tokens = estimate_tokens(overlap_text)
                            else:
                                current_chunk = []
                                current_tokens = 0
                        else:
                            current_chunk = []
                            current_tokens = 0
                
                current_chunk.append(sent)
                current_tokens += sent_tokens
        else:
            # Check if adding this paragraph exceeds limit
            if current_tokens + para_tokens > max_tokens:
                # Save current chunk
                if current_chunk:
                    chunks.append('\n\n'.join(current_chunk))
                    
                    # Start new chunk with overlap
                    if overlap_tokens > 0 and current_chunk:
                        # Take last paragraph for overlap
                        overlap_text = current_chunk[-1]
                        if estimate_tokens(overlap_text) <= overlap_tokens:
                            current_chunk = [overlap_text]
                            current_tokens = estimate_tokens(overlap_text)
                        else:
                            current_chunk = []
                            current_tokens = 0
                    else:
                        current_chunk = []
                        current_tokens = 0
            
            current_chunk.append(para)
            current_tokens += para_tokens
    
    # Add remaining chunk
    if current_chunk:
        chunks.append('\n\n'.join(current_chunk))
    
    return chunks


def create_chunk_from_section(
    section: IFUSection,
    section_key: str,
    record: IFURecord,
    max_tokens: int = 1000,
    overlap_tokens: int = 100
) -> List[IFUChunk]:
    """
    Create chunks from a single IFU section.
    
    Args:
        section: IFU section to chunk
        section_key: Key identifying the section type
        record: Parent IFU record for metadata
        max_tokens: Maximum tokens per chunk
        overlap_tokens: Overlapping tokens between chunks
        
    Returns:
        List of IFU chunks
    """
    if not section or not section.text:
        return []
    
    # Split the section text
    text_chunks = split_text_by_tokens(
        section.text,
        max_tokens=max_tokens,
        overlap_tokens=overlap_tokens
    )
    
    chunks = []
    total_chunks = len(text_chunks)
    
    for i, text in enumerate(text_chunks):
        # Generate chunk ID
        chunk_id = f"{record.regulatory.prov.doc_id if record.regulatory.prov else 'unknown'}_{section_key}_{i}"
        
        chunk = IFUChunk(
            doc_id=record.regulatory.prov.doc_id if record.regulatory.prov else "unknown",
            chunk_id=chunk_id,
            text=text,
            section_key=section_key,
            section_title=section.title,
            chunk_index=i,
            total_chunks=total_chunks,
            
            # Provenance
            source_path=section.prov.source_path if section.prov else "",
            sha256=section.prov.sha256 if section.prov else "",
            page_range=section.prov.pages if section.prov else [],
            
            # Metadata
            manufacturer=record.ifu_metadata.manufacturer,
            trade_name=record.ifu_metadata.trade_name,
            device_family=record.ifu_metadata.device_family,
            revision_id=record.ifu_metadata.revision_id,
            revision_date=str(record.ifu_metadata.revision_date) if record.ifu_metadata.revision_date else None,
            
            # Regulatory
            udi_di=record.regulatory.udi_di,
            catalog_numbers=record.regulatory.catalog_numbers,
            model_numbers=record.regulatory.model_numbers,
            product_codes=record.regulatory.product_codes,
            
            # Additional
            language=record.ifu_metadata.language,
            country_scope=record.ifu_metadata.country_scope,
        )
        
        chunks.append(chunk)
    
    return chunks


def create_chunk_from_structured(
    content: Any,
    section_key: str,
    section_title: str,
    record: IFURecord
) -> Optional[IFUChunk]:
    """
    Create a chunk from structured content (e.g., MRISafety, Reprocessing).
    
    Args:
        content: Structured content object
        section_key: Key identifying the section
        section_title: Human-readable section title
        record: Parent IFU record
        
    Returns:
        IFUChunk or None if no content
    """
    if not content:
        return None
    
    # Convert structured content to text
    text_parts = []
    
    if hasattr(content, 'model_dump'):
        # Pydantic model
        data = content.model_dump(exclude={'prov'})
        for key, value in data.items():
            if value is not None:
                # Format key nicely
                formatted_key = key.replace('_', ' ').title()
                if isinstance(value, list):
                    value_str = ', '.join(str(v) for v in value)
                elif isinstance(value, bool):
                    value_str = "Yes" if value else "No"
                else:
                    value_str = str(value)
                text_parts.append(f"{formatted_key}: {value_str}")
    else:
        # Simple conversion
        text_parts.append(str(content))
    
    if not text_parts:
        return None
    
    text = '\n'.join(text_parts)
    
    # Create chunk
    chunk_id = f"{record.regulatory.prov.doc_id if record.regulatory.prov else 'unknown'}_{section_key}_0"
    
    prov = getattr(content, 'prov', None)
    
    return IFUChunk(
        doc_id=record.regulatory.prov.doc_id if record.regulatory.prov else "unknown",
        chunk_id=chunk_id,
        text=text,
        section_key=section_key,
        section_title=section_title,
        chunk_index=0,
        total_chunks=1,
        
        # Provenance
        source_path=prov.source_path if prov else "",
        sha256=prov.sha256 if prov else "",
        page_range=prov.pages if prov else [],
        
        # Metadata
        manufacturer=record.ifu_metadata.manufacturer,
        trade_name=record.ifu_metadata.trade_name,
        device_family=record.ifu_metadata.device_family,
        revision_id=record.ifu_metadata.revision_id,
        revision_date=str(record.ifu_metadata.revision_date) if record.ifu_metadata.revision_date else None,
        
        # Regulatory
        udi_di=record.regulatory.udi_di,
        catalog_numbers=record.regulatory.catalog_numbers,
        model_numbers=record.regulatory.model_numbers,
        product_codes=record.regulatory.product_codes,
        
        # Additional
        language=record.ifu_metadata.language,
        country_scope=record.ifu_metadata.country_scope,
    )


def create_ifu_chunks(
    record: IFURecord,
    max_tokens: int = 1000,
    overlap_tokens: int = 100,
    include_metadata_chunk: bool = True
) -> List[IFUChunk]:
    """
    Create all chunks from an IFU record.
    
    Args:
        record: IFU record to chunk
        max_tokens: Maximum tokens per chunk
        overlap_tokens: Overlapping tokens
        include_metadata_chunk: Whether to create a metadata summary chunk
        
    Returns:
        List of all chunks
    """
    chunks = []
    
    # Create metadata summary chunk if requested
    if include_metadata_chunk:
        metadata_text = []
        
        if record.ifu_metadata.manufacturer:
            metadata_text.append(f"Manufacturer: {record.ifu_metadata.manufacturer}")
        if record.ifu_metadata.trade_name:
            metadata_text.append(f"Device: {record.ifu_metadata.trade_name}")
        if record.ifu_metadata.device_family:
            metadata_text.append(f"Device Family: {record.ifu_metadata.device_family}")
        if record.ifu_metadata.revision_id:
            metadata_text.append(f"Revision: {record.ifu_metadata.revision_id}")
        if record.ifu_metadata.revision_date:
            metadata_text.append(f"Revision Date: {record.ifu_metadata.revision_date}")
        
        if record.regulatory.udi_di:
            metadata_text.append(f"UDI-DI: {', '.join(record.regulatory.udi_di)}")
        if record.regulatory.catalog_numbers:
            metadata_text.append(f"Catalog Numbers: {', '.join(record.regulatory.catalog_numbers)}")
        if record.regulatory.model_numbers:
            metadata_text.append(f"Model Numbers: {', '.join(record.regulatory.model_numbers)}")
        
        if metadata_text:
            chunk_id = f"{record.regulatory.prov.doc_id if record.regulatory.prov else 'unknown'}_metadata_0"
            
            metadata_chunk = IFUChunk(
                doc_id=record.regulatory.prov.doc_id if record.regulatory.prov else "unknown",
                chunk_id=chunk_id,
                text='\n'.join(metadata_text),
                section_key="metadata",
                section_title="Device Information",
                chunk_index=0,
                total_chunks=1,
                source_path=record.fulltext_md_path or "",
                sha256="",
                page_range=[],
                manufacturer=record.ifu_metadata.manufacturer,
                trade_name=record.ifu_metadata.trade_name,
                device_family=record.ifu_metadata.device_family,
                revision_id=record.ifu_metadata.revision_id,
                revision_date=str(record.ifu_metadata.revision_date) if record.ifu_metadata.revision_date else None,
                udi_di=record.regulatory.udi_di,
                catalog_numbers=record.regulatory.catalog_numbers,
                model_numbers=record.regulatory.model_numbers,
                product_codes=record.regulatory.product_codes,
                language=record.ifu_metadata.language,
                country_scope=record.ifu_metadata.country_scope,
            )
            chunks.append(metadata_chunk)
    
    # Process text sections
    sections_to_chunk = [
        ("indications", record.indications),
        ("contraindications", record.contraindications),
        ("warnings", record.warnings),
        ("precautions", record.precautions),
        ("adverse_events", record.adverse_events),
        ("directions_for_use", record.directions_for_use),
        ("troubleshooting", record.troubleshooting),
        ("maintenance", record.maintenance),
        ("disposal", record.disposal),
    ]
    
    for section_key, section in sections_to_chunk:
        if section:
            section_chunks = create_chunk_from_section(
                section,
                section_key,
                record,
                max_tokens=max_tokens,
                overlap_tokens=overlap_tokens
            )
            chunks.extend(section_chunks)
    
    # Process structured sections
    if record.mri_safety:
        mri_chunk = create_chunk_from_structured(
            record.mri_safety,
            "mri_safety",
            "MRI Safety",
            record
        )
        if mri_chunk:
            chunks.append(mri_chunk)
    
    if record.reprocessing:
        reprocessing_chunk = create_chunk_from_structured(
            record.reprocessing,
            "reprocessing",
            "Reprocessing Instructions",
            record
        )
        if reprocessing_chunk:
            chunks.append(reprocessing_chunk)
    
    if record.compatibility:
        compat_chunk = create_chunk_from_structured(
            record.compatibility,
            "compatibility",
            "Device Compatibility",
            record
        )
        if compat_chunk:
            chunks.append(compat_chunk)
    
    if record.dimensions:
        dims_chunk = create_chunk_from_structured(
            record.dimensions,
            "dimensions",
            "Device Dimensions",
            record
        )
        if dims_chunk:
            chunks.append(dims_chunk)
    
    logger.info(f"Created {len(chunks)} chunks from IFU record")
    return chunks


def save_chunks_to_jsonl(chunks: List[IFUChunk], output_path: Path):
    """
    Save chunks to a JSONL file.
    
    Args:
        chunks: List of chunks to save
        output_path: Path to output JSONL file
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        for chunk in chunks:
            f.write(chunk.to_json() + '\n')
    
    logger.info(f"Saved {len(chunks)} chunks to {output_path}")