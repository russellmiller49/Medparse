#!/usr/bin/env python3
"""
Test script to randomly process 5 articles with UMLS linker
"""
import random
import sys
from pathlib import Path
from loguru import logger
import subprocess
import json
from datetime import datetime

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

def get_random_pdfs(input_dir: Path, n: int = 5) -> list[Path]:
    """Get n random PDFs from input directory"""
    all_pdfs = list(input_dir.glob("*.pdf"))
    if not all_pdfs:
        logger.error(f"No PDFs found in {input_dir}")
        return []
    
    # Sample up to n PDFs (or all if less than n available)
    sample_size = min(n, len(all_pdfs))
    selected = random.sample(all_pdfs, sample_size)
    
    logger.info(f"Selected {sample_size} random PDFs from {len(all_pdfs)} available")
    return selected

def process_single_pdf(pdf_path: Path, output_dir: Path) -> dict:
    """Process a single PDF and return results"""
    output_json = output_dir / f"{pdf_path.stem}.json"
    
    logger.info(f"Processing: {pdf_path.name}")
    
    # Build command
    cmd = [
        sys.executable,
        "scripts/process_one.py",
        "--pdf", str(pdf_path),
        "--out", str(output_json),
        "--linker", "umls"
    ]
    
    # Run processing
    start_time = datetime.now()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout per paper
        )
        elapsed = (datetime.now() - start_time).total_seconds()
        
        # Check if output was created
        success = output_json.exists()
        
        # Try to get some stats from the output
        stats = {}
        if success:
            try:
                with open(output_json) as f:
                    data = json.load(f)
                    stats = {
                        "n_sections": len(data.get("structure", {}).get("sections", [])),
                        "n_tables": len(data.get("structure", {}).get("tables", [])),
                        "n_figures": len(data.get("structure", {}).get("figures", [])),
                        "n_statistics": len(data.get("statistics", [])),
                        "n_umls_links": len(data.get("umls_links", [])),
                        "n_authors": len(data.get("metadata", {}).get("authors", [])),
                        "has_title": bool(data.get("metadata", {}).get("title")),
                        "file_size_mb": output_json.stat().st_size / (1024 * 1024)
                    }
            except Exception as e:
                logger.warning(f"Could not extract stats: {e}")
        
        return {
            "pdf": pdf_path.name,
            "success": success,
            "elapsed_seconds": elapsed,
            "output_file": str(output_json) if success else None,
            "stdout": result.stdout[-500:] if result.stdout else "",  # Last 500 chars
            "stderr": result.stderr[-500:] if result.stderr else "",
            "return_code": result.returncode,
            **stats
        }
        
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout processing {pdf_path.name}")
        return {
            "pdf": pdf_path.name,
            "success": False,
            "error": "Timeout after 5 minutes",
            "elapsed_seconds": 300
        }
    except Exception as e:
        logger.error(f"Error processing {pdf_path.name}: {e}")
        return {
            "pdf": pdf_path.name,
            "success": False,
            "error": str(e)
        }

def main():
    """Main test function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test random batch of PDFs with UMLS linker")
    parser.add_argument("--input", default="input", help="Input directory with PDFs")
    parser.add_argument("--output", default="out/test_batch_umls", help="Output directory")
    parser.add_argument("--n", type=int, default=5, help="Number of PDFs to process")
    parser.add_argument("--seed", type=int, help="Random seed for reproducibility")
    args = parser.parse_args()
    
    # Set random seed if provided
    if args.seed:
        random.seed(args.seed)
        logger.info(f"Using random seed: {args.seed}")
    
    input_dir = Path(args.input)
    output_dir = Path(args.output)
    
    if not input_dir.exists():
        logger.error(f"Input directory does not exist: {input_dir}")
        return 1
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Get random PDFs
    pdfs = get_random_pdfs(input_dir, args.n)
    if not pdfs:
        return 1
    
    logger.info("=" * 60)
    logger.info("Selected PDFs for testing:")
    for i, pdf in enumerate(pdfs, 1):
        logger.info(f"  {i}. {pdf.name}")
    logger.info("=" * 60)
    
    # Process each PDF
    results = []
    for i, pdf in enumerate(pdfs, 1):
        logger.info(f"\n[{i}/{len(pdfs)}] Processing {pdf.name}...")
        result = process_single_pdf(pdf, output_dir)
        results.append(result)
        
        # Quick summary
        if result["success"]:
            logger.success(f"✓ Completed in {result['elapsed_seconds']:.1f}s")
            if "n_sections" in result:
                logger.info(f"  → {result['n_sections']} sections, {result['n_tables']} tables, "
                          f"{result['n_figures']} figures, {result['n_statistics']} stats, "
                          f"{result['n_umls_links']} UMLS links")
        else:
            logger.error(f"✗ Failed: {result.get('error', 'Unknown error')}")
    
    # Summary report
    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY REPORT")
    logger.info("=" * 60)
    
    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]
    
    logger.info(f"Processed: {len(results)} PDFs")
    logger.info(f"Successful: {len(successful)}")
    logger.info(f"Failed: {len(failed)}")
    
    if successful:
        avg_time = sum(r["elapsed_seconds"] for r in successful) / len(successful)
        logger.info(f"Average processing time: {avg_time:.1f}s")
        
        # Stats summary
        if any("n_statistics" in r for r in successful):
            avg_stats = sum(r.get("n_statistics", 0) for r in successful) / len(successful)
            avg_umls = sum(r.get("n_umls_links", 0) for r in successful) / len(successful)
            logger.info(f"Average statistics extracted: {avg_stats:.1f}")
            logger.info(f"Average UMLS links: {avg_umls:.1f}")
    
    if failed:
        logger.warning("\nFailed PDFs:")
        for r in failed:
            logger.warning(f"  - {r['pdf']}: {r.get('error', 'See stderr')}")
    
    # Write detailed report
    report_file = output_dir / "test_report.json"
    with open(report_file, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "n_processed": len(results),
            "n_successful": len(successful),
            "n_failed": len(failed),
            "results": results
        }, f, indent=2)
    
    logger.info(f"\nDetailed report saved to: {report_file}")
    
    return 0 if len(failed) == 0 else 1

if __name__ == "__main__":
    sys.exit(main())