# Entry point for The Brownfield Cartographer
import argparse
import os
import glob

from src.agents.dynamic_surveyor import DynamicSurveyor



def main():
    try:
        parser = argparse.ArgumentParser(description="The Brownfield Cartographer")
        parser.add_argument('--repo', type=str, required=True, help='Path to target codebase')
        parser.add_argument('--so', type=str, default='build/my-languages.so', help='Path to tree-sitter languages .so')
        args = parser.parse_args()

        repo_path = args.repo
        so_path = args.so
        surveyor = DynamicSurveyor(so_path)
        results = surveyor.analyze_repo(repo_path)
        print(f"Analyzed {len(results)} files across supported languages.")
        # Save results as JSON (human- and machine-readable)
        import json
        import datetime
        output_dir = os.path.join(os.path.dirname(__file__), '..', 'docs')
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = os.path.join(output_dir, f"analysis_results_{timestamp}.json")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"Analysis results saved to {output_path}")
    except Exception as e:
        import traceback
        print("[ERROR] Exception occurred in CLI:")
        traceback.print_exc()

if __name__ == "__main__":
    main()
