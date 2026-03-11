# Entry point for The Brownfield Cartographer
import argparse
import os
from src.orchestrator import run_analysis

def main():
    try:
        parser = argparse.ArgumentParser(description="The Brownfield Cartographer")
        parser.add_argument('--repo', type=str, required=True, help='Path to target codebase')
        args = parser.parse_args()

        repo_path = args.repo
        run_analysis(repo_path)
    except Exception as e:
        import traceback
        print("[ERROR] Exception occurred in CLI:")
        traceback.print_exc()

if __name__ == "__main__":
    main()