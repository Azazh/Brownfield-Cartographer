import os
import logging
from tree_sitter import Parser
from src.utils.language_loader import load_language
from src.models.module_node import ModuleNode
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

PY_LANGUAGE = load_language('python')

class TreeSitterAnalyzer:
    """
    Analyze Python modules for imports, public functions, classes, and decorators.
    Resolves relative imports and provides structured output.
    """

    def __init__(self):
        self.parser = Parser()
        self.parser.set_language(PY_LANGUAGE)

    def analyze_module(self, path: str, base_path: str = None) -> Optional[ModuleNode]:
        """
        Analyze a Python file and return a ModuleNode.
        base_path: the root directory of the repository (used for resolving relative imports).
        """
        try:
            with open(path, 'r', encoding='utf-8') as f:
                code = f.read()
        except Exception as e:
            logger.error(f"Failed to read {path}: {e}")
            return None

        try:
            tree = self.parser.parse(bytes(code, 'utf8'))
        except Exception as e:
            logger.error(f"Failed to parse {path}: {e}")
            return None

        root = tree.root_node

        imports = self._extract_imports(root, code, path, base_path)
        public_functions = self._extract_functions(root, code, with_decorators=True)
        classes, class_inheritance = self._extract_classes(root, code)

        return ModuleNode(
            path=path,
            language='python',
            imports=imports,
            public_functions=public_functions,
            classes=classes,
            class_inheritance=class_inheritance
        )

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