# MedParse-Docling Quick Start Guide

Get up and running in 5 minutes! This guide provides the fastest path to processing your first medical PDF.

## 🚀 60-Second Setup

```bash
# 1. Clone and setup environment
git clone <repository-url> medparse-docling
cd medparse-docling
conda create -n medparse python=3.12 -y && conda activate medparse
pip install -r requirements.txt

# 2. Start GROBID (in another terminal)
docker run -d -p 8070:8070 lfoppiano/grobid:0.8.0

# 3. Configure API key
echo "UMLS_API_KEY=your_key_here" > .env
echo "GROBID_URL=http://localhost:8070" >> .env

# 4. Process your first PDF
cp your_paper.pdf input/
python scripts/run_batch.py --linker umls

# 5. View results
cat out/json_umls/your_paper.json | python -m json.tool | head -50
```

## 📋 Prerequisites Checklist

- [ ] Python 3.12 installed
- [ ] Docker installed and running
- [ ] UMLS account and API key ([Get one here](https://uts.nlm.nih.gov/uts/profile))
- [ ] At least 4GB RAM available
- [ ] Medical PDF files to process

## 🎯 Three Ways to Run

### Option 1: Simplest (UMLS only)
```bash
# Just need UMLS API key
echo "UMLS_API_KEY=your_key" > .env
python scripts/run_batch.py --linker umls
```

### Option 2: Fastest (QuickUMLS)
```bash
# Setup QuickUMLS (one-time)
pip install quickumls
# Download QuickUMLS data (see QuickUMLS docs)
echo "QUICKUMLS_PATH=/path/to/quickumls" >> .env
python scripts/run_batch.py --linker quickumls
```

### Option 3: Balanced (scispaCy)
```bash
# Setup scispaCy (one-time)
pip install scispacy spacy
python -m spacy download en_core_sci_md
python scripts/run_batch.py --linker scispacy
```

## 📁 Project Structure

```
medparse-docling/
├── input/          # ← Put your PDFs here
├── out/
│   ├── json_umls/  # ← JSON outputs appear here
│   ├── figures/    # ← Extracted figures
│   └── qa/         # ← Quality reports
├── scripts/        # Processing scripts
└── .env           # ← Your API keys
```

## 🔑 Get Your API Keys

### UMLS API Key (Required)
1. Go to https://uts.nlm.nih.gov/uts/
2. Sign up for free account
3. Login → My Profile → Edit Profile
4. Generate API Key
5. Add to `.env`: `UMLS_API_KEY=your_key_here`

### NCBI API Key (Optional, for references)
1. Go to https://www.ncbi.nlm.nih.gov/account/
2. Sign in → API Key Management
3. Create API Key
4. Add to `.env`: `NCBI_API_KEY=your_key_here`

## 💻 Essential Commands

### Process Single Paper
```bash
python scripts/process_one.py \
  --pdf input/paper.pdf \
  --out out/json_umls/paper.json \
  --linker umls
```

### Process All Papers
```bash
python scripts/run_batch.py --linker umls
```

### Compare Different Linkers
```bash
# Run all three
for linker in umls scispacy quickumls; do
  python scripts/run_batch.py --linker $linker
done

# Compare results
python scripts/compare_linkers.py --pdf_stems "paper1" "paper2"
```

### Check Processing Status
```bash
ls -la out/json_umls/  # See completed files
ls -la out/figures/    # See extracted figures
ls -la out/qa/         # See QA reports
```

## 📊 Understanding Output

### JSON Structure (Simplified)
```json
{
  "metadata": {
    "title": "Paper Title",
    "authors": ["Smith J", "Doe J"]
  },
  "umls_links": [
    {"phrase": "pneumonia", "cui": "C0032285"}
  ],
  "statistics": [
    {"type": "p_value", "value": 0.001}
  ],
  "drugs": [
    {"drug": "aspirin", "dosage": "100mg"}
  ],
  "validation": {
    "completeness_score": 88,
    "is_valid": true
  }
}
```

### Quick Analysis Commands
```bash
# Count UMLS concepts found
python -c "import json; d=json.load(open('out/json_umls/paper.json')); print(f'Found {len(d.get(\"umls_links\",[]))} concepts')"

# Extract all p-values
python -c "import json; d=json.load(open('out/json_umls/paper.json')); [print(s) for s in d.get('statistics',[])]"

# List all drugs
python -c "import json; d=json.load(open('out/json_umls/paper.json')); [print(drug) for drug in d.get('drugs',[])]"
```

## 🔧 Troubleshooting Quick Fixes

### GROBID Not Running?
```bash
# Check if running
curl http://localhost:8070/api/isalive
# If not, start it:
docker run -d -p 8070:8070 lfoppiano/grobid:0.8.0
```

### No UMLS Links Found?
```bash
# Test API key
curl -H "Authorization: apikey YOUR_KEY" \
  "https://uts-ws.nlm.nih.gov/rest/search/current?string=pneumonia"
```

### Processing Too Slow?
```bash
# Use local linker instead
python scripts/run_batch.py --linker scispacy
```

### Out of Memory?
```bash
# Process fewer files at once
mkdir input_subset
cp input/*.pdf input_subset/  # Copy just a few
python scripts/run_batch.py --input input_subset
```

## 📈 Next Steps

1. **Read Full Documentation**: See `DOCUMENTATION.md` for complete details
2. **Customize Configuration**: Edit `config/abbreviations_med.json` for your domain
3. **Set Up PubMed Enrichment**: Add NCBI API key for reference enhancement
4. **Explore Advanced Features**: Try the comparison pipeline for A/B testing
5. **Automate Processing**: Set up cron jobs or workflow automation

## 🚨 Quick Health Check

Run this to verify everything is working:

```bash
# Create test script
cat > test_setup.sh << 'EOF'
#!/bin/bash
echo "Checking setup..."

# Check Python
python --version || echo "❌ Python not found"

# Check Docker
docker --version || echo "❌ Docker not found"

# Check GROBID
curl -s http://localhost:8070/api/isalive || echo "❌ GROBID not running"

# Check environment
[ -f .env ] && echo "✅ .env exists" || echo "❌ .env missing"

# Check dependencies
python -c "import docling" && echo "✅ Docling installed" || echo "❌ Docling missing"

# Test run
if [ -f "input/*.pdf" ]; then
  echo "✅ PDFs found in input/"
else
  echo "⚠️  No PDFs in input/ folder"
fi

echo "Setup check complete!"
EOF
chmod +x test_setup.sh
./test_setup.sh
```

## 💡 Pro Tips

1. **Start Small**: Test with 1-2 PDFs first
2. **Use Cache**: Reprocessing is faster (cache in `cache/` folder)
3. **Monitor QA**: Check `out/qa/` for quality scores
4. **Batch by Type**: Group similar papers for better accuracy
5. **Save API Calls**: Use local linkers for experimentation

## 📞 Getting Help

- **Issues**: Check `TROUBLESHOOTING.md`
- **User Guide**: See `USER_GUIDE.md` for detailed workflows
- **API Reference**: See `API_REFERENCE.md` for function details
- **Examples**: Check `scripts/` folder for code examples

---

**Ready to process?** Drop your PDFs in `input/` and run:
```bash
python scripts/run_batch.py --linker umls
```

Results will appear in `out/json_umls/` within seconds! 🎉