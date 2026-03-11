import os
from tree_sitter import Parser
from src.models.module_node import ModuleNode
from typing import List

from src.utils.language_loader import load_language
PY_LANGUAGE = load_language('python')
class TreeSitterAnalyzer:
    # ... (rest unchanged, keep as before)
    def __init__(self):
        self.parser = Parser()
        self.parser.set_language(PY_LANGUAGE)

    def analyze_module(self, path: str) -> ModuleNode:
        with open(path, 'r', encoding='utf-8') as f:
            code = f.read()
        tree = self.parser.parse(bytes(code, 'utf8'))
        root = tree.root_node
        imports = self._extract_imports(root, code)
        public_functions = self._extract_public_functions(root, code)
        classes, class_inheritance = self._extract_classes(root, code)
        return ModuleNode(
            path=path,
            language='python',
            imports=imports,
            public_functions=public_functions,
            classes=classes,
            class_inheritance=class_inheritance
        )

    def _extract_imports(self, root, code) -> List[str]:
        imports = []
        for node in root.children:
            if node.type == 'import_statement' or node.type == 'import_from_statement':
                imports.append(code[node.start_byte:node.end_byte].strip())
        return imports

    def _extract_public_functions(self, root, code) -> List[str]:
        functions = []
        for node in root.children:
            if node.type == 'function_definition':
                name_node = node.child_by_field_name('name')
                if name_node:
                    name = code[name_node.start_byte:name_node.end_byte]
                    if not name.startswith('_'):
                        functions.append(name)
        return functions

    def _extract_classes(self, root, code):
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