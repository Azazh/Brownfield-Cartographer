import os
from tree_sitter import Parser
from src.utils.loader import load_language
from typing import Dict

class LanguageRouter:
    """
    Selects and manages tree-sitter parsers for multiple languages.
    Provides both parser and language name for a given file extension.
    """
    EXT_MAP = {
        '.py': 'python',
        '.sql': 'sql',
        '.yml': 'yaml',
        '.yaml': 'yaml',
    }


    def __init__(self):
        try:
            self.languages = {}
            self.parsers = {}
            for lang in set(self.EXT_MAP.values()):
                try:
                    self.languages[lang] = load_language(lang)
                    parser = Parser()
                    parser.language = self.languages[lang]
                    self.parsers[lang] = parser
                except Exception as e:
                    import traceback
                    print(f"[LanguageRouter] Failed to load language '{lang}': {e}")
                    traceback.print_exc()
        except Exception as e:
            import traceback
            print("[LanguageRouter] Exception during initialization:")
            traceback.print_exc()
            raise

    def get_parser_and_lang(self, ext: str):
        lang = self.EXT_MAP.get(ext.lower())
        if lang and lang in self.parsers:
            return self.parsers[lang], lang
        return None, None
