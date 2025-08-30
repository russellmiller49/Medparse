import os
from dotenv import load_dotenv

def load_env():
    load_dotenv()
    return {
        "UMLS_API_KEY": os.getenv("UMLS_API_KEY"),
        "NCBI_API_KEY": os.getenv("NCBI_API_KEY"),
        "NCBI_EMAIL": os.getenv("NCBI_EMAIL"),
        "GROBID_URL": os.getenv("GROBID_URL", "http://localhost:8070"),
        "QUICKUMLS_PATH": os.getenv("QUICKUMLS_PATH")
    }