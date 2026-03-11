import os
import logging
import networkx as nx
from tree_sitter import Parser

from src.utils.language_loader import load_language
from src.analyzers.tree_sitter_analyzer import TreeSitterAnalyzer
from src.analyzers.sql_analyzer import SQLAnalyzer
from src.analyzers.yaml_analyzer import YAMLAnalyzer
from src.graph.knowledge_graph import KnowledgeGraph
from src.models.node_types import ModuleNode
from src.models.edge_types import ImportEdge
from src.analyzers.git_velocity import extract_git_velocity

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
        # Only Python grammar is loaded; SQL/YAML are handled by external analyzers
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
        return None, lang

class DynamicSurveyor:
    def __init__(self, knowledge_graph: KnowledgeGraph):
        self.kg = knowledge_graph
        self.router = LanguageRouter()

    def analyze_repo(self, repo_path: str) -> dict:
        """
        Analyze the repository, build the module graph, compute analytics,
        and return a structured report.
        """
        file_paths = []   # for git velocity

        # --- First pass: collect all Python modules and add them to the KG ---
        for root, _, files in os.walk(repo_path):
            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                file_path = os.path.join(root, fname)
                parser, lang = self.router.get_parser_and_lang(ext)

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
                            is_dead_code_candidate=False   # will be updated later
                        )
                        self.kg.add_node(module_node)

                        # Add import edges (simplified – we don't resolve fully here)
                        for imp in result.imports:
                            edge = ImportEdge(
                                source=file_path,
                                target=imp,   # may need resolution; for now keep as string
                                weight=1,
                                source_file=file_path
                            )
                            self.kg.add_edge(edge)

                # SQL and YAML are not processed by Surveyor – they belong to Hydrologist

        # --- Compute git velocity ---
        git_velocity = extract_git_velocity(file_paths)

        # --- Build a directed graph of only import edges for analytics ---
        G = nx.DiGraph()
        for u, v, data in self.kg.graph.edges(data=True):
            edge_model = data.get('model')
            if isinstance(edge_model, ImportEdge):
                G.add_edge(u, v)

        # --- Compute PageRank ---
        pagerank = nx.pagerank(G, alpha=0.85)

        # --- Find strongly connected components ---
        sccs = list(nx.strongly_connected_components(G))
        scc_map = {}
        for idx, comp in enumerate(sccs):
            for node in comp:
                scc_map[node] = idx

        # --- Update each ModuleNode with analytics and dead-code flag ---
        for node_id, node_model in self.kg.graph.nodes(data='model'):
            if isinstance(node_model, ModuleNode):
                # Update git velocity
                if node_model.path in git_velocity:
                    node_model.change_velocity_30d = git_velocity[node_model.path]

                # Update PageRank
                node_model.pagerank = pagerank.get(node_id, 0.0)

                # Update SCC ID
                node_model.scc_id = scc_map.get(node_id)

                # Flag dead-code candidates:
                #   - no imports (in-degree and out-degree zero)
                #   - no public functions
                in_deg = G.in_degree(node_id)
                out_deg = G.out_degree(node_id)
                if in_deg == 0 and out_deg == 0 and len(node_model.public_functions) == 0:
                    node_model.is_dead_code_candidate = True
                # (Optional) also consider change_velocity_30d == 0

                # Persist the updated node back into the graph
                self.kg.add_node(node_model)

        # --- Generate structured report ---
        report = {
            'high_impact_modules': sorted(
                [(node_id, node_model.pagerank) for node_id, node_model in self.kg.graph.nodes(data='model')
                 if isinstance(node_model, ModuleNode)],
                key=lambda x: x[1], reverse=True
            )[:10],   # top 10 by PageRank
            'high_velocity_modules': sorted(
                [(node_id, node_model.change_velocity_30d) for node_id, node_model in self.kg.graph.nodes(data='model')
                 if isinstance(node_model, ModuleNode) and node_model.change_velocity_30d],
                key=lambda x: x[1], reverse=True
            )[:10],
            'circular_dependencies': [
                {'scc_id': idx, 'nodes': list(comp)}
                for idx, comp in enumerate(sccs) if len(comp) > 1
            ],
            'dead_code_candidates': [
                node_id for node_id, node_model in self.kg.graph.nodes(data='model')
                if isinstance(node_model, ModuleNode) and node_model.is_dead_code_candidate
            ]
        }

        return report