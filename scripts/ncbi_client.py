from __future__ import annotations
import os
import httpx
from typing import Dict, Optional
from .utils import robust_api_call

BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"

class NCBIClient:
    """
    Minimal NCBI Entrez client for PubMed.
    Uses esearch -> efetch to resolve PMIDs and pull XML.
    """
    def __init__(self, api_key: str, email: Optional[str] = None, tool: str = "medparse-docling", timeout: int = 30):
        self.api_key = api_key
        self.email = email or os.getenv("NCBI_EMAIL")
        self.tool = tool
        self.cli = httpx.Client(timeout=timeout)

    def _common(self) -> Dict[str, str]:
        q = {"api_key": self.api_key, "tool": self.tool}
        if self.email:
            q["email"] = self.email
        return q

    @robust_api_call()
    def esearch_pubmed(self, term: str, retmax: int = 3) -> str:
        params = {"db": "pubmed", "term": term, "retmax": str(retmax), **self._common()}
        r = self.cli.get(BASE + "esearch.fcgi", params=params)
        r.raise_for_status()
        return r.text

    @robust_api_call()
    def efetch_pubmed(self, pmids: str) -> str:
        params = {"db": "pubmed", "id": pmids, "retmode": "xml", **self._common()}
        r = self.cli.get(BASE + "efetch.fcgi", params=params)
        r.raise_for_status()
        return r.text