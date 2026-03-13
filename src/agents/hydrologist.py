# src/agents/hydrologist.py
import os
import networkx as nx
import logging
from tree_sitter import Parser
from tree_sitter_languages import get_language

from src.analyzers.sql_lineage import SQLLineageAnalyzer
from src.analyzers.dag_config_parser import DbtYamlAnalyzer  # optional for now

logger = logging.getLogger(__name__)

import ast

class PythonDataFlowAnalyzer:
    def analyze_file(self, file_path):
        operations = []
        with open(file_path, "r", encoding="utf-8") as f:
            try:
                tree = ast.parse(f.read(), filename=file_path)
            except Exception:
                return operations
        for node in ast.walk(tree):
            # Detect pandas.read_csv
            if (
                isinstance(node, ast.Call)
                and hasattr(node.func, 'attr')
                and node.func.attr == 'read_csv'
            ):
                for arg in node.args:
                    if isinstance(arg, ast.Str):
                        operations.append({'type': 'pandas', 'operation': 'read_csv', 'dataset': arg.s})
            # Detect pandas.DataFrame.to_csv
            if (
                isinstance(node, ast.Call)
                and hasattr(node.func, 'attr')
                and node.func.attr == 'to_csv'
            ):
                for arg in node.args:
                    if isinstance(arg, ast.Str):
                        operations.append({'type': 'pandas', 'operation': 'to_csv', 'dataset': arg.s})
        return operations

class DataLineageGraph:
    """
    A NetworkX DiGraph with nodes = datasets, edges = transformations.
    Each edge has attributes: type, source_file, line_range (optional).
    """
    def __init__(self):
        self.graph = nx.DiGraph()

    def add_edge(self, source, target, **attrs):
        self.graph.add_edge(source, target, **attrs)

    def add_node(self, node, **attrs):
        self.graph.add_node(node, **attrs)

    def blast_radius(self, node):
        """Return all nodes downstream of node (including node)."""
        if node not in self.graph:
            return []
        # BFS descendants
        descendants = nx.descendants(self.graph, node)
        return list(descendants) + [node]

    def find_sources(self):
        """Nodes with in_degree == 0."""
        return [n for n, d in self.graph.in_degree() if d == 0]

    def find_sinks(self):
        """Nodes with out_degree == 0."""
        return [n for n, d in self.graph.out_degree() if d == 0]

    def to_json_serializable(self):
        return nx.node_link_data(self.graph)

    @classmethod
    def from_json(cls, data):
        g = cls()
        g.graph = nx.node_link_graph(data)
        return g

class HydrologistAgent:
    def __init__(self, knowledge_graph=None, sql_dialect='duckdb', trace_logger=None):
        self.kg = knowledge_graph
        self.py_analyzer = PythonDataFlowAnalyzer()
        self.sql_analyzer = SQLLineageAnalyzer(dialect=sql_dialect)
        self.yaml_analyzer = DbtYamlAnalyzer()
        self.lineage_graph = DataLineageGraph()
        self.trace_logger = trace_logger

    def analyze_repo(self, repo_path, changed_files=None, added_files=None, deleted_files=None):
        """
        Walk repo, collect lineage from all relevant files. Supports incremental update via changed_files, added_files, deleted_files.
        """
        if changed_files or added_files or deleted_files:
            logger.info(f"[Hydrologist] Incremental update: changed={changed_files}, added={added_files}, deleted={deleted_files}")
            # Remove deleted files' nodes from the lineage graph
            if deleted_files:
                for node in list(self.kg.graph.nodes()):
                    model = self.kg.graph.nodes[node].get('model')
                    if hasattr(model, 'source_file') and model.source_file in deleted_files:
                        self.kg.graph.remove_node(node)
            # Re-analyze changed and added files
            files_to_process = (changed_files or []) + (added_files or [])
            for file_path in files_to_process:
                ext = os.path.splitext(file_path)[1].lower()
                try:
                    if ext == '.py':
                        self._process_python(file_path)
                    elif ext == '.sql':
                        self._process_sql(file_path)
                    elif ext in ('.yml', '.yaml'):
                        self._process_yaml(file_path)
                except Exception as e:
                    logger.error(f"Error processing {file_path}: {e}", exc_info=True)
            return self.lineage_graph
        # Walk repo, collect lineage from all relevant files.
        for root, _, files in os.walk(repo_path):
            for file in files:
                file_path = os.path.join(root, file)
                ext = os.path.splitext(file)[1].lower()
                try:
                    if ext == '.py':
                        self._process_python(file_path)
                    elif ext == '.sql':
                        self._process_sql(file_path)
                    elif ext in ('.yml', '.yaml'):
                        self._process_yaml(file_path)
                except Exception as e:
                    logger.error(f"Error processing {file_path}: {e}", exc_info=True)

        return self.lineage_graph

    def _process_python(self, file_path):
        operations = self.py_analyzer.analyze_file(file_path)
        for op in operations:
            # op: {'type': 'pandas', 'operation': func, 'dataset': dataset}
            dataset = op['dataset']
            if dataset and isinstance(dataset, str) and not dataset.startswith('dynamic'):
                # Treat as a node
                self.lineage_graph.add_node(dataset, type='dataset')
                # Optionally, we could infer an edge from something to dataset.
                # For read operations, the dataset is a source. For write, it's a sink.
                # We'll need to detect read vs write. For now, just record.
                # We'll handle more precisely in final.

    def _process_sql(self, file_path):
        lineage = self.sql_analyzer.extract_lineage(file_path)
        target = lineage['target']
        sources = lineage['sources']
        if target:
            self.lineage_graph.add_node(target, type='dataset')
        for src in sources:
            self.lineage_graph.add_node(src, type='dataset')
            self.lineage_graph.add_edge(src, target,
                                        type='sql',
                                        source_file=file_path)

    def _process_yaml(self, file_path):
        # For interim, we might just log
        edges = self.yaml_analyzer.extract_lineage(file_path)
        for src, tgt in edges:
            self.lineage_graph.add_node(src, type='dataset')
            self.lineage_graph.add_node(tgt, type='dataset')
            self.lineage_graph.add_edge(src, tgt,
                                        type='dbt_yaml',
                                        source_file=file_path)

    def blast_radius(self, node):
        return self.lineage_graph.blast_radius(node)

    def find_sources(self):
        return self.lineage_graph.find_sources()

    def find_sinks(self):
        return self.lineage_graph.find_sinks()