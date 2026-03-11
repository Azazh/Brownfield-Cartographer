#!/usr/bin/env python3
"""
Entry point for The Brownfield Cartographer.
Supports local paths and GitHub URLs (automatically cloned).
"""

import argparse
import os
import sys
import tempfile
import subprocess
import logging
from src.orchestrator import run_analysis

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def clone_repo(git_url):
    """Clone a git repository into a temporary directory and return the path."""
    temp_dir = tempfile.mkdtemp(prefix="brownfield_")
    logger.info(f"Cloning {git_url} into {temp_dir} ...")
    try:
        subprocess.run(["git", "clone", "--depth", "1", git_url, temp_dir],
                       check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Git clone failed: {e.stderr}")
        sys.exit(1)
    return temp_dir

def main():
    parser = argparse.ArgumentParser(description="The Brownfield Cartographer")
    parser.add_argument('--repo', type=str, required=True,
                        help='Path to local repository or GitHub URL (https://... or git@...)')
    parser.add_argument('--output', type=str, default='.cartography',
                        help='Output directory for artifacts (default: .cartography)')
    args = parser.parse_args()

    repo_path = args.repo
    output_dir = args.output

    # If the repo argument looks like a URL, clone it first
    if repo_path.startswith(('http://', 'https://', 'git@')):
        logger.info("Detected remote repository URL – cloning...")
        repo_path = clone_repo(repo_path)
        # We'll keep the cloned repo; it will be deleted after analysis (optional)
        # For now, we leave it; you can add cleanup later.

    # Run the analysis
    try:
        run_analysis(repo_path, output_dir)
    except Exception as e:
        logger.exception("Fatal error during analysis")
        sys.exit(1)
    finally:
        # Optional: clean up cloned temporary directory
        if 'temp_dir' in locals() and os.path.exists(temp_dir):
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.info(f"Cleaned up temporary directory {temp_dir}")

if __name__ == "__main__":
    main()