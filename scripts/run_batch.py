from pathlib import Path
from subprocess import run
from tqdm import tqdm
from scripts.env_loader import load_env

def main(inp="input", out_root="out", linker="umls"):
    env = load_env()
    json_dir = Path(out_root) / f"json_{linker}"
    json_dir.mkdir(parents=True, exist_ok=True)
    
    pdfs = sorted(Path(inp).glob("*.pdf"))
    for pdf in tqdm(pdfs, desc=f"Batch[{linker}]"):
        out_json = json_dir / f"{pdf.stem}.json"
        cmd = [
            "python", "scripts/process_one.py",
            "--pdf", str(pdf),
            "--out", str(out_json),
            "--linker", linker
        ]
        run(cmd, check=True)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="input")
    ap.add_argument("--out_root", default="out")
    ap.add_argument("--linker", choices=["umls","scispacy","quickumls"], default="umls")
    a = ap.parse_args()
    main(inp=a.input, out_root=a.out_root, linker=a.linker)