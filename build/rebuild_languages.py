
import os
import shutil
from tree_sitter import Language

def temporarily_move_yaml_schema_files(src_dir, temp_dir):
    schema_files = ["schema.core.c", "schema.json.c", "schema.legacy.c"]
    moved = []
    for fname in schema_files:
        src_path = os.path.join(src_dir, fname)
        if os.path.exists(src_path):
            shutil.move(src_path, os.path.join(temp_dir, fname))
            moved.append(fname)
    return moved

def restore_yaml_schema_files(src_dir, temp_dir, moved):
    for fname in moved:
        shutil.move(os.path.join(temp_dir, fname), os.path.join(src_dir, fname))

os.makedirs('build', exist_ok=True)
yaml_src = 'vendor/tree-sitter-yaml/src'
temp_dir = 'vendor/tree-sitter-yaml/'
moved = temporarily_move_yaml_schema_files(yaml_src, temp_dir)
try:
    Language.build_library(
        'build/my-languages.so',
        [
            'vendor/tree-sitter-python',
            'vendor/tree-sitter-sql',
            'vendor/tree-sitter-yaml',
        ]
    )
    print("✅ Shared library built at build/my-languages.so with Python, SQL, YAML")
finally:
    restore_yaml_schema_files(yaml_src, temp_dir, moved)