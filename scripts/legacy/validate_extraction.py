#!/usr/bin/env python3
"""
Validation report for extraction quality metrics.
"""
import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import Counter

# Content mirrored from previous location (now marked legacy)
from scripts.legacy.validate_batch_results import validate_json_file  # not used; kept for context

def validate_extraction(doc: Dict[str, Any]) -> Dict[str, Any]:
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
    if 'metadata' in doc:
        report['has_metadata'] = True
        metadata = doc['metadata']
        authors = metadata.get('authors', [])
        valid_authors = [a for a in authors if isinstance(a, str) and a.strip()]
        report['has_authors'] = len(valid_authors) > 0
        report['metrics']['n_authors'] = len(valid_authors)
        title = metadata.get('title', '')
        report['has_title'] = bool(title and title.strip())
        abstract = metadata.get('abstract', '')
        report['has_abstract'] = bool(abstract and len(abstract) > 100)
    if 'structure' in doc:
        structure = doc['structure']
        sections = structure.get('sections', [])
        report['has_sections'] = len(sections) > 0
        report['metrics']['n_sections'] = len(sections)
        tables = structure.get('tables', [])
        figures = structure.get('figures', [])
        report['metrics']['n_tables'] = len(tables)
        report['metrics']['n_figures'] = len(figures)
    if 'statistics' in doc:
        stats = doc['statistics']
        report['has_statistics'] = len(stats) > 0
        report['metrics']['n_statistics'] = len(stats)
        for stat in stats:
            if isinstance(stat, dict):
                text = stat.get('text', '')
                if any(p in text for p in ['NIH', 'NSF', 'DOD', 'R01', 'U54']):
                    report['issues'].append(f"Possible grant ID in statistics: {text}")
                if isinstance(stat.get('value'), list) and len(stat['value']) == 2:
                    vals = stat['value']
                    if all(isinstance(v, (int, float)) and 1 <= v <= 500 for v in vals):
                        if 'CI' not in text.upper():
                            report['warnings'].append(f"Possible citation in statistics: {text}")
    if 'umls_links' in doc:
        links = doc['umls_links']
        report['has_filtered_umls'] = True
        report['metrics']['n_umls_links'] = len(links)
        for link in links:
            if isinstance(link, dict):
                text = link.get('text', '').lower()
                if 'history of' in text and any(n in text for n in ['one', 'two', 'three', 'four', 'five']):
                    report['issues'].append(f"Suspicious UMLS link: {link.get('text')}")
    if 'assets' in doc:
        assets = doc['assets']
        if 'tables' in assets:
            tables_with_captions = sum(1 for t in assets['tables'] if t.get('captions'))
            if assets['tables']:
                caption_rate = tables_with_captions / len(assets['tables'])
                report['metrics']['table_caption_rate'] = caption_rate
                report['has_captions'] = caption_rate > 0.5
        if 'figures' in assets:
            figures_with_captions = sum(1 for f in assets['figures'] if f.get('captions'))
            if assets['figures']:
                caption_rate = figures_with_captions / len(assets['figures'])
                report['metrics']['figure_caption_rate'] = caption_rate
    if 'references' in doc or ('metadata' in doc and 'references' in doc['metadata']):
        refs = doc.get('references', doc.get('metadata', {}).get('references', []))
        report['has_references'] = len(refs) > 0
        report['metrics']['n_references'] = len(refs)
    quality_score = sum([
        report['has_metadata'] * 10,
        report['has_authors'] * 15,
        report['has_title'] * 15,
        report['has_abstract'] * 10,
        report['has_sections'] * 10,
        report['has_statistics'] * 10,
        report['has_filtered_umls'] * 10,
        report['has_captions'] * 10,
        report['has_references'] * 10
    ])
    report['quality_score'] = quality_score
    report['quality_grade'] = 'A' if quality_score >= 90 else 'B' if quality_score >= 75 else 'C' if quality_score >= 60 else 'D' if quality_score >= 40 else 'F'
    report['extraction_quality'] = 'enhanced' if doc.get('validation', {}).get('extraction_quality') == 'enhanced' else 'standard'
    return report

def pretty_print_report(report: Dict[str, Any], file_name: str = "") -> None:
    print("\n" + "="*60)
    print(f"Validation Report: {file_name}" if file_name else "Validation Report")
    print("="*60)
    print("\n✓ Completeness Checks:")
    checks = [('Metadata', report['has_metadata']),('Authors', report['has_authors']),('Title', report['has_title']),('Abstract', report['has_abstract']),('Sections', report['has_sections']),('Statistics', report['has_statistics']),('UMLS Links', report['has_filtered_umls']),('Captions', report['has_captions']),('References', report['has_references'])]
    for name, passed in checks:
        print(f"  {'✓' if passed else '✗'} {name}")
    print(f"\nQuality Score: {report['quality_score']}/100 (Grade: {report['quality_grade']})")
    print(f"Extraction Quality: {report['extraction_quality']}")
    if report['metrics']:
        print("\n📊 Metrics:")
        for k,v in report['metrics'].items():
            print(f"  • {k}: {v if not isinstance(v,float) else f'{v:.2f}'}")
    if report['issues']:
        print("\n⚠️ Issues:")
        for issue in report['issues']:
            print(f"  • {issue}")
    if report['warnings']:
        print("\n⚡ Warnings:")
        for w in report['warnings']:
            print(f"  • {w}")
    print("="*60)

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Validate extraction quality")
    parser.add_argument("path", help="JSON file or directory to validate")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()
    path = Path(args.path)
    if path.is_file():
        with open(path) as f:
            doc = json.load(f)
        report = validate_extraction(doc)
        pretty_print_report(report, path.name)
        sys.exit(0 if report['quality_score'] >= 60 else 1)
    elif path.is_dir():
        json_files = list(path.glob("*.json"))
        if not json_files:
            print(f"No JSON files found in {path}")
            sys.exit(1)
        reports = []
        quality_scores = []
        for json_file in sorted(json_files):
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
                    print(f"{json_file.name}: Score={report['quality_score']}/100 Grade={report['quality_grade']}")
            except Exception as e:
                print(f"Error validating {json_file.name}: {e}")
                continue
        if args.summary and reports:
            print("\n" + "="*60)
            print("SUMMARY")
            print("="*60)
            print(f"Files validated: {len(reports)}")
            print(f"Average quality score: {sum(quality_scores)/len(quality_scores):.1f}")
            grades = Counter(r[1]['quality_grade'] for r in reports)
            print("\nGrade distribution:")
            for grade in ['A','B','C','D','F']:
                print(f"  {grade}: {grades.get(grade,0)} files")
    else:
        print(f"Error: {path} is neither a file nor a directory")
        sys.exit(1)

if __name__ == "__main__":
    main()

