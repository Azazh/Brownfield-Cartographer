import os
import logging
from tree_sitter import Parser
from src.utils.language_loader import load_language
from src.analyzers.tree_sitter_analyzer import TreeSitterAnalyzer
from src.analyzers.sql_analyzer import SQLAnalyzer
from src.analyzers.yaml_analyzer import YAMLAnalyzer
from src.graph.knowledge_graph import KnowledgeGraph
from src.models.node_types import ModuleNode
from src.models.edge_types import ImportEdge

logger = logging.getLogger(__name__)

# Analyzer instances
PY_ANALYZER = TreeSitterAnalyzer()
SQL_ANALYZER = SQLAnalyzer(dialect='duckdb')
YAML_ANALYZER = YAMLAnalyzer()

class LanguageRouter:
    EXT_MAP = {'.py': 'python', '.sql': 'sql', '.yml': 'yaml', '.yaml': 'yaml'}

    def __init__(self):
        self.languages = {}
        self.parsers = {}
        # Only Python grammar is loaded; SQL/YAML are handled by other means
        for lang in set(self.EXT_MAP.values()):
            if lang == 'python':
                try:
                    self.languages[lang] = load_language(lang)
                    parser = Parser()
                    parser.set_language(self.languages[lang])
                    self.parsers[lang] = parser
                    logger.info(f"[LanguageRouter] Loaded language '{lang}'")
                except Exception as e:
                    logger.debug(f"[LanguageRouter] Failed to load language '{lang}': {e}")
            else:
                logger.debug(f"[LanguageRouter] Skipping grammar for '{lang}' – using external analyzer")

    def get_parser_and_lang(self, ext: str):
        lang = self.EXT_MAP.get(ext.lower())
        if lang == 'python' and lang in self.parsers:
            return self.parsers[lang], lang
        # For SQL and YAML, return None parser but lang name
        return None, lang

class DynamicSurveyor:
    def __init__(self, knowledge_graph: KnowledgeGraph):
        self.kg = knowledge_graph
        self.router = LanguageRouter()

    def analyze_repo(self, repo_path: str):
        from src.analyzers.git_velocity import extract_git_velocity

        file_paths = []

        # Walk all files
        for root, _, files in os.walk(repo_path):
            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                file_path = os.path.join(root, fname)
                parser, lang = self.router.get_parser_and_lang(ext)

                # Use appropriate analyzer
                if lang == 'python':
                    result = PY_ANALYZER.analyze_module(file_path, base_path=repo_path)
                    if result:
                        file_paths.append(file_path)
                        module_node = ModuleNode(
                            path=file_path,
                            language='python',
                            imports=result.imports,
                            public_functions=result.public_functions,
                            classes=result.classes,
                            class_inheritance=result.class_inheritance,
                            change_velocity_30d=0,
                            is_dead_code_candidate=(len(result.imports)==0 and len(result.public_functions)==0)
                        )
                        self.kg.add_node(module_node)

                        # Add import edges (simplified)
                        for imp in result.imports:
                            edge = ImportEdge(
                                source=file_path,
                                target=imp,  # may need resolution
                                weight=1,
                                source_file=file_path
                            )
                            self.kg.add_edge(edge)

                elif lang == 'sql':
                    result = SQL_ANALYZER.analyze_file(file_path)
                    if result and result['error'] is None:
                        # We'll let Hydrologist handle SQL lineage
                        pass

                elif lang == 'yaml':
                    result = YAML_ANALYZER.analyze_file(file_path)
                    if result and result['error'] is None:
                        # Let Hydrologist handle YAML dependencies
                        pass

        # Compute git velocity and update nodes
        git_velocity = extract_git_velocity(file_paths)
        for node_id, node_model in self.kg.graph.nodes(data='model'):
            if isinstance(node_model, ModuleNode) and node_model.path in git_velocity:
                node_model.change_velocity_30d = git_velocity[node_model.path]
                self.kg.add_node(node_model)  # update