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
        import ast, logging
        logger = logging.getLogger(__name__)
        operations = []
        with open(file_path, "r", encoding="utf-8") as f:
            try:
                tree = ast.parse(f.read(), filename=file_path)
            except Exception:
                return operations
        for node in ast.walk(tree):
            # Pandas read_csv/read_sql
            if (
                isinstance(node, ast.Call)
                and hasattr(node.func, 'attr')
                and node.func.attr in ('read_csv', 'read_sql')
            ):
                op_type = 'pandas'
                op_name = node.func.attr
                dataset = None
                for arg in node.args:
                    if isinstance(arg, ast.Str):
                        dataset = arg.s
                    elif isinstance(arg, ast.JoinedStr):
                        logger.warning(f"[Lineage] Unresolved dynamic reference in {file_path}: f-string in {op_name}")
                        dataset = 'dynamic_reference'
                if dataset:
                    operations.append({'type': op_type, 'operation': op_name, 'dataset': dataset, 'direction': 'read', 'line_range': (getattr(node, 'lineno', None), getattr(node, 'end_lineno', None))})
            # Pandas to_csv/to_sql
            if (
                isinstance(node, ast.Call)
                and hasattr(node.func, 'attr')
                and node.func.attr in ('to_csv', 'to_sql')
            ):
                op_type = 'pandas'
                op_name = node.func.attr
                dataset = None
                for arg in node.args:
                    if isinstance(arg, ast.Str):
                        dataset = arg.s
                    elif isinstance(arg, ast.JoinedStr):
                        logger.warning(f"[Lineage] Unresolved dynamic reference in {file_path}: f-string in {op_name}")
                        dataset = 'dynamic_reference'
                if dataset:
                    operations.append({'type': op_type, 'operation': op_name, 'dataset': dataset, 'direction': 'write', 'line_range': (getattr(node, 'lineno', None), getattr(node, 'end_lineno', None))})
            # SQLAlchemy engine.execute
            if (
                isinstance(node, ast.Call)
                and hasattr(node.func, 'attr')
                and node.func.attr == 'execute'
            ):
                op_type = 'sqlalchemy'
                op_name = 'execute'
                dataset = None
                for arg in node.args:
                    if isinstance(arg, ast.Str):
                        dataset = arg.s
                    elif isinstance(arg, ast.JoinedStr):
                        logger.warning(f"[Lineage] Unresolved dynamic reference in {file_path}: f-string in SQLAlchemy execute")
                        dataset = 'dynamic_reference'
                if dataset:
                    operations.append({'type': op_type, 'operation': op_name, 'dataset': dataset, 'direction': 'read', 'line_range': (getattr(node, 'lineno', None), getattr(node, 'end_lineno', None))})
            # PySpark read/write
            if (
                isinstance(node, ast.Call)
                and hasattr(node.func, 'attr')
                and node.func.attr in ('csv', 'parquet', 'json')
            ):
                parent = getattr(node.func, 'value', None)
                if parent and hasattr(parent, 'attr') and parent.attr in ('read', 'write'):
                    op_type = 'spark'
                    op_name = f"{parent.attr}_{node.func.attr}"
                    direction = 'read' if parent.attr == 'read' else 'write'
                    dataset = None
                    for arg in node.args:
                        if isinstance(arg, ast.Str):
                            dataset = arg.s
                        elif isinstance(arg, ast.JoinedStr):
                            logger.warning(f"[Lineage] Unresolved dynamic reference in {file_path}: f-string in PySpark {op_name}")
                            dataset = 'dynamic_reference'
                    if dataset:
                        operations.append({'type': op_type, 'operation': op_name, 'dataset': dataset, 'direction': direction, 'line_range': (getattr(node, 'lineno', None), getattr(node, 'end_lineno', None))})
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
        import logging
        self.kg = knowledge_graph
        self.py_analyzer = PythonDataFlowAnalyzer()
        self.sql_analyzer = SQLLineageAnalyzer(dialect=sql_dialect)
        self.yaml_analyzer = DbtYamlAnalyzer()
        self.lineage_graph = DataLineageGraph()
        self.trace_logger = trace_logger
        self.logger = logging.getLogger(__name__)
        self.sql_dialect = sql_dialect

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
            # op: {'type': 'pandas'|'spark'|'sqlalchemy', 'operation': func, 'dataset': dataset, 'direction': 'read'|'write', 'line_range': (start, end)}
            dataset = op.get('dataset')
            transformation_type = op.get('type', 'python')
            direction = op.get('direction', None)
            line_range = op.get('line_range', None)
            if dataset and isinstance(dataset, str) and not dataset.startswith('dynamic'):
                self.lineage_graph.add_node(dataset, type='dataset')
                # Standardize edge metadata
                edge_meta = {
                    'transformation_type': transformation_type,
                    'source_file': file_path,
                    'line_range': line_range
                }
                # For reads, dataset is a source; for writes, dataset is a target
                if direction == 'read':
                    # Consumed by transformation
                    self.lineage_graph.add_edge(dataset, f"{file_path}:{line_range}", **edge_meta)
                elif direction == 'write':
                    # Produced by transformation
                    self.lineage_graph.add_edge(f"{file_path}:{line_range}", dataset, **edge_meta)

    def _process_sql(self, file_path):
        # Support multiple dialects via sqlglot, auto-detect if possible
        dialect = self.sql_analyzer.dialect if hasattr(self.sql_analyzer, 'dialect') else self.sql_dialect
        try:
            lineage = self.sql_analyzer.extract_lineage(file_path)
        except Exception as e:
            self.logger.warning(f"[Lineage] SQL parsing failed for {file_path}: {e}")
            return
        target = lineage.get('target')
        sources = lineage.get('sources', [])
        line_range = lineage.get('line_range', None)
        used_dialect = lineage.get('dialect', dialect)
        if target:
            self.lineage_graph.add_node(target, type='dataset')
        for src in sources:
            self.lineage_graph.add_node(src, type='dataset')
            edge_meta = {
                'transformation_type': f'sql_{used_dialect}',
                'source_file': file_path,
                'line_range': line_range
            }
            self.lineage_graph.add_edge(src, target, **edge_meta)
        if not sources or not target:
            self.logger.warning(f"[Lineage] Unresolved SQL lineage in {file_path}: sources={sources}, target={target}")

    def _process_yaml(self, file_path):
        edges = self.yaml_analyzer.extract_lineage(file_path)
        for src, tgt, meta in edges:
            self.lineage_graph.add_node(src, type='dataset')
            self.lineage_graph.add_node(tgt, type='dataset')
            edge_meta = {
                'transformation_type': meta.get('transformation_type', 'dbt_yaml') if meta else 'dbt_yaml',
                'source_file': file_path,
                'line_range': meta.get('line_range') if meta else None
            }
            self.lineage_graph.add_edge(src, tgt, **edge_meta)

    def blast_radius(self, node):
        # Return downstream nodes with edge metadata
        nodes = self.lineage_graph.blast_radius(node)
        results = []
        for n in nodes:
            for succ in self.lineage_graph.graph.successors(n):
                edge_data = self.lineage_graph.graph.get_edge_data(n, succ)
                results.append({'from': n, 'to': succ, 'edge': edge_data})
        return results

    def find_sources(self):
        # Return source nodes with metadata
        sources = self.lineage_graph.find_sources()
        return [{'node': n, 'metadata': self.lineage_graph.graph.nodes[n]} for n in sources]

    def find_sinks(self):
        # Return sink nodes with metadata
        sinks = self.lineage_graph.find_sinks()
        return [{'node': n, 'metadata': self.lineage_graph.graph.nodes[n]} for n in sinks]