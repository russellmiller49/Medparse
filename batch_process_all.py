#!/usr/bin/env python
"""
Batch process all PDFs in input folder and automatically push results to GitHub.
Runs in background and logs progress.
"""
import os
import sys
import json
import subprocess
import traceback
from pathlib import Path
from datetime import datetime
from loguru import logger

# Configure logging
LOG_FILE = "batch_process.log"
logger.add(LOG_FILE, rotation="500 MB")

def find_all_pdfs(input_dir="input", output_dir="out/batch_processed"):
    """Find all PDF files in input directory that haven't been processed yet."""
    input_path = Path(input_dir)
    if not input_path.exists():
        logger.error(f"Input directory {input_dir} does not exist")
        return []
    
    pdfs = list(input_path.glob("*.pdf"))
    
    # Check which ones are already processed
    output_path = Path(output_dir)
    if output_path.exists():
        processed = set()
        for json_file in output_path.glob("*.json"):
            if json_file.stem != "processing_report":
                processed.add(json_file.stem)
        
        # Filter out already processed PDFs
        unprocessed = [p for p in pdfs if p.stem not in processed]
        logger.info(f"Found {len(pdfs)} PDFs total, {len(processed)} already processed, {len(unprocessed)} to process")
        return unprocessed
    
    logger.info(f"Found {len(pdfs)} PDF files in {input_dir}")
    return pdfs

def process_single_pdf(pdf_path, output_dir="out/batch_processed"):
    """Process a single PDF file."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    pdf_name = pdf_path.stem
    output_file = output_path / f"{pdf_name}.json"
    
    logger.info(f"Processing {pdf_path.name}...")
    
    cmd = [
        "python", "scripts/process_one.py",
        "--pdf", str(pdf_path),
        "--out", str(output_file),
        "--cfg", "config/docling_medical_config.yaml",
        "--linker", "umls"
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout per PDF
        )
        
        if result.returncode == 0:
            logger.success(f"✓ Successfully processed {pdf_name}")
            return True, output_file
        else:
            logger.error(f"✗ Failed to process {pdf_name}: {result.stderr}")
            return False, None
            
    except subprocess.TimeoutExpired:
        logger.error(f"✗ Timeout processing {pdf_name}")
        return False, None
    except Exception as e:
        logger.error(f"✗ Error processing {pdf_name}: {e}")
        return False, None

def create_summary_report(results, output_dir="out/batch_processed"):
    """Create a summary report of processing results."""
    report = {
        "timestamp": datetime.now().isoformat(),
        "total_pdfs": len(results),
        "successful": sum(1 for success, _ in results.values() if success),
        "failed": sum(1 for success, _ in results.values() if not success),
        "details": {}
    }
    
    for pdf_name, (success, output_file) in results.items():
        report["details"][pdf_name] = {
            "success": success,
            "output_file": str(output_file) if output_file else None
        }
        
        # Try to extract key metrics from successful outputs
        if success and output_file and output_file.exists():
            try:
                with open(output_file) as f:
                    data = json.load(f)
                    meta = data.get("metadata", {})
                    report["details"][pdf_name].update({
                        "authors": len(meta.get("authors", [])),
                        "abstract": bool(meta.get("abstract")),
                        "references": len(meta.get("references_enriched", [])),
                        "statistics": len(data.get("statistics", [])),
                        "tables": len(data.get("assets", {}).get("tables", [])),
                        "figures": len(data.get("assets", {}).get("figures", []))
                    })
            except Exception as e:
                logger.warning(f"Could not extract metrics from {output_file}: {e}")
    
    # Save report
    report_file = Path(output_dir) / "processing_report.json"
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2)
    
    logger.info(f"Report saved to {report_file}")
    return report

def git_commit_and_push(message=None):
    """Commit all changes and push to GitHub."""
    try:
        # Add all changes
        logger.info("Adding changes to git...")
        subprocess.run(["git", "add", "-A"], check=True)
        
        # Create commit message
        if not message:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            message = f"feat: Batch processed PDFs with improved extraction - {timestamp}\n\n"
            message += "- Enhanced abstract extraction\n"
            message += "- Reference fallback management\n"
            message += "- Statistics with context gating\n"
            message += "- Improved caption association\n"
            message += "- Fixed 'or' expansion pollution\n\n"
            message += "🤖 Generated with [Claude Code](https://claude.ai/code)\n\n"
            message += "Co-Authored-By: Claude <noreply@anthropic.com>"
        
        # Commit
        logger.info("Creating git commit...")
        subprocess.run(["git", "commit", "-m", message], check=True)
        
        # Get current branch
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            check=True
        )
        branch = result.stdout.strip()
        
        # Push to origin
        logger.info(f"Pushing to origin/{branch}...")
        subprocess.run(["git", "push", "origin", branch], check=True)
        
        logger.success(f"✓ Successfully pushed to GitHub (branch: {branch})")
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Git operation failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during git operations: {e}")
        return False

def main():
    """Main batch processing function."""
    logger.info("=" * 60)
    logger.info("Starting batch PDF processing")
    logger.info("=" * 60)
    
    # Find all PDFs
    pdfs = find_all_pdfs()
    if not pdfs:
        logger.error("No PDFs found to process")
        return 1
    
    # Process each PDF
    results = {}
    COMMIT_EVERY = 10  # Commit every 10 successful PDFs
    successful_count = 0
    
    for i, pdf_path in enumerate(pdfs, 1):
        logger.info(f"[{i}/{len(pdfs)}] Processing {pdf_path.name}")
        success, output_file = process_single_pdf(pdf_path)
        results[pdf_path.stem] = (success, output_file)
        
        if success:
            successful_count += 1
            
            # Periodic commit and push
            if successful_count % COMMIT_EVERY == 0:
                logger.info(f"Reached {successful_count} successful processes, committing intermediate results...")
                git_commit_and_push(
                    f"feat: Batch processed {successful_count} PDFs (intermediate commit)\n\n"
                    f"Progress: {i}/{len(pdfs)} total files\n\n"
                    "🤖 Generated with [Claude Code](https://claude.ai/code)\n\n"
                    "Co-Authored-By: Claude <noreply@anthropic.com>"
                )
    
    # Create summary report
    logger.info("Creating summary report...")
    report = create_summary_report(results)
    
    # Print summary
    logger.info("=" * 60)
    logger.info("PROCESSING COMPLETE")
    logger.info(f"Total PDFs: {report['total_pdfs']}")
    logger.info(f"Successful: {report['successful']}")
    logger.info(f"Failed: {report['failed']}")
    logger.info("=" * 60)
    
    # Commit and push to GitHub
    if report['successful'] > 0:
        logger.info("Committing and pushing results to GitHub...")
        git_success = git_commit_and_push()
        
        if git_success:
            logger.success("✓ All changes pushed to GitHub successfully!")
        else:
            logger.warning("⚠ Processing complete but git push failed. Check logs.")
    else:
        logger.warning("No successful outputs to commit")
    
    logger.info(f"Full log available at: {LOG_FILE}")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logger.warning("Batch processing interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)