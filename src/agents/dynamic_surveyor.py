import os
import re
import yaml
import logging
from tree_sitter import Parser
from src.utils.language_loader import load_language
from src.analyzers.tree_sitter_analyzer import TreeSitterAnalyzer
from src.analyzers.sql_import_extractor import SQLImportExtractor
from src.graph.knowledge_graph import KnowledgeGraph
from src.models.node_types import ModuleNode
from src.models.edge_types import ImportEdge

logger = logging.getLogger(__name__)

class YAMLExtractor:
    # ... (unchanged, keep as before)
    def extract(self, path, parser=None):
        # same implementation as before
        pass

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
        # Only Python grammar is loaded (SQL/YAML will fail – that's expected)
        for lang in set(self.EXT_MAP.values()):
            try:
                self.languages[lang] = load_language(lang)
                parser = Parser()
                parser.set_language(self.languages[lang])
                self.parsers[lang] = parser
                logger.info(f"[LanguageRouter] Loaded language '{lang}'")
            except Exception as e:
                logger.debug(f"[LanguageRouter] Failed to load language '{lang}': {e}")

    def get_parser_and_lang(self, ext: str):
        lang = self.EXT_MAP.get(ext.lower())
        if lang and lang in self.parsers:
            return self.parsers[lang], lang
        return None, None

class DynamicSurveyor:
    def __init__(self, knowledge_graph: KnowledgeGraph):
        self.kg = knowledge_graph
        self.router = LanguageRouter()

    def analyze_repo(self, repo_path: str):
        from src.analyzers.git_velocity import extract_git_velocity

        file_imports = {}           # for legacy, if needed
        file_paths = []

        # Build SQL file map for resolving dependencies
        sql_file_map = {}
        for root, _, files in os.walk(repo_path):
            for fname in files:
                ext = os.path.splitext(fname)[1]
                file_path = os.path.join(root, fname)
                if ext == '.sql':
                    model_name = os.path.splitext(os.path.basename(fname))[0]
                    sql_file_map[model_name] = file_path

        # Walk all files
        for root, _, files in os.walk(repo_path):
            for fname in files:
                ext = os.path.splitext(fname)[1]
                file_path = os.path.join(root, fname)
                parser, lang = self.router.get_parser_and_lang(ext)
                if parser and lang:
                    extractor = EXTRACTORS.get(lang)
                    if extractor:
                        file_paths.append(file_path)
                        try:
                            if lang == 'python':
                                result = extractor.analyze_module(file_path)
                                # Create ModuleNode
                                module_node = ModuleNode(
                                    path=file_path,
                                    language='python',
                                    imports=result.imports,
                                    public_functions=result.public_functions,
                                    classes=result.classes,
                                    class_inheritance=result.class_inheritance,
                                    # Analytical fields (will be filled later or from git)
                                    change_velocity_30d=0,
                                    is_dead_code_candidate=(len(result.imports)==0 and len(result.public_functions)==0)
                                )
                                self.kg.add_node(module_node)

                                # Add import edges
                                for imp in result.imports:
                                    # Try to resolve import to a file path (simple heuristic)
                                    target_path = sql_file_map.get(imp, imp)
                                    edge = ImportEdge(
                                        source=file_path,
                                        target=target_path,
                                        weight=1,
                                        source_file=file_path
                                    )
                                    self.kg.add_edge(edge)

                            elif lang == 'sql':
                                imports = extractor.extract_imports(file_path)
                                # We'll let Hydrologist handle SQL lineage
                                pass
                            elif lang == 'yaml':
                                result = extractor.extract(file_path, parser)
                                # YAML dependencies will be processed by Hydrologist
                                pass
                        except Exception as e:
                            logger.error(f"Error analyzing {file_path}: {e}")

        # Compute git velocity for all processed files
        git_velocity = extract_git_velocity(file_paths)
        # Update ModuleNodes with change velocity
        for node_id, node_model in self.kg.graph.nodes(data='model'):
            if isinstance(node_model, ModuleNode) and node_model.path in git_velocity:
                node_model.change_velocity_30d = git_velocity[node_model.path]
                # Update the node in the graph (re‑add with updated model)
                self.kg.add_node(node_model)   # overwrites

        # Return legacy results if needed (optional)
        return {
            'file_types': {},
            'git_velocity': git_velocity,
            # ... other legacy fields
        }