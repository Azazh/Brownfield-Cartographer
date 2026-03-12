import os
from tree_sitter import Language

# Path to the multi-language shared library
LANGUAGE_SO = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../build/my-languages.so'))

def load_language(language_so_path):
    """
    Load a language from the given .so path using the legacy tree-sitter API (Language(language_so_path)).
    """
    return Language(language_so_path)