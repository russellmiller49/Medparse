# MedParse-Docling Troubleshooting Guide

This guide covers common issues and their solutions. If your issue isn't listed here, please check the GitHub issues or create a new one.

## Table of Contents
1. [Installation Issues](#installation-issues)
2. [GROBID Problems](#grobid-problems)
3. [API Key Issues](#api-key-issues)
4. [Processing Errors](#processing-errors)
5. [Performance Issues](#performance-issues)
6. [Output Problems](#output-problems)
7. [Entity Linking Issues](#entity-linking-issues)
8. [Memory and Resource Issues](#memory-and-resource-issues)
9. [Docker Issues](#docker-issues)
10. [Debugging Tools](#debugging-tools)

---

## Installation Issues

### Problem: `ModuleNotFoundError: No module named 'docling'`

**Solution:**
```bash
pip install --upgrade pip
pip install docling
# If still fails, try:
pip install --no-cache-dir docling
```

### Problem: `error: Microsoft Visual C++ 14.0 is required` (Windows)

**Solution:**
1. Download Visual Studio Build Tools
2. Install "Desktop development with C++"
3. Restart terminal and retry installation

### Problem: Conflicting package versions

**Solution:**
```bash
# Create fresh environment
conda create -n medparse_fresh python=3.12 -y
conda activate medparse_fresh
pip install -r requirements.txt
```

### Problem: `spacy` model download fails

**Solution:**
```bash
# Direct download
pip install https://github.com/explosion/spacy-models/releases/download/en_core_sci_md-0.5.1/en_core_sci_md-0.5.1-py3-none-any.whl
# Or use proxy if behind firewall
pip install --proxy http://proxy.server:port spacy
python -m spacy download en_core_sci_md
```

---

## GROBID Problems

### Problem: `ConnectionError: Failed to connect to GROBID`

**Diagnosis:**
```bash
curl http://localhost:8070/api/isalive
```

**Solutions:**

1. **Start GROBID:**
```bash
docker run -d -p 8070:8070 lfoppiano/grobid:0.8.0
```

2. **Check if port is already in use:**
```bash
lsof -i :8070  # Linux/Mac
netstat -ano | findstr :8070  # Windows
```

3. **Use different port:**
```bash
docker run -d -p 8071:8070 lfoppiano/grobid:0.8.0
echo "GROBID_URL=http://localhost:8071" >> .env
```

### Problem: GROBID container keeps restarting

**Diagnosis:**
```bash
docker logs $(docker ps -a | grep grobid | awk '{print $1}')
```

**Solutions:**

1. **Insufficient memory:**
```bash
docker run -d -p 8070:8070 -m 4g lfoppiano/grobid:0.8.0
```

2. **Corrupted container:**
```bash
docker stop $(docker ps -a | grep grobid | awk '{print $1}')
docker rm $(docker ps -a | grep grobid | awk '{print $1}')
docker pull lfoppiano/grobid:0.8.0
docker run -d -p 8070:8070 lfoppiano/grobid:0.8.0
```

### Problem: GROBID processing timeout

**Solution:**
```python
# Increase timeout in scripts/grobid_client.py
class Grobid:
    def __init__(self, url="http://localhost:8070", timeout=180):  # Increase from 90
```

---

## API Key Issues

### Problem: `UMLS API authentication failed`

**Diagnosis:**
```bash
# Test API key
curl -H "Authorization: apikey YOUR_KEY" \
  "https://uts-ws.nlm.nih.gov/rest/search/current?string=test"
```

**Solutions:**

1. **Verify key is active:**
   - Login to https://uts.nlm.nih.gov/uts/
   - Go to My Profile → Edit Profile
   - Check API Key status

2. **Check .env format:**
```bash
# Correct format (no quotes)
UMLS_API_KEY=abcd1234-5678-90ef-ghij-klmnopqrstuv
# Wrong format
UMLS_API_KEY="abcd1234-5678-90ef-ghij-klmnopqrstuv"
```

3. **Regenerate key:**
   - Delete old key in UTS profile
   - Generate new key
   - Update .env file

### Problem: `NCBI API rate limit exceeded`

**Solution:**
```bash
# Add API key to increase rate limit
echo "NCBI_API_KEY=your_ncbi_key" >> .env
echo "NCBI_EMAIL=your@email.com" >> .env
```

Without key: 3 requests/second
With key: 10 requests/second

### Problem: Environment variables not loading

**Diagnosis:**
```python
python -c "from scripts.env_loader import load_env; print(load_env())"
```

**Solutions:**

1. **Check .env location:**
```bash
ls -la .env  # Should be in project root
pwd  # Verify you're in medparse-docling/
```

2. **Fix permissions:**
```bash
chmod 644 .env
```

3. **Manual export:**
```bash
export UMLS_API_KEY=your_key
export GROBID_URL=http://localhost:8070
```

---

## Processing Errors

### Problem: `No sections extracted from PDF`

**Causes & Solutions:**

1. **Scanned PDF (image only):**
```bash
# Check if PDF has text
pdftotext input/paper.pdf - | head
# If empty, PDF is scanned. Solution: OCR it first
```

2. **Corrupted PDF:**
```bash
# Try to repair
gs -o fixed.pdf -sDEVICE=pdfwrite -dPDFSETTINGS=/prepress corrupted.pdf
```

3. **Non-standard structure:**
   - Check if PDF opens correctly in viewer
   - Try different Docling configuration

### Problem: `No UMLS links found`

**Diagnosis:**
```python
# Test UMLS directly
from scripts.umls_linker import UMLSClient
client = UMLSClient(api_key="your_key")
results = client.search_term("pneumonia")
print(results)
```

**Solutions:**

1. **Non-medical content:**
   - UMLS only links medical terms
   - Check if document is medical

2. **Abbreviations not expanded:**
   - Add to `config/abbreviations_med.json`

3. **Too restrictive filtering:**
   - Check stoplist in `postprocess.py`

### Problem: `JSONDecodeError` when reading output

**Solution:**
```bash
# Validate JSON
python -m json.tool out/json_umls/paper.json
# If fails, regenerate
rm out/json_umls/paper.json
python scripts/process_one.py --pdf input/paper.pdf --out out/json_umls/paper.json --linker umls
```

---

## Performance Issues

### Problem: Processing is very slow

**Diagnosis:**
```bash
time python scripts/process_one.py --pdf input/test.pdf --out test.json --linker umls
```

**Solutions:**

1. **Use local linkers:**
```bash
python scripts/run_batch.py --linker scispacy  # Faster
python scripts/run_batch.py --linker quickumls  # Fastest
```

2. **Enable caching:**
```bash
# Cache is automatic, verify it's working
ls -la cache/*.pkl
```

3. **Process in parallel:**
```bash
# Create parallel processing script
cat > parallel_batch.py << 'EOF'
from multiprocessing import Pool
from pathlib import Path
import subprocess

def process_one(pdf):
    cmd = ["python", "scripts/process_one.py", 
           "--pdf", str(pdf), 
           "--out", f"out/json_umls/{pdf.stem}.json",
           "--linker", "umls"]
    subprocess.run(cmd)
    return pdf.name

if __name__ == "__main__":
    pdfs = list(Path("input").glob("*.pdf"))
    with Pool(4) as pool:  # Adjust number of workers
        results = pool.map(process_one, pdfs)
    print(f"Processed {len(results)} PDFs")
EOF
python parallel_batch.py
```

### Problem: High CPU usage

**Solution:**
```python
# Limit parallelism in config/docling_medical_config.yaml
options:
  parallelism: 4  # Reduce from 8
```

---

## Output Problems

### Problem: Missing figures in output

**Diagnosis:**
```python
# Check if figures detected
import json
data = json.load(open("out/json_umls/paper.json"))
print(f"Figures found: {len(data['structure']['figures'])}")
```

**Solutions:**

1. **No bounding boxes:**
```python
# Check Docling config includes bbox
pipeline:
  - enrich.figures:
      include_bboxes: true
```

2. **Embedded images:**
   - Some PDFs have images as background
   - Try different PDF tool to extract

### Problem: Incomplete references

**Solutions:**

1. **GROBID issue:**
```bash
# Try biblio-only processing
curl -X POST -F "input=@input/paper.pdf" \
  http://localhost:8070/api/processReferences > refs.xml
```

2. **Enhance with NCBI:**
```bash
echo "NCBI_API_KEY=your_key" >> .env
echo "NCBI_EMAIL=your@email.com" >> .env
```

### Problem: Wrong section classification

**Solution:**
Edit `scripts/section_classifier.py` to add custom rules:
```python
def classify_section(title):
    title_lower = title.lower()
    # Add custom patterns
    if "statistical" in title_lower:
        return "methods"
    # ... existing code
```

---

## Entity Linking Issues

### Problem: scispaCy not finding entities

**Diagnosis:**
```python
import spacy
nlp = spacy.load("en_core_sci_md")
doc = nlp("Patient with pneumonia and diabetes")
print([(ent.text, ent.label_) for ent in doc.ents])
```

**Solutions:**

1. **Model not installed:**
```bash
pip install scispacy
python -m spacy download en_core_sci_md
```

2. **Text too long:**
```python
# Increase max length in local_linkers.py
nlp.max_length = 1000000  # Default is 500000
```

### Problem: QuickUMLS initialization error

**Solutions:**

1. **Invalid path:**
```bash
# Verify QuickUMLS data exists
ls -la /path/to/quickumls/data
# Should contain: umls-data.db, etc.
```

2. **Rebuild index:**
```bash
python -m quickumls.install /path/to/UMLS/data /path/to/quickumls/output
```

### Problem: Different results between linkers

This is **expected behavior**. Each linker has different:
- Coverage (UMLS > QuickUMLS > scispaCy)
- Accuracy (UMLS > scispaCy > QuickUMLS)
- Speed (QuickUMLS > scispaCy > UMLS)

Use comparison tool to analyze:
```bash
python scripts/compare_linkers.py --pdf_stems "paper_name"
```

---

## Memory and Resource Issues

### Problem: `MemoryError` or `killed` process

**Diagnosis:**
```bash
# Check available memory
free -h  # Linux
vm_stat  # Mac
# Monitor during processing
top -p $(pgrep -f process_one.py)
```

**Solutions:**

1. **Process smaller batches:**
```bash
# Process one at a time
for pdf in input/*.pdf; do
    python scripts/process_one.py --pdf "$pdf" \
      --out "out/json_umls/$(basename ${pdf%.pdf}).json" \
      --linker umls
    sleep 2  # Give system time to recover
done
```

2. **Reduce memory usage:**
```python
# In process_one.py, process text in chunks
def process_in_chunks(text, chunk_size=100000):
    chunks = [text[i:i+chunk_size] 
              for i in range(0, len(text), chunk_size)]
    results = []
    for chunk in chunks:
        results.extend(process_chunk(chunk))
    return results
```

3. **Increase swap space:**
```bash
# Linux
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

### Problem: Disk space issues

**Solutions:**

1. **Clear cache:**
```bash
rm -rf cache/*.pkl
```

2. **Remove temporary files:**
```bash
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -delete
```

3. **Archive old outputs:**
```bash
tar -czf outputs_backup.tar.gz out/
rm -rf out/json_*
```

---

## Docker Issues

### Problem: `Cannot connect to Docker daemon`

**Solutions:**

1. **Start Docker:**
```bash
# Linux
sudo systemctl start docker
# Mac
open -a Docker
# Windows
# Start Docker Desktop
```

2. **Add user to docker group (Linux):**
```bash
sudo usermod -aG docker $USER
newgrp docker
```

### Problem: `docker: Error response from daemon: port is already allocated`

**Solution:**
```bash
# Find what's using the port
docker ps --filter "publish=8070"
# Stop it
docker stop <container_id>
# Or use different port
docker run -d -p 8071:8070 lfoppiano/grobid:0.8.0
```

---

## Debugging Tools

### Enable Debug Logging

```bash
# Set environment variable
export LOGURU_LEVEL=DEBUG
python scripts/process_one.py --pdf input/test.pdf --out debug.json --linker umls
```

### Profile Performance

```python
# Create profiling script
cat > profile_run.py << 'EOF'
import cProfile
import pstats
from pathlib import Path
from scripts.process_one import process_pdf

def run():
    process_pdf(
        Path("input/test.pdf"),
        Path("profile_output.json"),
        Path("config/docling_medical_config.yaml"),
        "umls"
    )

cProfile.run('run()', 'profile_stats')
stats = pstats.Stats('profile_stats')
stats.sort_stats('cumulative')
stats.print_stats(20)
EOF
python profile_run.py
```

### Test Individual Components

```python
# Test script for components
cat > test_components.py << 'EOF'
#!/usr/bin/env python
import sys
from pathlib import Path

def test_imports():
    try:
        import docling
        print("✅ Docling imported")
    except Exception as e:
        print(f"❌ Docling import failed: {e}")
    
    try:
        import spacy
        print("✅ spaCy imported")
    except Exception as e:
        print(f"❌ spaCy import failed: {e}")

def test_grobid():
    import httpx
    try:
        r = httpx.get("http://localhost:8070/api/isalive")
        print(f"✅ GROBID responding: {r.text}")
    except Exception as e:
        print(f"❌ GROBID not responding: {e}")

def test_env():
    from scripts.env_loader import load_env
    env = load_env()
    if env.get("UMLS_API_KEY"):
        print("✅ UMLS key loaded")
    else:
        print("❌ UMLS key not found")

if __name__ == "__main__":
    test_imports()
    test_grobid()
    test_env()
EOF
python test_components.py
```

### Check System Resources

```bash
# Create system check script
cat > check_system.sh << 'EOF'
#!/bin/bash
echo "=== System Resources ==="
echo "CPU Cores: $(nproc)"
echo "Memory: $(free -h | grep Mem | awk '{print $2}')"
echo "Disk Space: $(df -h . | tail -1 | awk '{print $4}')"
echo ""
echo "=== Python Environment ==="
python --version
pip --version
echo "Installed packages: $(pip list | wc -l)"
echo ""
echo "=== Docker Status ==="
docker --version
docker ps | grep grobid
echo ""
echo "=== Network Connectivity ==="
curl -s -o /dev/null -w "%{http_code}" https://uts-ws.nlm.nih.gov && echo "✅ UMLS API reachable" || echo "❌ UMLS API unreachable"
curl -s -o /dev/null -w "%{http_code}" https://eutils.ncbi.nlm.nih.gov && echo "✅ NCBI API reachable" || echo "❌ NCBI API unreachable"
EOF
chmod +x check_system.sh
./check_system.sh
```

---

## Getting Additional Help

1. **Check logs:**
```bash
# Save all output to file
python scripts/process_one.py --pdf input/test.pdf --out test.json --linker umls 2>&1 | tee debug.log
```

2. **Create minimal reproducible example:**
```python
# Isolate the problem
from scripts.grobid_client import Grobid
g = Grobid()
result = g.process_fulltext("input/test.pdf")
print(result)
```

3. **Report issue with details:**
   - OS and Python version
   - Error message and stack trace
   - Steps to reproduce
   - Sample PDF (if possible)

4. **Community resources:**
   - GitHub Issues
   - Stack Overflow (tag: docling, grobid, umls)
   - Medical NLP forums