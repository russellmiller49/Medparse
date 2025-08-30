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