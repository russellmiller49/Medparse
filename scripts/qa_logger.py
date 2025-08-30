import json, time
from pathlib import Path
from typing import Dict, Any

def write_qa(qa_dir: Path, pdf_name: str, stats: Dict[str, Any]) -> None:
    qa_dir.mkdir(parents=True, exist_ok=True)
    stats.update({"timestamp": time.strftime("%Y-%m-%d %H:%M:%S")})
    with open(qa_dir / f"{pdf_name}.qa.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)