#!/usr/bin/env python3
"""
Validation report for extraction quality metrics.
"""
import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import Counter

def validate_extraction(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate extraction quality and completeness.
    
    Returns dict with metrics and issues found.
    """
    report = {
        'has_metadata': False,
        'has_authors': False,
        'has_title': False,
        'has_abstract': False,
        'has_sections': False,
        'has_statistics': False,
        'has_filtered_umls': False,
        'has_captions': False,
        'has_references': False,
        'issues': [],
        'warnings': [],
        'metrics': {}
    }
    
    # Check metadata
    if 'metadata' in doc:
        report['has_metadata'] = True
        metadata = doc['metadata']
        
        # Check authors
        authors = metadata.get('authors', [])
        valid_authors = [a for a in authors if isinstance(a, str) and a.strip()]
        report['has_authors'] = len(valid_authors) > 0
        report['metrics']['n_authors'] = len(valid_authors)
        
        # Check title
        title = metadata.get('title', '')
        report['has_title'] = bool(title and title.strip())
        
        # Check abstract
        abstract = metadata.get('abstract', '')
        report['has_abstract'] = bool(abstract and len(abstract) > 100)
    
    # Check structure
    if 'structure' in doc:
        structure = doc['structure']
        
        # Check sections
        sections = structure.get('sections', [])
        report['has_sections'] = len(sections) > 0
        report['metrics']['n_sections'] = len(sections)
        
        # Check tables and figures
        tables = structure.get('tables', [])
        figures = structure.get('figures', [])
        report['metrics']['n_tables'] = len(tables)
        report['metrics']['n_figures'] = len(figures)
    
    # Check statistics
    if 'statistics' in doc:
        stats = doc['statistics']
        report['has_statistics'] = len(stats) > 0
        report['metrics']['n_statistics'] = len(stats)
        
        # Check for suspicious statistics
        for stat in stats:
            if isinstance(stat, dict):
                text = stat.get('text', '')
                # Check for grant patterns
                if any(p in text for p in ['NIH', 'NSF', 'DOD', 'R01', 'U54']):
                    report['issues'].append(f"Possible grant ID in statistics: {text}")
                
                # Check for citation patterns
                if isinstance(stat.get('value'), list) and len(stat['value']) == 2:
                    vals = stat['value']
                    if all(isinstance(v, (int, float)) and 1 <= v <= 500 for v in vals):
                        if 'CI' not in text.upper():
                            report['warnings'].append(f"Possible citation in statistics: {text}")
    
    # Check UMLS links
    if 'umls_links' in doc:
        links = doc['umls_links']
        report['has_filtered_umls'] = True
        report['metrics']['n_umls_links'] = len(links)
        
        # Check for suspicious links
        for link in links:
            if isinstance(link, dict):
                text = link.get('text', '').lower()
                if 'history of' in text and any(n in text for n in ['one', 'two', 'three', 'four', 'five']):
                    report['issues'].append(f"Suspicious UMLS link: {link.get('text')}")
    
    # Check captions in assets
    if 'assets' in doc:
        assets = doc['assets']
        
        # Check table captions
        if 'tables' in assets:
            tables_with_captions = sum(1 for t in assets['tables'] if t.get('captions'))
            if assets['tables']:
                caption_rate = tables_with_captions / len(assets['tables'])
                report['metrics']['table_caption_rate'] = caption_rate
                report['has_captions'] = caption_rate > 0.5
        
        # Check figure captions
        if 'figures' in assets:
            figures_with_captions = sum(1 for f in assets['figures'] if f.get('captions'))
            if assets['figures']:
                caption_rate = figures_with_captions / len(assets['figures'])
                report['metrics']['figure_caption_rate'] = caption_rate
    
    # Check references
    if 'references' in doc or ('metadata' in doc and 'references' in doc['metadata']):
        refs = doc.get('references', doc.get('metadata', {}).get('references', []))
        report['has_references'] = len(refs) > 0
        report['metrics']['n_references'] = len(refs)
    
    # Calculate overall quality score
    quality_score = sum([
        report['has_metadata'] * 10,
        report['has_authors'] * 15,
        report['has_title'] * 10,
        report['has_abstract'] * 10,
        report['has_sections'] * 15,
        report['has_statistics'] * 10,
        report['has_filtered_umls'] * 10,
        report['has_captions'] * 10,
        report['has_references'] * 10
    ])
    report['quality_score'] = quality_score
    report['quality_grade'] = 'A' if quality_score >= 90 else 'B' if quality_score >= 75 else 'C' if quality_score >= 60 else 'D' if quality_score >= 40 else 'F'
    
    # Check for extraction enhancements
    report['extraction_quality'] = 'enhanced' if doc.get('validation', {}).get('extraction_quality') == 'enhanced' else 'standard'
    
    return report

def pretty_print_report(report: Dict[str, Any], file_name: str = "") -> None:
    """Pretty print validation report."""
    print("\n" + "="*60)
    if file_name:
        print(f"Validation Report: {file_name}")
    else:
        print("Validation Report")
    print("="*60)
    
    print("\n✓ Completeness Checks:")
    checks = [
        ('Metadata', report['has_metadata']),
        ('Authors', report['has_authors']),
        ('Title', report['has_title']),
        ('Abstract', report['has_abstract']),
        ('Sections', report['has_sections']),
        ('Statistics', report['has_statistics']),
        ('UMLS Links', report['has_filtered_umls']),
        ('Captions', report['has_captions']),
        ('References', report['has_references'])
    ]
    
    for name, passed in checks:
        status = "✓" if passed else "✗"
        print(f"  {status} {name}")
    
    print(f"\nQuality Score: {report['quality_score']}/100 (Grade: {report['quality_grade']})")
    print(f"Extraction Quality: {report['extraction_quality']}")
    
    if report['metrics']:
        print("\n📊 Metrics:")
        for key, value in report['metrics'].items():
            if isinstance(value, float):
                print(f"  • {key}: {value:.2f}")
            else:
                print(f"  • {key}: {value}")
    
    if report['issues']:
        print("\n⚠️ Issues:")
        for issue in report['issues']:
            print(f"  • {issue}")
    
    if report['warnings']:
        print("\n⚡ Warnings:")
        for warning in report['warnings']:
            print(f"  • {warning}")
    
    print("="*60)

def main():
    """Main validation function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate extraction quality")
    parser.add_argument("path", help="JSON file or directory to validate")
    parser.add_argument("--verbose", action="store_true", help="Show detailed output")
    parser.add_argument("--summary", action="store_true", help="Show summary for directory")
    args = parser.parse_args()
    
    path = Path(args.path)
    
    if path.is_file():
        # Validate single file
        with open(path) as f:
            doc = json.load(f)
        
        report = validate_extraction(doc)
        pretty_print_report(report, path.name)
        
        # Exit with error if quality is poor
        sys.exit(0 if report['quality_score'] >= 60 else 1)
        
    elif path.is_dir():
        # Validate all JSON files in directory
        json_files = list(path.glob("*.json"))
        
        if not json_files:
            print(f"No JSON files found in {path}")
            sys.exit(1)
        
        reports = []
        quality_scores = []
        
        for json_file in sorted(json_files):
            # Skip report files
            if 'report' in json_file.name.lower():
                continue
                
            try:
                with open(json_file) as f:
                    doc = json.load(f)
                
                report = validate_extraction(doc)
                reports.append((json_file.name, report))
                quality_scores.append(report['quality_score'])
                
                if args.verbose:
                    pretty_print_report(report, json_file.name)
                else:
                    grade = report['quality_grade']
                    print(f"{json_file.name}: Score={report['quality_score']}/100 Grade={grade}")
                    
            except Exception as e:
                print(f"Error validating {json_file.name}: {e}")
                continue
        
        if args.summary and reports:
            print("\n" + "="*60)
            print("SUMMARY")
            print("="*60)
            print(f"Files validated: {len(reports)}")
            print(f"Average quality score: {sum(quality_scores)/len(quality_scores):.1f}")
            
            # Count grades
            grades = Counter(r[1]['quality_grade'] for r in reports)
            print("\nGrade distribution:")
            for grade in ['A', 'B', 'C', 'D', 'F']:
                count = grades.get(grade, 0)
                print(f"  {grade}: {count} files")
            
            # Common issues
            all_issues = []
            for _, report in reports:
                all_issues.extend(report['issues'])
            
            if all_issues:
                print("\nMost common issues:")
                issue_counts = Counter(all_issues)
                for issue, count in issue_counts.most_common(5):
                    print(f"  • {issue} ({count} occurrences)")
    
    else:
        print(f"Error: {path} is neither a file nor a directory")
        sys.exit(1)

if __name__ == "__main__":
    main()