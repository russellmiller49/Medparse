#!/usr/bin/env python3
"""
Audit abstracts in cleaned JSON files to track sources and missing items.
"""
import json
import sys
from pathlib import Path
from collections import defaultdict

def audit_abstracts(directory: Path):
    """Audit all JSON files for abstract presence and sources."""
    missing = []
    sources = defaultdict(int)
    total_files = 0
    errors = []
    
    for p in sorted(directory.glob("*.json")):
        # Skip chunk files
        if p.name.endswith("_chunks.json"):
            continue
        
        total_files += 1
        
        try:
            js = json.loads(p.read_text(encoding="utf-8"))
            meta = js.get("metadata", {}) or {}
            quality = js.get("quality", {}) or {}
            
            has_abstract = bool(meta.get("abstract") and meta["abstract"].strip())
            
            # Track source of abstract
            if has_abstract:
                # Try multiple places where source might be stored
                src = (meta.get("abstract_source") or 
                       quality.get("abstract_source") or 
                       "unknown")
                sources[src] += 1
            else:
                sources["missing"] += 1
                missing.append({
                    "file": p.name,
                    "title": meta.get("title", "No title")[:80],
                    "doi": meta.get("doi", ""),
                    "year": meta.get("year", "")
                })
                
        except Exception as e:
            errors.append(f"{p.name}: {e}")
            sources["error"] += 1
    
    # Print summary
    print("=" * 80)
    print("ABSTRACT AUDIT SUMMARY")
    print("=" * 80)
    print(f"\nTotal files: {total_files}")
    print(f"With abstracts: {total_files - sources['missing'] - sources.get('error', 0)}")
    print(f"Missing: {sources['missing']}")
    
    if errors:
        print(f"Errors: {len(errors)}")
    
    print("\n--- Abstract Sources ---")
    for src in sorted(sources.keys()):
        if src != "missing" and src != "error":
            print(f"  {src:20s}: {sources[src]:4d}")
    
    print(f"\n  {'TOTAL WITH ABSTRACT':20s}: {sum(v for k,v in sources.items() if k not in ['missing', 'error']):4d}")
    print(f"  {'MISSING':20s}: {sources['missing']:4d}")
    
    if sources.get('error'):
        print(f"  {'ERRORS':20s}: {sources['error']:4d}")
    
    # Calculate percentages
    if total_files > 0:
        pct_with = (total_files - sources['missing'] - sources.get('error', 0)) / total_files * 100
        pct_missing = sources['missing'] / total_files * 100
        print(f"\n--- Coverage ---")
        print(f"  With abstracts: {pct_with:.1f}%")
        print(f"  Missing: {pct_missing:.1f}%")
    
    # Show sample of missing
    if missing:
        print(f"\n--- Sample of Missing Abstracts (first 10) ---")
        for item in missing[:10]:
            print(f"  • {item['file'][:50]:50s} | {item['year']:>4} | {item['title'][:40]}")
    
    # Show errors if any
    if errors:
        print(f"\n--- Errors ---")
        for err in errors[:5]:
            print(f"  ! {err}")
    
    # Write detailed report to file
    report_file = directory / "abstract_audit_report.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("ABSTRACT AUDIT REPORT\n")
        f.write("=" * 80 + "\n")
        f.write(f"Directory: {directory}\n")
        f.write(f"Total files: {total_files}\n")
        f.write(f"With abstracts: {total_files - sources['missing'] - sources.get('error', 0)}\n")
        f.write(f"Missing: {sources['missing']}\n\n")
        
        f.write("Abstract Sources:\n")
        for src in sorted(sources.keys()):
            if src not in ['missing', 'error']:
                f.write(f"  {src}: {sources[src]}\n")
        
        f.write(f"\n\nFILES MISSING ABSTRACTS ({len(missing)} total):\n")
        f.write("-" * 80 + "\n")
        for item in missing:
            f.write(f"\nFile: {item['file']}\n")
            f.write(f"  Title: {item['title']}\n")
            f.write(f"  Year: {item['year']}\n")
            f.write(f"  DOI: {item['doi']}\n")
        
        if errors:
            f.write(f"\n\nERRORS ({len(errors)} total):\n")
            f.write("-" * 80 + "\n")
            for err in errors:
                f.write(f"  {err}\n")
    
    print(f"\n✓ Detailed report saved to: {report_file}")
    
    return {
        "total": total_files,
        "with_abstract": total_files - sources['missing'] - sources.get('error', 0),
        "missing": sources['missing'],
        "sources": dict(sources),
        "errors": len(errors)
    }

def main():
    if len(sys.argv) > 1:
        directory = Path(sys.argv[1])
    else:
        directory = Path("out/rag_ready_fixed")
    
    if not directory.exists():
        print(f"Error: Directory {directory} does not exist")
        sys.exit(1)
    
    results = audit_abstracts(directory)
    
    # Return exit code based on results
    if results['missing'] > results['total'] * 0.5:  # More than 50% missing
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()