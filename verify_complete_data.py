#!/usr/bin/env python3
"""
Comprehensive verification of the JSON files to show actual state.
"""
import json
from pathlib import Path
import sys

def verify_files(directory: Path):
    """Verify the 10 specific files mentioned in the review."""
    
    test_files = [
        "An updated review in percutaneous tracheostomy.json",
        "Andriolo-2015-Early versus late tracheostomy f.json",
        "Anesthesia and Upper and Lower Airway.json",
        "Anesthesia for bronchoscopy and update 2024.json",
        "Anesthetic considerations for bronchoscopic procedures.json",
        "Angel-2020-Novel Percutaneous Tracheostomy for.json",
        "Approach to hemoptysis in the modern era.json",
        "Arnold-2018-Investigating unilateral pleural e.json",
        "ASAP trial.json",
        "AMPLE2.json"
    ]
    
    print(f"VERIFICATION REPORT FOR: {directory}")
    print("=" * 80)
    
    for fname in test_files:
        filepath = directory / fname
        
        if not filepath.exists():
            print(f"\n❌ {fname}")
            print("   FILE NOT FOUND")
            continue
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            metadata = data.get('metadata', {})
            sections = data.get('sections', [])
            tables = data.get('tables', [])
            
            # Check abstract
            abstract = metadata.get('abstract', '')
            abstract_source = metadata.get('abstract_source', 'unknown')
            
            # Check for empty sections
            empty_sections = []
            total_content_length = 0
            for section in sections:
                content = section.get('content', '').strip()
                if not content:
                    empty_sections.append(section.get('title', 'Untitled'))
                else:
                    total_content_length += len(content)
            
            # Check table headers
            tables_with_headers = 0
            tables_without_headers = 0
            total_table_rows = 0
            for table in tables:
                if table.get('headers'):
                    tables_with_headers += 1
                else:
                    tables_without_headers += 1
                total_table_rows += len(table.get('rows', []))
            
            # Print summary
            status = "✅" if abstract and not empty_sections else "⚠️"
            print(f"\n{status} {fname}")
            print(f"   Abstract: {'YES' if abstract else 'NO'} ({len(abstract)} chars, source: {abstract_source})")
            print(f"   Sections: {len(sections)} total, {len(empty_sections)} empty, {total_content_length} total chars")
            if empty_sections:
                print(f"   Empty sections: {empty_sections[:3]}{'...' if len(empty_sections) > 3 else ''}")
            print(f"   Tables: {len(tables)} total ({tables_with_headers} with headers, {tables_without_headers} without)")
            if tables:
                print(f"   Table data: {total_table_rows} total rows across all tables")
            
        except Exception as e:
            print(f"\n❌ {fname}")
            print(f"   ERROR: {str(e)}")
    
    print("\n" + "=" * 80)
    print("SUMMARY:")
    print(f"Directory checked: {directory}")
    print(f"Files verified: {len(test_files)}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        directory = Path(sys.argv[1])
    else:
        directory = Path("out/rag_ready_complete")
    
    if not directory.exists():
        print(f"Error: Directory {directory} does not exist")
        sys.exit(1)
    
    verify_files(directory)