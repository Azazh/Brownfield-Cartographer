import os
from src.analyzers.language_router import LanguageRouter

class MultiLangSurveyor:
    """
    Surveyor for Python, SQL, and YAML using tree-sitter LanguageRouter.
    """
    def __init__(self, so_path: str):
        self.router = LanguageRouter(so_path)

    def analyze_file(self, path: str):
        ext = os.path.splitext(path)[1]
        parser = self.router.get_parser(ext)
        if not parser:
            return None
        with open(path, 'r', encoding='utf-8') as f:
            code = f.read()
        tree = parser.parse(bytes(code, 'utf8'))
        root = tree.root_node
        # TODO: Dispatch to language-specific extractors
        return {'path': path, 'lang': ext, 'tree': tree, 'root': root}
