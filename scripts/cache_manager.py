import hashlib, pickle
from pathlib import Path
from typing import Any, Optional, Dict

class CacheManager:
    def __init__(self, cache_dir: Path = Path("cache")):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_key(self, prefix: str, content: str) -> str:
        # Clean content to avoid filesystem issues
        clean_content = content.strip()
        return f"{prefix}_{hashlib.md5(clean_content.encode()).hexdigest()}"

    def get(self, key: str) -> Optional[Any]:
        # Sanitize key for filesystem
        safe_key = hashlib.md5(key.encode()).hexdigest()
        p = self.cache_dir / f"{safe_key}.pkl"
        if p.exists():
            with open(p, "rb") as f:
                return pickle.load(f)
        return None

    def set(self, key: str, value: Any) -> None:
        # Sanitize key for filesystem
        safe_key = hashlib.md5(key.encode()).hexdigest()
        p = self.cache_dir / f"{safe_key}.pkl"
        with open(p, "wb") as f:
            pickle.dump(value, f)

    def cache_umls_lookup(self, term: str, result: Dict) -> None:
        self.set(self._get_key("umls", term), result)

    def get_umls_lookup(self, term: str) -> Optional[Dict]:
        return self.get(self._get_key("umls", term))