#!/usr/bin/env python3
"""
List all articles with missing abstracts from cleaned JSON files.
"""
import json
import sys
from pathlib import Path

def find_missing_abstracts(root_dir: Path):
    """Find all files with missing abstracts."""
    
    missing_abstracts = []
    total_files = 0
    
    for p in sorted(root_dir.glob('*.json')):
        if p.name.endswith('_chunks.json'):
            continue
        
        total_files += 1
        
        try:
            with p.open('r', encoding='utf-8') as f:
                doc = json.load(f)
            
            metadata = doc.get('metadata', {})
            if not metadata.get('abstract'):
                # Get additional info for context
                title = metadata.get('title', 'No title')
                doi = metadata.get('doi', 'No DOI')
                year = metadata.get('year', 'Unknown year')
                missing_abstracts.append({
                    'filename': p.name,
                    'title': title,
                    'doi': doi,
                    'year': year
                })
                
        except Exception as e:
            print(f"Error processing {p.name}: {e}", file=sys.stderr)
    
    return missing_abstracts, total_files


def main():
    if len(sys.argv) > 1:
        root_dir = Path(sys.argv[1])
    else:
        root_dir = Path('out/rag_ready_fixed')
    
    if not root_dir.exists():
        print(f"Error: Directory {root_dir} does not exist")
        sys.exit(1)
    
    print(f"Scanning files in: {root_dir}\n")
    missing, total = find_missing_abstracts(root_dir)
    
    print(f"=== ARTICLES WITH MISSING ABSTRACTS ===")
    print(f"Found {len(missing)} articles without abstracts out of {total} total files\n")
    
    # Sort by year then title
    missing.sort(key=lambda x: (x['year'], x['title']))
    
    # Print in a formatted table
    print(f"{'#':<4} {'Year':<6} {'Filename':<70} {'Title':<80}")
    print("-" * 160)
    
    for i, article in enumerate(missing, 1):
        title_short = article['title'][:77] + "..." if len(article['title']) > 80 else article['title']
        filename_short = article['filename'][:67] + "..." if len(article['filename']) > 70 else article['filename']
        print(f"{i:<4} {article['year']:<6} {filename_short:<70} {title_short:<80}")
    
    # Save to file
    output_file = root_dir / "missing_abstracts.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"Articles with Missing Abstracts\n")
        f.write(f"Directory: {root_dir}\n")
        f.write(f"Total: {len(missing)} out of {total} files\n")
        f.write("=" * 80 + "\n\n")
        
        for i, article in enumerate(missing, 1):
            f.write(f"{i}. {article['filename']}\n")
            f.write(f"   Title: {article['title']}\n")
            f.write(f"   Year: {article['year']}\n")
            f.write(f"   DOI: {article['doi']}\n")
            f.write("\n")
    
    print(f"\n✓ Full list saved to: {output_file}")


if __name__ == '__main__':
    main()