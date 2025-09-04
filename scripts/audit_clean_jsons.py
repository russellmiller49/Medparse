#!/usr/bin/env python3
"""
Audit cleaned JSON files to check for proper retention of clinical data.
"""
import json
import sys
from pathlib import Path

def audit_files(root_dir: Path):
    """Audit all cleaned JSON files in the given directory."""
    root = root_dir
    
    bad = []
    stats = {
        'files': 0,
        'no_full_text': 0,
        'low_refs': 0,
        'no_tables_field': 0,
        'no_figures_field': 0,
        'missing_abstract': 0,
        'low_sections': 0
    }
    
    for p in root.glob('*.json'):
        if p.name.endswith('_chunks.json'):
            continue
        stats['files'] += 1
        
        try:
            with p.open('r', encoding='utf-8') as f:
                doc = json.load(f)
            
            qual = doc.get('quality', {})
            
            # Check full text
            if not qual.get('has_full_text'):
                stats['no_full_text'] += 1
                bad.append((p.name, 'no_full_text'))
            
            # Check references
            if qual.get('num_references', 0) == 0:
                stats['low_refs'] += 1
                bad.append((p.name, 'no_references'))
            
            # Check tables field exists
            if 'tables' not in doc:
                stats['no_tables_field'] += 1
                bad.append((p.name, 'no_tables_field'))
            
            # Check figures field exists
            if 'figures' not in doc:
                stats['no_figures_field'] += 1
                bad.append((p.name, 'no_figures_field'))
            
            # Check abstract
            if not doc.get('metadata', {}).get('abstract'):
                stats['missing_abstract'] += 1
                bad.append((p.name, 'missing_abstract'))
            
            # Check section count
            if qual.get('num_sections', 0) < 3:
                stats['low_sections'] += 1
                bad.append((p.name, f"low_sections({qual.get('num_sections', 0)})"))
                
        except Exception as e:
            bad.append((p.name, f'error: {e}'))
    
    # Print summary
    print("=== AUDIT SUMMARY ===")
    print(f"Total files processed: {stats['files']}")
    print(f"\nIssues found:")
    print(f"  - No full text: {stats['no_full_text']}")
    print(f"  - No references: {stats['low_refs']}")
    print(f"  - Missing tables field: {stats['no_tables_field']}")
    print(f"  - Missing figures field: {stats['no_figures_field']}")
    print(f"  - Missing abstract: {stats['missing_abstract']}")
    print(f"  - Low section count (<3): {stats['low_sections']}")
    
    if bad:
        print(f"\n=== PROBLEMATIC FILES (showing first 25) ===")
        for name, reason in bad[:25]:
            print(f"  {name:60s} -> {reason}")
    else:
        print("\n✓ All files passed audit checks!")
    
    # Return success metrics
    success_rate = ((stats['files'] - len(set(n for n, _ in bad))) / stats['files'] * 100) if stats['files'] > 0 else 0
    print(f"\n=== OVERALL SUCCESS RATE: {success_rate:.1f}% ===")


def main():
    if len(sys.argv) > 1:
        root_dir = Path(sys.argv[1])
    else:
        root_dir = Path('out/rag_ready')
    
    if not root_dir.exists():
        print(f"Error: Directory {root_dir} does not exist")
        sys.exit(1)
    
    print(f"Auditing files in: {root_dir}\n")
    audit_files(root_dir)


if __name__ == '__main__':
    main()