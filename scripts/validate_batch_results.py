#!/usr/bin/env python3
"""
Validate batch processing results for common issues
"""
import json
from pathlib import Path
from typing import Dict, List
import sys

def validate_json_file(json_path: Path) -> Dict:
    """Validate a single JSON output file"""
    issues = []
    warnings = []
    
    try:
        with open(json_path) as f:
            data = json.load(f)
        
        # Check for raw Docling document
        if data.get("schema_name") == "DoclingDocument":
            issues.append("ERROR: Raw Docling document detected (not merged pipeline JSON)")
        
        # Check required top-level keys
        required_keys = ["metadata", "structure"]
        for key in required_keys:
            if key not in data:
                issues.append(f"ERROR: Missing required key '{key}'")
        
        # Check for statistics issues
        stats = data.get("statistics", [])
        for stat in stats:
            # Check for grant-like patterns in stats
            if isinstance(stat, dict):
                text = stat.get("text", "")
                if any(c in text for c in ["U54HL", "NIH", "1R01"]):
                    issues.append(f"ERROR: Grant ID in statistics: {text}")
                
                # Check for citation patterns
                if isinstance(stat.get("value"), list) and len(stat["value"]) == 2:
                    if all(isinstance(v, (int, float)) and v < 100 for v in stat["value"]):
                        # Could be a citation like (3,4)
                        if "CI" not in text.upper() and "confidence" not in text.lower():
                            issues.append(f"WARNING: Possible citation in statistics: {text}")
        
        # Check UMLS links
        umls_links = data.get("umls_links", [])
        for link in umls_links:
            if isinstance(link, dict):
                text = link.get("text", "").lower()
                # Check for problematic patterns
                if "history of" in text and any(num in text for num in ["one", "two", "three", "four", "five"]):
                    issues.append(f"ERROR: Suspicious UMLS link: '{link.get('text')}' -> {link.get('preferred_name')}")
        
        # Check authors
        authors = data.get("metadata", {}).get("authors", [])
        if any(not author or not author.strip() for author in authors if isinstance(author, str)):
            issues.append("ERROR: Blank author entries detected")
        
        # Check file size (warn if too large, might have base64 images)
        file_size_mb = json_path.stat().st_size / (1024 * 1024)
        if file_size_mb > 10:
            warnings.append(f"WARNING: Large file size ({file_size_mb:.1f} MB) - may contain base64 images")
        
        # Check tables/figures for captions
        tables = data.get("structure", {}).get("tables", [])
        figures = data.get("structure", {}).get("figures", [])
        
        tables_without_caption = sum(1 for t in tables if not t.get("caption"))
        if tables and tables_without_caption > 0:
            warnings.append(f"INFO: {tables_without_caption}/{len(tables)} tables missing captions")
        
        figures_without_caption = sum(1 for f in figures if not f.get("caption"))
        if figures and figures_without_caption > 0:
            warnings.append(f"INFO: {figures_without_caption}/{len(figures)} figures missing captions")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "stats": {
                "n_sections": len(data.get("structure", {}).get("sections", [])),
                "n_tables": len(tables),
                "n_figures": len(figures),
                "n_statistics": len(stats),
                "n_umls_links": len(umls_links),
                "n_authors": len(authors),
                "file_size_mb": round(file_size_mb, 2)
            }
        }
        
    except json.JSONDecodeError as e:
        return {
            "valid": False,
            "issues": [f"ERROR: Invalid JSON - {e}"],
            "warnings": [],
            "stats": {}
        }
    except Exception as e:
        return {
            "valid": False,
            "issues": [f"ERROR: Could not validate - {e}"],
            "warnings": [],
            "stats": {}
        }

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate batch processing results")
    parser.add_argument("--dir", default="out/test_batch_umls", help="Directory with JSON outputs")
    parser.add_argument("--verbose", action="store_true", help="Show all warnings and info")
    args = parser.parse_args()
    
    output_dir = Path(args.dir)
    if not output_dir.exists():
        print(f"ERROR: Directory does not exist: {output_dir}")
        return 1
    
    json_files = list(output_dir.glob("*.json"))
    # Exclude the report file
    json_files = [f for f in json_files if f.name != "test_report.json"]
    
    if not json_files:
        print(f"No JSON files found in {output_dir}")
        return 1
    
    print(f"Validating {len(json_files)} JSON files in {output_dir}")
    print("=" * 60)
    
    all_valid = True
    total_issues = 0
    total_warnings = 0
    
    for json_file in sorted(json_files):
        print(f"\n{json_file.name}:")
        result = validate_json_file(json_file)
        
        if result["valid"]:
            print("  ✓ VALID")
        else:
            print("  ✗ INVALID")
            all_valid = False
        
        # Show issues
        for issue in result["issues"]:
            print(f"    {issue}")
            total_issues += 1
        
        # Show warnings if verbose
        if args.verbose or not result["valid"]:
            for warning in result["warnings"]:
                print(f"    {warning}")
                total_warnings += 1
        
        # Show stats
        if result["stats"]:
            stats = result["stats"]
            print(f"    Stats: {stats['n_sections']} sections, {stats['n_tables']} tables, "
                  f"{stats['n_figures']} figures, {stats['n_statistics']} statistics, "
                  f"{stats['n_umls_links']} UMLS links")
    
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    print(f"Files validated: {len(json_files)}")
    print(f"Valid files: {sum(1 for f in json_files if validate_json_file(f)['valid'])}")
    print(f"Total issues: {total_issues}")
    if args.verbose:
        print(f"Total warnings: {total_warnings}")
    
    if all_valid:
        print("\n✓ All files passed validation!")
        return 0
    else:
        print("\n✗ Some files have validation issues")
        return 1

if __name__ == "__main__":
    sys.exit(main())