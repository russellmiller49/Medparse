#!/usr/bin/env python3
import json, sys
from pathlib import Path

def main(summary_path: str):
    s = json.loads(Path(summary_path).read_text(encoding='utf-8'))
    gates = {
        'missing_doi': int(os.getenv('GATE_MISSING_DOI', '0')),
        'missing_journal': int(os.getenv('GATE_MISSING_JOURNAL', '0')),
        'missing_year': int(os.getenv('GATE_MISSING_YEAR', '0')),
        'missing_title': int(os.getenv('GATE_MISSING_TITLE', '0')),
        'empty_authors': int(os.getenv('GATE_EMPTY_AUTHORS', '0')),
    }
    failures = []
    for k, limit in gates.items():
        val = int(s.get(k, 0))
        if val > limit:
            failures.append(f"{k}={val} > {limit}")
    if failures:
        print('CI gate failed:', ', '.join(failures))
        sys.exit(1)
    print('CI gates passed.')
    return 0

if __name__ == '__main__':
    import os
    if len(sys.argv) < 2:
        print('Usage: ci_gate.py out/reports_ci/quality_summary.json')
        sys.exit(2)
    sys.exit(main(sys.argv[1]))

