import os
import subprocess
import sys

DBT_PROJECT_PATH = sys.argv[1] if len(sys.argv) > 1 else '.'
COMPILED_SQL_DIR = os.path.join(DBT_PROJECT_PATH, 'target', 'compiled')
CARTOGRAPHY_DIR = '.cartography'

# 1. Run dbt compile
print(f"[INFO] Running 'dbt compile' in {DBT_PROJECT_PATH} ...")
subprocess.run(['dbt', 'compile'], cwd=DBT_PROJECT_PATH, check=True)

# 2. Find the models directory with compiled SQL
models_dir = os.path.join(COMPILED_SQL_DIR, 'jaffle_shop', 'models')
if not os.path.isdir(models_dir) or not any(f.endswith('.sql') for f in os.listdir(models_dir)):
    print(f"[ERROR] No compiled SQL files found in {models_dir}")
    sys.exit(1)

print(f"[INFO] Analyzing compiled SQL in {models_dir} ...")
subprocess.run([
    sys.executable, '-m', 'src.cli',
    '--repo', models_dir,
    '--output', CARTOGRAPHY_DIR,
    '--mode', 'analyze'
], check=True)

print(f"[INFO] Analysis complete. See {CARTOGRAPHY_DIR} for results.")
