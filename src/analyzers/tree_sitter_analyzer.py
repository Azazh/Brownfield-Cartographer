import os
import logging
from tree_sitter import Parser
from src.utils.language_loader import load_language
from src.models.module_node import ModuleNode
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


LANGUAGES = {
    'python': load_language('python'),
    'sql': load_language('sql'),
    'yaml': load_language('yaml'),
}

class TreeSitterAnalyzer:
    """
    Multi-language AST analyzer for Python, SQL, and YAML using tree-sitter.
    Returns structured outputs for all languages.
    """
    def __init__(self):
        self.parsers = {}
        for lang, lang_obj in LANGUAGES.items():
            parser = Parser()
            parser.set_language(lang_obj)
            self.parsers[lang] = parser

    def analyze(self, path: str, lang: str, base_path: str = None) -> Optional[dict]:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                code = f.read()
        except Exception as e:
            logger.error(f"Failed to read {path}: {e}")
            return None
        parser = self.parsers.get(lang)
        if not parser:
            logger.error(f"No parser for language: {lang}")
            return None
        try:
            tree = parser.parse(bytes(code, 'utf8'))
        except Exception as e:
            logger.error(f"Failed to parse {path}: {e}")
            return None
        root = tree.root_node
        if lang == 'python':
            return self._analyze_python(root, code, path, base_path)
        elif lang == 'sql':
            return self._analyze_sql(root, code, path)
        elif lang == 'yaml':
            return self._analyze_yaml(root, code, path)
        return None

    def _analyze_python(self, root, code, file_path, base_path):
        imports, star_imports, dynamic_imports = self._extract_imports_python(root, code, file_path, base_path)
        public_functions = self._extract_functions(root, code, with_decorators=True)
        classes, class_inheritance = self._extract_classes(root, code)
        return {
            'path': file_path,
            'language': 'python',
            'imports': imports,
            'star_imports': star_imports,
            'dynamic_imports': dynamic_imports,
            'public_functions': public_functions,
            'classes': classes,
            'class_inheritance': class_inheritance
        }

    def _extract_imports_python(self, root, code, file_path, base_path):
        imports = []
        star_imports = []
        dynamic_imports = []
        for node in root.children:
            if node.type == 'import_statement':
                imp = code[node.start_byte:node.end_byte].strip()
                imports.append(imp)
                if '*' in imp:
                    star_imports.append(imp)
            elif node.type == 'import_from_statement':
                imp = code[node.start_byte:node.end_byte].strip()
                imports.append(imp)
                if '*' in imp:
                    star_imports.append(imp)
        # Detect dynamic imports
        if '__import__' in code or 'importlib' in code:
            dynamic_imports.append(file_path)
        return imports, star_imports, dynamic_imports

    def _analyze_sql(self, root, code, file_path):
        # Example: extract table names, star selects, etc.
        tables = set()
        star_selects = False
        for node in root.walk():
            if node.type == 'table_reference':
                tables.add(code[node.start_byte:node.end_byte])
            if node.type == 'select_clause':
                if '*' in code[node.start_byte:node.end_byte]:
                    star_selects = True
        return {
            'path': file_path,
            'language': 'sql',
            'tables': list(tables),
            'star_selects': star_selects
        }

    def _analyze_yaml(self, root, code, file_path):
        # Example: extract top-level keys, anchors, etc.
        keys = set()
        for node in root.children:
            if node.type == 'block_mapping_pair':
                key_node = node.child_by_field_name('key')
                if key_node:
                    keys.add(code[key_node.start_byte:key_node.end_byte])
        return {
            'path': file_path,
            'language': 'yaml',
            'top_level_keys': list(keys)
        }

    def _extract_functions(self, root, code: str, with_decorators: bool = True) -> List[str]:
        functions = []
        for node in root.children:
            if node.type == 'function_definition':
                name_node = node.child_by_field_name('name')
                if name_node:
                    name = code[name_node.start_byte:name_node.end_byte]
                    if not name.startswith('_'):
                        functions.append(name)
        return functions

    def _extract_classes(self, root, code: str):
        classes = []
        class_inheritance = {}
        for node in root.children:
            if node.type == 'class_definition':
                name_node = node.child_by_field_name('name')
                if name_node:
                    name = code[name_node.start_byte:name_node.end_byte]
                    classes.append(name)
                    bases_node = node.child_by_field_name('superclasses')
                    if bases_node:
                        bases = []
                        for child in bases_node.children:
                            if child.type == 'identifier':
                                bases.append(code[child.start_byte:child.end_byte])
                        if bases:
                            class_inheritance[name] = bases
        return classes, class_inheritance

    def _extract_imports(self, root, code: str, file_path: str, base_path: str) -> List[str]:
        """Extract import statements and resolve relative paths."""
        imports = []
        for node in root.children:
            if node.type == 'import_statement':
                # import a, b, c
                imp = code[node.start_byte:node.end_byte].strip()
                imports.append(imp)
            elif node.type == 'import_from_statement':
                # from ... import ...
                imp = code[node.start_byte:node.end_byte].strip()
                # Try to resolve relative imports to absolute module names
                if base_path and imp.startswith('from .'):
                    # This is a relative import; we could attempt to resolve to absolute path
                    # For now, keep as is
                    imports.append(imp)
                else:
                    imports.append(imp)
        return imports

    def _extract_functions(self, root, code: str, with_decorators: bool = True) -> List[str]:
        """Extract function names, optionally including decorators."""
        functions = []
        for node in root.children:
            if node.type == 'function_definition':
                name_node = node.child_by_field_name('name')
                if name_node:
                    name = code[name_node.start_byte:name_node.end_byte]
                    # Check if it's public (not starting with '_')
                    if not name.startswith('_'):
                        functions.append(name)
                    # Could also extract decorators if needed
        return functions

    def _extract_classes(self, root, code: str):
        classes = []
        class_inheritance = {}
        for node in root.children:
            if node.type == 'class_definition':
                name_node = node.child_by_field_name('name')
                if name_node:
                    name = code[name_node.start_byte:name_node.end_byte]
                    classes.append(name)
                    # Inheritance
                    bases_node = node.child_by_field_name('superclasses')
                    if bases_node:
                        bases = []
                        for child in bases_node.children:
                            if child.type == 'identifier':
                                bases.append(code[child.start_byte:child.end_byte])
                        if bases:
                            class_inheritance[name] = bases
        return classes, class_inheritance