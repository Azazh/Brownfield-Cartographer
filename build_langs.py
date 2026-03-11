import os
from tree_sitter import Language

os.makedirs('build', exist_ok=True)

try:
    Language.build_library(
        'build/my-languages.so',
        [
            'vendor/tree-sitter-python',   # Only Python for now
            # 'vendor/tree-sitter-sql',    # Comment out SQL
            # 'vendor/tree-sitter-yaml'    # Optional – if you have it
        ]
    )
except AttributeError:
    from tree_sitter import build_library
    build_library(
        'build/my-languages.so',
        [
            'vendor/tree-sitter-python',
        ]
    )
print("✅ Shared library built at build/my-languages.so")