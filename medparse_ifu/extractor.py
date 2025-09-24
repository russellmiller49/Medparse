"""
IFU extraction using Docling for layout-aware document processing.
"""

from pathlib import Path
from hashlib import sha256
from typing import Optional, List, Dict, Any
from docling.document_converter import DocumentConverter
from medparse_ifu.schema import (
    IFURecord, 
    IFUMetadata, 
    RegIdentifiers, 
    IFUSection, 
    Provenance,
    MRISafety,
    Reprocessing,
    Compatibility,
    Dimensions,
)
from datetime import date
import re
import json
import logging

logger = logging.getLogger(__name__)


SECTION_ALIASES = {
    "indications": [
        r"\bindications?\b", 
        r"\bintended use\b",
        r"\bintended purpose\b",
    ],
    "contraindications": [
        r"\bcontraindications?\b",
        r"\bdo not use\b",
    ],
    "warnings": [
        r"\bwarnings?\b",
        r"\b⚠\b",  # warning symbol
    ],
    "precautions": [
        r"\bprecautions?\b",
        r"\bcautions?\b",
    ],
    "adverse_events": [
        r"\badverse events?\b", 
        r"\bcomplications?\b",
        r"\bside effects?\b",
    ],
    "directions_for_use": [
        r"\bdirections (for|of) use\b", 
        r"\binstructions\b", 
        r"\bprocedure\b",
        r"\bhow to use\b",
        r"\boperating instructions\b",
    ],
    "troubleshooting": [
        r"\btroubleshooting\b",
        r"\bproblem solving\b",
    ],
    "maintenance": [
        r"\bmaintenance\b",
        r"\bcare and maintenance\b",
    ],
    "disposal": [
        r"\bdisposal\b", 
        r"\bwaste\b",
        r"\bend of life\b",
    ],
    "reprocessing": [
        r"\breprocessing\b", 
        r"\bcleaning\b", 
        r"\bdisinfection\b", 
        r"\bsteriliz(e|ation)\b",
        r"\bdecontamination\b",
    ],
    "mri_safety": [
        r"\bmri\b", 
        r"\bmagnetic resonance\b", 
        r"\bASTM F2503\b",
        r"\bMR (safe|conditional|unsafe)\b",
    ],
    "compatibility": [
        r"\bcompatib", 
        r"\bbronch(o)?scope", 
        r"\bchannel\b",
        r"\baccessor(y|ies)\b",
    ],
    "dimensions": [
        r"\bdimension", 
        r"\bdiameter\b", 
        r"\blength\b", 
        r"\bsize\b",
        r"\bspecifications?\b",
    ],
}


def _hash_file(p: Path) -> str:
    """Calculate SHA256 hash of file."""
    return sha256(p.read_bytes()).hexdigest()


def export_tables(conv_res, out_dir: Path) -> list[str]:
    """Export tables from document as CSV files."""
    csv_paths = []
    tables = getattr(conv_res.document, 'tables', [])
    
    for i, table in enumerate(tables):
        try:
            df = table.export_to_dataframe()
            csv_path = out_dir / f"{conv_res.input.file.stem}-table-{i+1}.csv"
            df.to_csv(csv_path, index=False)
            csv_paths.append(str(csv_path))
            logger.info(f"Exported table {i+1} to {csv_path}")
        except Exception as e:
            logger.warning(f"Failed to export table {i+1}: {e}")
    
    return csv_paths


def extract_sections_from_markdown(md: str, section_aliases=SECTION_ALIASES):
    """Extract IFU sections from markdown based on heading patterns."""
    # Split on headings while preserving the heading itself
    blocks = re.split(r"\n(?=#{1,6}\s+)", md)
    found = {}
    
    for blk in blocks:
        if not blk.strip():
            continue
            
        header = re.match(r"^#{1,6}\s+(.+)", blk.strip())
        if not header:
            continue
            
        title = header.group(1).strip().lower()
        
        # Check if this title matches any of our section patterns
        for key, patterns in section_aliases.items():
            if any(re.search(pat, title, flags=re.I) for pat in patterns):
                # Merge if we already have content for this section
                if key in found:
                    found[key] += "\n\n" + blk
                else:
                    found[key] = blk
                break
    
    return found


def parse_reg_identifiers(md: str) -> RegIdentifiers:
    """Extract regulatory identifiers from markdown text."""
    # UDI patterns
    udi = re.findall(
        r"\b(?:UDI(?:-DI)?|Device Identifier)[:\s]*([A-Za-z0-9\-\.\(\)\/\+]+)",
        md, flags=re.I
    )
    
    # Catalog numbers
    cat = re.findall(
        r"\b(?:cat(?:alog)?(?:\s+no\.?|\s+#|\s+number)?)[:\s]*([A-Za-z0-9\-\.\_/]+)",
        md, flags=re.I
    )
    
    # Model numbers
    model = re.findall(
        r"\b(?:model(?:\s+no\.?|\s+#|\s+number)?)[:\s]*([A-Za-z0-9\-\.\_/]+)",
        md, flags=re.I
    )
    
    # FDA product codes (typically 3 letters)
    prod_codes = re.findall(r"\bProduct Code[:\s]*([A-Z]{3})\b", md, flags=re.I)
    
    # 510(k) numbers
    k510 = re.findall(r"\bK\d{6}\b", md)
    
    # PMA numbers
    pma = re.findall(r"\bP\d{6}\b", md)
    
    # GMDN terms
    gmdn = re.findall(
        r"\bGMDN[:\s]*([^,\n]+)",
        md, flags=re.I
    )
    
    return RegIdentifiers(
        udi_di=list(dict.fromkeys(udi)) or None,
        catalog_numbers=[m for m in cat if m] or None,
        model_numbers=[m for m in model if m] or None,
        product_codes=list(dict.fromkeys(prod_codes)) or None,
        k510_numbers=list(dict.fromkeys(k510)) or None,
        pma_numbers=list(dict.fromkeys(pma)) or None,
        gmdn_terms=[g.strip() for g in gmdn if g.strip()] or None,
    )


def extract_mri_safety(md: str, prov: Provenance) -> Optional[MRISafety]:
    """Extract MRI safety information from text."""
    # Look for explicit MR safety status
    status_match = re.search(
        r"\bMR\s*(Safe|Conditional|Unsafe)\b",
        md, flags=re.I
    )
    
    if not status_match:
        return None
    
    status = status_match.group(1).title()
    
    # Try to extract conditions for MR Conditional devices
    conditions = None
    if status == "Conditional":
        # Look for conditions in the vicinity of the status
        context_start = max(0, status_match.start() - 500)
        context_end = min(len(md), status_match.end() + 500)
        context = md[context_start:context_end]
        
        # Common condition patterns
        tesla_match = re.search(r"(\d+(?:\.\d+)?)\s*T(?:esla)?", context, flags=re.I)
        sar_match = re.search(r"SAR[:\s]*(?:<|less than)?\s*(\d+(?:\.\d+)?)\s*W/kg", context, flags=re.I)
        
        conditions_parts = []
        if tesla_match:
            conditions_parts.append(f"{tesla_match.group(1)}T max field strength")
        if sar_match:
            conditions_parts.append(f"SAR < {sar_match.group(1)} W/kg")
            
        if conditions_parts:
            conditions = ", ".join(conditions_parts)
    
    return MRISafety(
        status=status,
        conditions=conditions,
        prov=prov
    )


def extract_reprocessing(sections: dict, prov: Provenance) -> Optional[Reprocessing]:
    """Extract reprocessing information from relevant sections."""
    if "reprocessing" not in sections:
        return None
    
    text = sections["reprocessing"]
    
    # Check for single use
    single_use = None
    if re.search(r"\bsingle[- ]use\b|\bdo not reuse\b|\bdisposable\b", text, flags=re.I):
        single_use = True
    elif re.search(r"\breusable\b|\bmulti[- ]use\b", text, flags=re.I):
        single_use = False
    
    # Extract cleaning instructions
    cleaning = None
    cleaning_match = re.search(
        r"cleaning[:\s]+([^.]+\.)",
        text, flags=re.I | re.S
    )
    if cleaning_match:
        cleaning = cleaning_match.group(1).strip()
    
    # Extract disinfection instructions
    disinfection = None
    disinfection_match = re.search(
        r"disinfection[:\s]+([^.]+\.)",
        text, flags=re.I | re.S
    )
    if disinfection_match:
        disinfection = disinfection_match.group(1).strip()
    
    # Extract sterilization instructions
    sterilization = None
    sterilization_match = re.search(
        r"steriliz(?:e|ation)[:\s]+([^.]+\.)",
        text, flags=re.I | re.S
    )
    if sterilization_match:
        sterilization = sterilization_match.group(1).strip()
    
    return Reprocessing(
        single_use=single_use,
        cleaning=cleaning,
        disinfection=disinfection,
        sterilization=sterilization,
        prov=prov
    )


def extract_compatibility(sections: dict, prov: Provenance) -> Optional[Compatibility]:
    """Extract device compatibility information."""
    relevant_text = ""
    for key in ["compatibility", "dimensions"]:
        if key in sections:
            relevant_text += sections[key] + "\n"
    
    if not relevant_text:
        return None
    
    # Extract minimum channel size
    channel_min = None
    channel_match = re.search(
        r"(?:minimum|min\.?)\s+(?:channel|working channel)[:\s]*(\d+(?:\.\d+)?)\s*mm",
        relevant_text, flags=re.I
    )
    if channel_match:
        channel_min = float(channel_match.group(1))
    
    # Extract compatible scopes
    scopes = []
    scope_matches = re.findall(
        r"compatible with[:\s]*([^.]+(?:scope|endoscope)[^.]*)",
        relevant_text, flags=re.I
    )
    for match in scope_matches:
        scopes.extend([s.strip() for s in re.split(r"[,;]", match)])
    
    return Compatibility(
        bronch_channel_mm_min=channel_min,
        compatible_scopes=list(set(scopes)) if scopes else None,
        prov=prov
    )


def extract_dimensions(sections: dict, prov: Provenance) -> Optional[Dimensions]:
    """Extract device dimensions."""
    if "dimensions" not in sections:
        return None
    
    text = sections["dimensions"]
    
    # Extract outer diameter
    od = None
    od_match = re.search(
        r"(?:outer diameter|OD|O\.D\.)[:\s]*(\d+(?:\.\d+)?)\s*mm",
        text, flags=re.I
    )
    if od_match:
        od = float(od_match.group(1))
    
    # Extract length
    length = None
    length_match = re.search(
        r"(?:length|working length)[:\s]*(\d+(?:\.\d+)?)\s*mm",
        text, flags=re.I
    )
    if length_match:
        length = float(length_match.group(1))
    
    # Extract other dimensions
    other_dims = {}
    dim_matches = re.findall(
        r"(\w+(?:\s+\w+)?)[:\s]*(\d+(?:\.\d+)?)\s*(mm|cm|in)",
        text, flags=re.I
    )
    for name, value, unit in dim_matches:
        if name.lower() not in ["outer diameter", "od", "length", "working length"]:
            other_dims[name] = f"{value} {unit}"
    
    if not (od or length or other_dims):
        return None
    
    return Dimensions(
        od_mm=od,
        length_mm=length,
        other_dims=other_dims,
        prov=prov
    )


def extract_ifu_metadata(md: str) -> IFUMetadata:
    """Extract IFU metadata from markdown text."""
    metadata = IFUMetadata(language="en")
    
    # Manufacturer
    mfg_match = re.search(
        r"\b(?:manufacturer|labeler|manufactured by)[:\s]+(.+?)(?:\n|$)",
        md, flags=re.I | re.M
    )
    if mfg_match:
        metadata.manufacturer = mfg_match.group(1).strip()
    
    # Device/Trade name (often in the title)
    title_match = re.search(r"^#\s+(.+?)(?:\n|$)", md, flags=re.M)
    if title_match:
        metadata.device_family = title_match.group(1).strip()
    
    # Trade name
    trade_match = re.search(
        r"\b(?:trade name|brand name)[:\s]+(.+?)(?:\n|$)",
        md, flags=re.I | re.M
    )
    if trade_match:
        metadata.trade_name = trade_match.group(1).strip()
    
    # Revision info
    rev_match = re.search(
        r"\b(?:revision|rev\.?)[:\s]*([A-Za-z0-9\.\-]+)",
        md, flags=re.I
    )
    if rev_match:
        metadata.revision_id = rev_match.group(1)
    
    # Revision date
    date_match = re.search(
        r"\b(?:issued|effective|revision date|date)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2})",
        md, flags=re.I
    )
    if date_match:
        date_str = date_match.group(1)
        # Try to parse date (simple approach - could be enhanced)
        try:
            # Handle MM/DD/YYYY or YYYY-MM-DD formats
            if "/" in date_str:
                parts = date_str.split("/")
                if len(parts[0]) == 4:  # YYYY/MM/DD
                    metadata.revision_date = date(int(parts[0]), int(parts[1]), int(parts[2]))
                else:  # MM/DD/YYYY
                    metadata.revision_date = date(int(parts[2]), int(parts[0]), int(parts[1]))
            elif "-" in date_str:
                parts = date_str.split("-")
                if len(parts[0]) == 4:  # YYYY-MM-DD
                    metadata.revision_date = date(int(parts[0]), int(parts[1]), int(parts[2]))
                else:  # MM-DD-YYYY
                    metadata.revision_date = date(int(parts[2]), int(parts[0]), int(parts[1]))
        except (ValueError, IndexError):
            pass
    
    # Contact info
    contact_match = re.search(
        r"(?:contact|customer service|support)[:\s]+(.+?)(?:\n|$)",
        md, flags=re.I | re.M
    )
    if contact_match:
        metadata.contact = contact_match.group(1).strip()
    
    # Website
    website_match = re.search(
        r"(?:website|web|www)[:\s]*((?:https?://)?(?:www\.)?[a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,}(?:/[^\s]*)?)",
        md, flags=re.I
    )
    if website_match:
        metadata.website = website_match.group(1).strip()
    
    return metadata


def create_section_object(
    section_name: str,
    sections: dict,
    prov: Provenance
) -> Optional[IFUSection]:
    """Create an IFUSection object from extracted section text."""
    if section_name not in sections:
        return None
    
    # Strip first heading line for cleaner text
    text = re.sub(r"^#{1,6}\s+.+\n", "", sections[section_name]).strip()
    
    if not text:
        return None
    
    return IFUSection(
        title=section_name.replace("_", " ").title(),
        text=text,
        prov=prov
    )


def extract_ifu(pdf_path: Path, out_dir: Path) -> IFURecord:
    """
    Extract IFU information from a PDF document.
    
    Args:
        pdf_path: Path to the PDF file
        out_dir: Output directory for extracted content
        
    Returns:
        IFURecord with extracted information
    """
    logger.info(f"Processing IFU: {pdf_path}")
    
    # Create output directory
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Calculate file hash for provenance
    file_hash = _hash_file(pdf_path)
    
    # Convert document using Docling
    logger.info("Converting document with Docling...")
    converter = DocumentConverter()
    conv_res = converter.convert(str(pdf_path))
    
    # Export to markdown
    md = conv_res.document.export_to_markdown()
    md_path = out_dir / f"{pdf_path.stem}.md"
    md_path.write_text(md, encoding="utf-8")
    logger.info(f"Saved markdown to {md_path}")
    
    # Export tables
    tables_csv = export_tables(conv_res, out_dir)
    
    # Extract sections from markdown
    sections = extract_sections_from_markdown(md)
    logger.info(f"Found sections: {list(sections.keys())}")
    
    # Create provenance
    prov = Provenance(
        doc_id=file_hash[:12],
        source_path=str(pdf_path),
        sha256=file_hash,
        pages=[]  # TODO: Extract page numbers from Docling if available
    )
    
    # Extract metadata
    metadata = extract_ifu_metadata(md)
    
    # Extract regulatory identifiers
    regulatory = parse_reg_identifiers(md)
    
    # Extract MRI safety
    mri_safety = extract_mri_safety(md, prov)
    
    # Extract reprocessing
    reprocessing = extract_reprocessing(sections, prov)
    
    # Extract compatibility
    compatibility = extract_compatibility(sections, prov)
    
    # Extract dimensions
    dimensions = extract_dimensions(sections, prov)
    
    # Create the IFU record
    record = IFURecord(
        ifu_metadata=metadata,
        regulatory=regulatory,
        indications=create_section_object("indications", sections, prov),
        contraindications=create_section_object("contraindications", sections, prov),
        warnings=create_section_object("warnings", sections, prov),
        precautions=create_section_object("precautions", sections, prov),
        adverse_events=create_section_object("adverse_events", sections, prov),
        directions_for_use=create_section_object("directions_for_use", sections, prov),
        troubleshooting=create_section_object("troubleshooting", sections, prov),
        maintenance=create_section_object("maintenance", sections, prov),
        disposal=create_section_object("disposal", sections, prov),
        reprocessing=reprocessing,
        mri_safety=mri_safety,
        compatibility=compatibility,
        dimensions=dimensions,
        tables_csv=tables_csv,
        figures=[],  # TODO: Extract figures from Docling if needed
        fulltext_md_path=str(md_path),
        extracted_at=date.today(),
    )
    
    # Save the record as JSON
    out_json = out_dir / f"{pdf_path.stem}.ifu.json"
    out_json.write_text(json.dumps(record.model_dump(), indent=2, default=str), encoding="utf-8")
    logger.info(f"Saved IFU record to {out_json}")
    
    return record