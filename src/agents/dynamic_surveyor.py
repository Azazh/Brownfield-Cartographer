import os
from tree_sitter import Parser
from src.analyzers.language_router import LanguageRouter   # if this file exists
from src.analyzers.tree_sitter_analyzer import TreeSitterAnalyzer
from src.analyzers.sql_import_extractor import SQLImportExtractor
from src.utils.language_loader import load_language
import re
import yaml


class YAMLExtractor:
    """
    Extracts dbt source and ref dependencies from YAML files.
    Looks for 'source:' and 'ref:' fields and dbt config patterns.
    """
    def extract(self, path, parser=None):  # parser argument kept for compatibility, not used
        print(f"[DEBUG] YAMLExtractor called for {path}")
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            data = yaml.safe_load(content)
            imports = set()
            # Look for dbt sources and refs in YAML structure
            def walk(obj):
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        if k == 'source' and isinstance(v, str):
                            imports.add(f"source:{v}")
                        if k == 'ref' and isinstance(v, str):
                            imports.add(f"ref:{v}")
                        walk(v)
                elif isinstance(obj, list):
                    for item in obj:
                        walk(item)
            walk(data)
            # Also look for dbt ref/source in raw YAML text (for templated fields)
            ref_pattern = re.compile(r"ref\(['\"]([\w_]+)['\"]\)")
            source_pattern = re.compile(r"source\(['\"]([\w_]+)['\"],\s*['\"]([\w_]+)['\"]\)")
            for ref in ref_pattern.findall(content):
                imports.add(f"ref:{ref}")
            for m in source_pattern.findall(content):
                imports.add(f"source:{m[0]}.{m[1]}")
            print(f"[DEBUG] YAML dependencies for {path}: {imports}")
            return {'type': 'yaml', 'path': path, 'imports': list(imports)}
        except Exception as e:
            import traceback
            print(f"[YAMLExtractor] Error extracting imports from {path}:")
            traceback.print_exc()
            return {'type': 'yaml', 'path': path, 'imports': []}

# Extractors keyed by language name
EXTRACTORS = {
    'python': TreeSitterAnalyzer(),
    'sql': SQLImportExtractor(),
    'yaml': YAMLExtractor(),
}

class LanguageRouter:
    EXT_MAP = {'.py': 'python', '.sql': 'sql', '.yml': 'yaml', '.yaml': 'yaml'}

    def __init__(self):
        self.languages = {}
        self.parsers = {}
        for lang in set(self.EXT_MAP.values()):
            try:
                self.languages[lang] = load_language(lang)
                parser = Parser()
                parser.set_language(self.languages[lang])
                self.parsers[lang] = parser
                print(f"[LanguageRouter] Loaded language '{lang}'")
            except Exception as e:
                print(f"[LanguageRouter] Failed to load language '{lang}': {e}")

    def get_parser_and_lang(self, ext: str):
        lang = self.EXT_MAP.get(ext.lower())
        if lang and lang in self.parsers:
            return self.parsers[lang], lang
        return None, None

class DynamicSurveyor:
    """
    Surveyor agent for static structure analysis.
    Integrates modular extractors for Python, SQL, and YAML using tree-sitter.
    """
    def __init__(self):
        try:
            self.router = LanguageRouter()
        except Exception as e:
            import traceback
            print("[DynamicSurveyor] Exception during LanguageRouter initialization:")
            traceback.print_exc()
            raise

    def analyze_repo(self, repo_path: str):
        """
        Analyze the repo and return a structured dict with:
        - imports: {file_path: [imports]}
        - file_types: {file_path: type}
        - git_velocity: {file_path: commit_count}
        - module_graph: {nodes, edges}
        """
        from src.analyzers.git_velocity import extract_git_velocity
        from src.graph.module_import_graph import ModuleImportGraph
        file_imports = {}
        file_types = {}
        file_paths = []
        module_graph = ModuleImportGraph()
        # Build a mapping from dependency name to file path for SQL (e.g., model name to .sql file)
        sql_file_map = {}
        for root, _, files in os.walk(repo_path):
            for fname in files:
                ext = os.path.splitext(fname)[1]
                file_path = os.path.join(root, fname)
                if ext == '.sql':
                    # Map model name (file name without extension) to path
                    model_name = os.path.splitext(os.path.basename(fname))[0]
                    sql_file_map[model_name] = file_path

        for root, _, files in os.walk(repo_path):
            for fname in files:
                ext = os.path.splitext(fname)[1]
                try:
                    parser, lang = self.router.get_parser_and_lang(ext)
                    if parser and lang:
                        extractor = EXTRACTORS.get(lang)
                        if extractor:
                            file_path = os.path.join(root, fname)
                            print(f"[DEBUG] Analyzing {file_path} as {lang}")
                            file_types[file_path] = lang
                            file_paths.append(file_path)
                            try:
                                if lang == 'python':
                                    result = extractor.analyze_module(file_path)
                                    file_imports[file_path] = result.imports
                                    module_graph.add_module(file_path)
                                    for imp in result.imports:
                                        imp_path = sql_file_map.get(imp) or imp
                                        if imp_path in file_types:
                                            module_graph.add_import(file_path, imp_path)
                                elif lang == 'sql':
                                    imports = extractor.extract_imports(file_path)
                                    file_imports[file_path] = imports
                                    module_graph.add_module(file_path)
                                    for imp in imports:
                                        imp_path = sql_file_map.get(imp) or imp
                                        if imp_path in file_types or imp_path in sql_file_map.values():
                                            module_graph.add_import(file_path, imp_path)
                                elif lang == 'yaml':
                                    result = extractor.extract(file_path, parser)
                                    file_imports[file_path] = result.get('imports', [])
                                    module_graph.add_module(file_path)
                                else:
                                    file_imports[file_path] = []
                                    module_graph.add_module(file_path)
                            except Exception as e:
                                import traceback
                                print(f"[DynamicSurveyor] Error analyzing {fname} as {lang}:")
                                traceback.print_exc()
                except Exception as e:
                    import traceback
                    print(f"[DynamicSurveyor] Error processing file {fname}:")
                    traceback.print_exc()
        # Git velocity
        git_velocity = extract_git_velocity(file_paths)
        # Module graph export (nodes and edges)
        nodes = list(module_graph.graph.nodes())
        edges = list(module_graph.graph.edges())
        return {
            'imports': file_imports,
            'file_types': file_types,
            'git_velocity': git_velocity,
            'module_graph': {
                'nodes': nodes,
                'edges': edges
            }
        }