#!/usr/bin/env python3
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
                        help='Path to local repository or GitHub URL')
    parser.add_argument('--output', type=str, default='.cartography',
                        help='Output directory for artifacts (default: .cartography)')
    parser.add_argument('--sql-dialect', type=str, default='duckdb',
                        help='SQL dialect for parsing (e.g., duckdb, postgres, bigquery, snowflake). Default: duckdb')
    args = parser.parse_args()

    repo_path = args.repo
    output_dir = args.output
    sql_dialect = args.sql_dialect

    # If the repo argument looks like a URL, clone it first
    if repo_path.startswith(('http://', 'https://', 'git@')):
        logger.info("Detected remote repository URL – cloning...")
        repo_path = clone_repo(repo_path)

    try:
        run_analysis(repo_path, output_dir, sql_dialect=sql_dialect)
    except Exception as e:
        logger.exception("Fatal error during analysis")
        sys.exit(1)
    finally:
        # Optional cleanup of temporary clone
        if 'temp_dir' in locals() and os.path.exists(temp_dir):
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.info(f"Cleaned up temporary directory {temp_dir}")

if __name__ == "__main__":
    main()