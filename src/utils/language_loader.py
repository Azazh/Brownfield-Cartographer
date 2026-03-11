import os
from tree_sitter import Language

LANGUAGE_SO = os.path.join(os.path.dirname(__file__), '../../build/my-languages.so')

def load_language(lang_name):
    """
    Load a language from the shared library using tree-sitter 0.21.x API.
    """
    return Language(LANGUAGE_SO, lang_name)