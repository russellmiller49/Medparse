#!/usr/bin/env python3
"""
CLI orchestration for IFU processing pipeline.

Processes IFU documents through:
1. Extraction with Docling
2. Optional enrichment from GUDID/OpenFDA
3. RAG-ready chunking
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import List, Optional

from medparse_ifu.extractor import extract_ifu
from medparse_ifu.enrich_gudid import enrich_from_ids
from medparse_ifu.chunker import create_ifu_chunks, save_chunks_to_jsonl
from medparse_ifu.schema import IFURecord

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def find_pdf_files(input_path: Path) -> List[Path]:
    """
    Find all PDF files in the input directory.
    
    Args:
        input_path: Input directory path
        
    Returns:
        List of PDF file paths
    """
    pdf_files = []
    
    if input_path.is_file():
        if input_path.suffix.lower() == '.pdf':
            pdf_files.append(input_path)
    elif input_path.is_dir():
        # Find all PDFs recursively
        pdf_files.extend(input_path.glob('**/*.pdf'))
        pdf_files.extend(input_path.glob('**/*.PDF'))
    
    return sorted(pdf_files)


def find_docx_files(input_path: Path) -> List[Path]:
    """
    Find all DOCX files in the input directory.
    
    Args:
        input_path: Input directory path
        
    Returns:
        List of DOCX file paths
    """
    docx_files = []
    
    if input_path.is_file():
        if input_path.suffix.lower() in ['.docx', '.doc']:
            docx_files.append(input_path)
    elif input_path.is_dir():
        # Find all DOCX files recursively
        docx_files.extend(input_path.glob('**/*.docx'))
        docx_files.extend(input_path.glob('**/*.DOCX'))
        docx_files.extend(input_path.glob('**/*.doc'))
        docx_files.extend(input_path.glob('**/*.DOC'))
    
    return sorted(docx_files)


def process_single_ifu(
    file_path: Path,
    out_dir: Path,
    enrich_sources: Optional[List[str]] = None,
    create_chunks: bool = True,
    max_tokens: int = 1000,
    overlap_tokens: int = 100
) -> Optional[IFURecord]:
    """
    Process a single IFU document.
    
    Args:
        file_path: Path to the IFU document
        out_dir: Output directory
        enrich_sources: List of enrichment sources to use
        create_chunks: Whether to create RAG chunks
        max_tokens: Maximum tokens per chunk
        overlap_tokens: Overlapping tokens between chunks
        
    Returns:
        IFURecord or None if processing failed
    """
    try:
        logger.info(f"Processing: {file_path}")
        
        # Create subdirectories
        json_dir = out_dir / "json"
        json_dir.mkdir(parents=True, exist_ok=True)
        
        csv_dir = out_dir / "csv"
        csv_dir.mkdir(parents=True, exist_ok=True)
        
        # Extract IFU
        logger.info("Extracting IFU content...")
        record = extract_ifu(file_path, json_dir)
        
        # Enrich if requested
        if enrich_sources:
            logger.info(f"Enriching from sources: {enrich_sources}")
            record = enrich_from_ids(record, enrich_sources)
            
            # Save enriched version
            enriched_path = json_dir / f"{file_path.stem}.enriched.json"
            enriched_path.write_text(
                json.dumps(record.model_dump(), indent=2, default=str),
                encoding="utf-8"
            )
            logger.info(f"Saved enriched record to {enriched_path}")
        
        # Create chunks if requested
        if create_chunks:
            logger.info("Creating RAG chunks...")
            chunks = create_ifu_chunks(
                record,
                max_tokens=max_tokens,
                overlap_tokens=overlap_tokens
            )
            
            chunks_dir = out_dir / "chunks"
            chunks_dir.mkdir(parents=True, exist_ok=True)
            
            chunks_path = chunks_dir / f"{file_path.stem}.chunks.jsonl"
            save_chunks_to_jsonl(chunks, chunks_path)
            logger.info(f"Saved {len(chunks)} chunks to {chunks_path}")
        
        logger.info(f"Successfully processed: {file_path.name}")
        return record
        
    except Exception as e:
        logger.error(f"Failed to process {file_path}: {e}", exc_info=True)
        return None


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Process IFU documents for RAG applications",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process single IFU
  python -m medparse.ifu.run --input path/to/ifu.pdf --out out/ifu
  
  # Process directory of IFUs with enrichment
  python -m medparse.ifu.run --input input/ifu --out out/ifu --enrich gudid,openfda
  
  # Process with custom chunk size
  python -m medparse.ifu.run --input input/ifu --out out/ifu --chunks --max-tokens 800
  
  # Dry run without chunking
  python -m medparse.ifu.run --input input/ifu --out out/ifu --no-chunks
        """
    )
    
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Input IFU file or directory containing IFU documents"
    )
    
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Output directory for processed IFUs"
    )
    
    parser.add_argument(
        "--enrich",
        type=str,
        help="Comma-separated list of enrichment sources (gudid,openfda)"
    )
    
    parser.add_argument(
        "--chunks",
        action="store_true",
        default=True,
        help="Create RAG chunks (default: True)"
    )
    
    parser.add_argument(
        "--no-chunks",
        dest="chunks",
        action="store_false",
        help="Skip chunk creation"
    )
    
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=1000,
        help="Maximum tokens per chunk (default: 1000)"
    )
    
    parser.add_argument(
        "--overlap-tokens",
        type=int,
        default=100,
        help="Overlapping tokens between chunks (default: 100)"
    )
    
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)"
    )
    
    args = parser.parse_args()
    
    # Set logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Validate input path
    if not args.input.exists():
        logger.error(f"Input path does not exist: {args.input}")
        sys.exit(1)
    
    # Parse enrichment sources
    enrich_sources = None
    if args.enrich:
        enrich_sources = [s.strip() for s in args.enrich.split(",")]
        valid_sources = ["gudid", "openfda"]
        for source in enrich_sources:
            if source not in valid_sources:
                logger.error(f"Invalid enrichment source: {source}")
                logger.error(f"Valid sources: {', '.join(valid_sources)}")
                sys.exit(1)
    
    # Find files to process
    files_to_process = []
    files_to_process.extend(find_pdf_files(args.input))
    files_to_process.extend(find_docx_files(args.input))
    
    if not files_to_process:
        logger.warning(f"No PDF or DOCX files found in: {args.input}")
        sys.exit(0)
    
    logger.info(f"Found {len(files_to_process)} files to process")
    
    # Process each file
    successful = 0
    failed = 0
    
    for file_path in files_to_process:
        result = process_single_ifu(
            file_path,
            args.out,
            enrich_sources=enrich_sources,
            create_chunks=args.chunks,
            max_tokens=args.max_tokens,
            overlap_tokens=args.overlap_tokens
        )
        
        if result:
            successful += 1
        else:
            failed += 1
    
    # Summary
    logger.info(f"\nProcessing complete:")
    logger.info(f"  Successful: {successful}")
    logger.info(f"  Failed: {failed}")
    
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()