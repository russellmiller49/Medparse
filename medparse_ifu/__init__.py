"""
IFU (Instructions For Use) processing module for medical device documentation.

This module provides specialized extraction, enrichment, and chunking capabilities
for IFUs and other technical medical device documents.
"""

from medparse_ifu.schema import (
    IFURecord,
    IFUMetadata,
    RegIdentifiers,
    IFUSection,
    MRISafety,
    Reprocessing,
    Compatibility,
    Dimensions,
    Provenance,
)
from medparse_ifu.extractor import extract_ifu
from medparse_ifu.enrich_gudid import enrich_from_ids
from medparse_ifu.chunker import create_ifu_chunks

__all__ = [
    'IFURecord',
    'IFUMetadata',
    'RegIdentifiers',
    'IFUSection',
    'MRISafety',
    'Reprocessing',
    'Compatibility',
    'Dimensions',
    'Provenance',
    'extract_ifu',
    'enrich_from_ids',
    'create_ifu_chunks',
]