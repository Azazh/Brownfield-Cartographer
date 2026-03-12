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



TS_ANALYZER = TreeSitterAnalyzer()

class DynamicSurveyor:
    def __init__(self, knowledge_graph: KnowledgeGraph):
        self.kg = knowledge_graph
        self.router = LanguageRouter()


    def analyze_repo(self, repo_path: str) -> dict:
        """
        Analyze the repository, build the module graph (multi-language), compute analytics,
        and return a structured report. Compliant with challenge architecture.
        """
        file_paths = []   # for git velocity

        total_files = sum(len(files) for _, _, files in os.walk(repo_path))
        processed = 0
        for root, _, files in os.walk(repo_path):
            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                file_path = os.path.join(root, fname)
                lang = self.router.get_lang(ext)
                processed += 1
                if processed % 100 == 0 or processed == total_files:
                    logger.info(f"[Surveyor] Processed {processed}/{total_files} files...")
                try:
                    if lang in ('python', 'sql', 'yaml'):
                        result = TS_ANALYZER.analyze(file_path, lang, base_path=repo_path)
                        if not result:
                            continue
                        # For Python, use ModuleNode; for SQL/YAML, use DatasetNode or generic node
                        if lang == 'python':
                            file_paths.append(file_path)
                            module_node = ModuleNode(
                                path=file_path,
                                language='python',
                                imports=result['imports'],
                                public_functions=result['public_functions'],
                                classes=result['classes'],
                                class_inheritance=result['class_inheritance'],
                                change_velocity_30d=0,
                                is_dead_code_candidate=False
                            )
                            self.kg.add_node(module_node)
                            # Add import edges (including star/dynamic flags)
                            for imp in result['imports']:
                                edge = ImportEdge(
                                    source=file_path,
                                    target=imp,
                                    weight=1,
                                    source_file=file_path
                                )
                                self.kg.add_edge(edge)
                        elif lang == 'sql':
                            from src.models.node_types import DatasetNode
                            for table in result['tables']:
                                ds_node = DatasetNode(name=table, storage_type='table')
                                self.kg.add_node(ds_node)
                        elif lang == 'yaml':
                            from src.models.node_types import DatasetNode
                            for key in result['top_level_keys']:
                                ds_node = DatasetNode(name=key, storage_type='yaml_key')
                                self.kg.add_node(ds_node)
                except Exception as e:
                    logger.error(f"[Surveyor] Error processing {file_path}: {e}", exc_info=True)
                    continue

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