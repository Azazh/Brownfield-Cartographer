import os
import subprocess
import datetime
from typing import Dict, List


def extract_git_velocity(file_paths: List[str], days: int = 30) -> Dict[str, int]:
    """
    Returns a dict mapping file path to number of commits in the last `days` days.
    """
    velocity = {}
    since_date = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime('%Y-%m-%d')
    print(f"[DEBUG] Calculating git velocity since {since_date} for {len(file_paths)} files")
    # Find repo root
    try:
        repo_root = subprocess.check_output(["git", "rev-parse", "--show-toplevel"]).decode().strip()
        print(f"[DEBUG] Git repo root: {repo_root}")
    except Exception as e:
        import traceback
        print("[extract_git_velocity] Error finding git repo root:")
        traceback.print_exc()
        repo_root = os.getcwd()
    for path in file_paths:
        try:
            rel_path = os.path.relpath(path, repo_root)
            git_cmd = [
                "git", "log", "--follow", f"--since={since_date}", "--pretty=oneline", "--", rel_path
            ]
            print(f"[DEBUG] Running: {' '.join(git_cmd)} (cwd={repo_root})")
            result = subprocess.run(
                git_cmd,
                cwd=repo_root,
                capture_output=True, text=True, check=True
            )
            commit_count = len(result.stdout.strip().splitlines())
            velocity[path] = commit_count
            print(f"[DEBUG] {rel_path}: {commit_count} commits")
        except subprocess.CalledProcessError:
            print(f"[WARN] No git history for {path} (not tracked or no commits)")
            velocity[path] = 0
        except Exception as e:
            import traceback
            print(f"[extract_git_velocity] Error processing {path}:")
            traceback.print_exc()
            velocity[path] = 0
    return velocity

def get_high_velocity_core(velocity: Dict[str, int], top_percent: float = 0.2) -> List[str]:
    """
    Returns the top X% of files by change count.
    """
    if not velocity:
        print("[DEBUG] No velocity data provided to get_high_velocity_core.")
        return []
    sorted_files = sorted(velocity.items(), key=lambda x: x[1], reverse=True)
    n = max(1, int(len(sorted_files) * top_percent))
    core = [f for f, _ in sorted_files[:n]]
    print(f"[DEBUG] High velocity core ({top_percent*100:.0f}%): {core}")
    return core
