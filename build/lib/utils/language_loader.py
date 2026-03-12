import os
from tree_sitter import Language

# Path to the multi-language shared library
LANGUAGE_SO = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../build/my-languages.so'))

def load_language(lang_name):
    """
    Load a language from the shared library using tree-sitter >=0.20.x API.
    Requires the shared library to be built with all grammars.
    """
    return Language(LANGUAGE_SO, lang_name)