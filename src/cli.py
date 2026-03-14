#!/usr/bin/env python3

import argparse
import os
import sys
import tempfile
import subprocess
import logging
from src.orchestrator import run_analysis

# Load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

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
    parser.add_argument('--mode', type=str, default='analyze', choices=['analyze', 'query'],
                        help='Mode: analyze (default) or query (Navigator agent)')
    parser.add_argument('--run-mode', type=str, default='auto', choices=['auto', 'full', 'incremental'],
                        help='Run mode: auto (default, infer from git), full (force full analysis), incremental (force incremental if possible)')
    parser.add_argument('--query-tool', type=str, default=None,
                        help='Navigator tool to use: find_implementation, trace_lineage, blast_radius, explain_module')
    parser.add_argument('--query-arg', type=str, nargs='*', default=None,
                        help='Arguments for the query tool (e.g., concept, dataset, direction, module_path, path)')
    args = parser.parse_args()
    repo_path = args.repo
    output_dir = args.output
    sql_dialect = args.sql_dialect
    mode = args.mode
    run_mode = args.run_mode
    temp_dir = None
    if repo_path.startswith(('http://', 'https://', 'git@')):
        logger.info("Detected remote repository URL – cloning...")
        temp_dir = clone_repo(repo_path)
        repo_path = temp_dir

    try:
        if mode == 'analyze':
            from src.orchestrator import run_analysis
            run_analysis(repo_path, output_dir, sql_dialect=sql_dialect, run_mode=run_mode)
        elif mode == 'query':
            from src.orchestrator import run_query
            run_query(repo_path, output_dir, args.query_tool, args.query_arg)
    except Exception as e:
        logger.exception("Fatal error during analysis/query")
        sys.exit(1)
    finally:
        # Optional cleanup of temporary clone
        if temp_dir is not None and os.path.exists(temp_dir):
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.info(f"Cleaned up temporary directory {temp_dir}")

if __name__ == "__main__":
    main()