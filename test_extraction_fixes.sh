#!/bin/bash
# Test extraction fixes on a sample file

echo "Testing extraction fixes on sample PDF..."
echo "========================================="

# Process one file with the new fixes
python scripts/process_one.py \
    --pdf "input/AMPLE2.pdf" \
    --out "output/ample2_test.json" \
    --linker umls

# Validate the output
echo ""
echo "Running validation..."
python scripts/validate_extraction.py output/ample2_test.json --verbose

echo ""
echo "Checking for specific fixes:"
echo "-----------------------------"

# Check if grant IDs are in statistics (they shouldn't be)
echo -n "Grant IDs in statistics: "
python -c "
import json
with open('output/ample2_test.json') as f:
    doc = json.load(f)
stats = doc.get('statistics', [])
grant_patterns = ['U54HL', 'R01', 'NIH']
found = False
for stat in stats:
    if isinstance(stat, dict):
        text = str(stat.get('text', ''))
        if any(p in text for p in grant_patterns):
            print(f'FOUND: {text}')
            found = True
if not found:
    print('NONE (Good!)')
"

# Check for 'history of three' type links
echo -n "Suspicious UMLS links: "
python -c "
import json
with open('output/ample2_test.json') as f:
    doc = json.load(f)
links = doc.get('umls_links', [])
suspicious = ['history of', 'one', 'two', 'three', 'four', 'five']
found = False
for link in links:
    if isinstance(link, dict):
        text = link.get('text', '').lower()
        if any(s in text for s in suspicious):
            print(f'FOUND: {text}')
            found = True
if not found:
    print('NONE (Good!)')
"

# Check if authors are present
echo -n "Authors present: "
python -c "
import json
with open('output/ample2_test.json') as f:
    doc = json.load(f)
authors = doc.get('metadata', {}).get('authors', [])
if authors:
    print(f'YES ({len(authors)} authors)')
else:
    print('NO')
"

# Check if captions are linked
echo -n "Tables with captions: "
python -c "
import json
with open('output/ample2_test.json') as f:
    doc = json.load(f)
assets = doc.get('assets', {})
tables = assets.get('tables', [])
with_captions = sum(1 for t in tables if t.get('captions'))
print(f'{with_captions}/{len(tables)}')
"

echo ""
echo "Test complete!"