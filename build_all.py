import os
from tree_sitter import Language

os.makedirs('build', exist_ok=True)
Language.build_library(
    'build/my-languages.so',
    [
        'vendor/tree-sitter-python',
        'vendor/tree-sitter-sql',
        'vendor/tree-sitter-yaml',
    ]
)
print("✅ Shared library built at build/my-languages.so with Python, SQL, YAML")
