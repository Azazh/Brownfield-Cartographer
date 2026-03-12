# src/analyzers/git_velocity.py
import subprocess
import os
from datetime import datetime, timedelta

def extract_git_velocity(file_paths, days=30):
    """
    For each file, count commits in the last `days` days.
    Returns dict: {file_path: commit_count}
    """
    if not file_paths:
        return {}
    # Get the git root from the first file
    repo_dir = os.path.dirname(os.path.commonprefix(file_paths))
    since_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    cmd = ['git', 'log', '--since={}'.format(since_date), '--pretty=format:', '--name-only']
    result = subprocess.run(cmd, cwd=repo_dir, capture_output=True, text=True)
    if result.returncode != 0:
        return {}
    # Count occurrences of each file
    counts = {}
    for line in result.stdout.splitlines():
        line = line.strip()
        if line:
            counts[line] = counts.get(line, 0) + 1
    # Filter to only the provided file paths
    return {f: counts.get(os.path.relpath(f, repo_dir), 0) for f in file_paths}