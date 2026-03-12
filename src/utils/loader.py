import ctypes
import os
from tree_sitter import Language

LANGUAGE_SO = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../build/my-languages.so'))

def load_language(lang_name):
    """
    Load a language from the shared library using ctypes.
    Works with tree-sitter >= 0.22.
    """
    lib = ctypes.CDLL(LANGUAGE_SO)
    func_name = f'tree_sitter_{lang_name}'
    if not hasattr(lib, func_name):
        raise RuntimeError(f"Language '{lang_name}' not found in {LANGUAGE_SO}")
    func = getattr(lib, func_name)
    func.restype = ctypes.c_void_p
    func.argtypes = []
    ptr = func()
    return Language(ptr)