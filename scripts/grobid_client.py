import httpx
from typing import Dict
from .utils import robust_api_call

class Grobid:
    def __init__(self, url: str = "http://localhost:8070", timeout: int = 90):
        self.base = url.rstrip("/")
        self.cli = httpx.Client(timeout=timeout)

    @robust_api_call()
    def process_fulltext(self, pdf_path: str) -> Dict:
        with open(pdf_path, "rb") as f:
            r = self.cli.post(f"{self.base}/api/processFulltextDocument",
                              files={"input": (pdf_path, f, "application/pdf")},
                              data={"consolidateHeader":"1","consolidateCitations":"1"})
        r.raise_for_status()
        return {"tei_xml": r.text}

    @robust_api_call()
    def process_biblio(self, pdf_path: str) -> Dict:
        with open(pdf_path, "rb") as f:
            r = self.cli.post(f"{self.base}/api/processReferences",
                              files={"input": (pdf_path, f, "application/pdf")})
        r.raise_for_status()
        return {"references_tei": r.text}