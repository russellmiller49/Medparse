# Docling API Changes - Version 2.48.0

## Important API Changes

### Old API (pre-2.0)
```python
from docling.document_converter import DocumentConverter
converter = DocumentConverter()
result = converter.convert("file.pdf")
data = result.to_dict()  # OLD METHOD
```

### New API (2.48.0+)
```python
from docling.document_converter import DocumentConverter
converter = DocumentConverter()
result = converter.convert("file.pdf")
data = result.model_dump()  # NEW METHOD - uses Pydantic model
```

## Key Changes
1. **Method name change**: `.to_dict()` → `.model_dump()`
2. **Reason**: Docling now uses Pydantic models for data structures
3. **Compatibility**: Not backwards compatible - must update code for 2.48.0+

## CLI Usage
Docling 2.48.0+ also provides a CLI interface:
```bash
docling input.pdf --to json --output output_dir
```

## Migration Notes
- When upgrading from older versions, search and replace all `.to_dict()` with `.model_dump()`
- The structure of the returned data remains largely the same
- Import path `from docling.document_converter import DocumentConverter` remains valid

## Version Check
```python
import docling
print(docling.__version__)  # Should show 2.48.0 or higher
```

## Affected Files in This Project
- `scripts/process_one.py` - Line 42: Changed from `.to_dict()` to `.model_dump()`

---
*Note: This change was discovered and fixed during debugging on 2024. The medparse-docling project now uses the correct API for docling 2.48.0+*