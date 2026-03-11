"""
Hydrologist Agent: Phase 2 - Data Lineage Analyst
Combines Python, SQL, and YAML analyzers to build a unified DataLineageGraph.
"""

import os
import logging
import networkx as nx
import sqlglot
from sqlglot import exp
import yaml
import re

from tree_sitter import Parser
from src.utils.language_loader import load_language

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# PythonDataFlowAnalyzer (already in your file, keep it as is)
# ----------------------------------------------------------------------
class PythonDataFlowAnalyzer:
    def __init__(self):
        self.language = load_language('python')
        self.parser = Parser()
        self.parser.set_language(self.language)

    def analyze_file(self, file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            code = f.read()
        try:
            tree = self.parser.parse(bytes(code, 'utf8'))
        except Exception as e:
            logger.error(f"Failed to parse {file_path}: {e}")
            return []
        return self._extract_data_operations(tree.root_node, code, file_path)

    def _extract_data_operations(self, root, code, file_path):
        results = []
        for node in self._walk(root):
            if node.type == 'call':
                func_name = self._get_func_name(node, code)
                if not func_name:
                    continue
                if func_name in ('pd.read_csv', 'pandas.read_csv',
                                 'pd.read_sql', 'pandas.read_sql',
                                 'pd.read_parquet', 'pandas.read_parquet'):
                    arg = self._extract_first_arg(node, code)
                    results.append(self._make_result('pandas', func_name, arg, node, file_path))
                elif func_name.endswith('.read.parquet') or func_name.endswith('.write.parquet'):
                    arg = self._extract_first_arg(node, code)
                    results.append(self._make_result('spark', func_name, arg, node, file_path))
                elif func_name.endswith('.execute'):
                    arg = self._extract_first_arg(node, code)
                    results.append(self._make_result('sqlalchemy', func_name, arg, node, file_path))
        return results

    def _walk(self, node):
        yield node
        for child in node.children:
            yield from self._walk(child)

    def _get_func_name(self, node, code):
        func_node = node.child_by_field_name('function')
        if not func_node:
            return ''
        names = []
        current = func_node
        while current:
            if current.type == 'attribute':
                attr_node = current.child_by_field_name('attribute')
                obj_node = current.child_by_field_name('object')
                if attr_node:
                    names.insert(0, code[attr_node.start_byte:attr_node.end_byte])
                current = obj_node
            elif current.type == 'identifier':
                names.insert(0, code[current.start_byte:current.end_byte])
                break
            else:
                break
        return '.'.join(names)

    def _extract_first_arg(self, node, code):
        args_node = node.child_by_field_name('arguments')
        if not args_node or len(args_node.children) == 0:
            return None
        for child in args_node.children:
            if child.type == 'string':
                return self._strip_quotes(code[child.start_byte:child.end_byte])
            elif child.type == 'f_string':
                return 'dynamic reference, cannot resolve (f-string)'
            elif child.type == 'identifier':
                return 'dynamic reference, cannot resolve (variable)'
            elif child.type == 'call':
                return 'dynamic reference, cannot resolve (call)'
        return 'dynamic reference, cannot resolve (complex)'

    def _strip_quotes(self, s):
        if s and len(s) >= 2 and s[0] in ('"', "'") and s[-1] in ('"', "'"):
            return s[1:-1]
        return s

    def _make_result(self, typ, func, dataset, node, file_path):
        return {
            'type': typ,
            'operation': func,
            'dataset': dataset,
            'line': node.start_point[0] + 1,
            'source_file': file_path
        }


# ----------------------------------------------------------------------
# SQLLineageAnalyzer (using sqlglot)
# ----------------------------------------------------------------------
class SQLLineageAnalyzer:
    def __init__(self, dialect=None):
        self.dialect = dialect or 'duckdb'

    def extract_lineage(self, file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            sql = f.read()
        try:
            parsed = sqlglot.parse_one(sql, dialect=self.dialect)
        except Exception as e:
            logger.warning(f"Failed to parse {file_path}: {e}")
            return {'target': None, 'sources': [], 'edges': []}

        output_table = self._extract_output_table(parsed, file_path)
        source_tables = self._extract_source_tables(parsed)
        edges = [(src, output_table) for src in source_tables if src != output_table]
        return {
            'target': output_table,
            'sources': source_tables,
            'edges': edges
        }

    def _extract_output_table(self, parsed, file_path):
        for node in parsed.find_all(exp.Create, exp.Insert):
            if isinstance(node, exp.Create) and node.this:
                return node.this.sql(dialect=self.dialect)
            if isinstance(node, exp.Insert) and node.this:
                return node.this.sql(dialect=self.dialect)
        import os
        return os.path.splitext(os.path.basename(file_path))[0]

    def _extract_source_tables(self, parsed):
        tables = set()
        for table in parsed.find_all(exp.Table):
            tables.add(table.sql(dialect=self.dialect))
        return list(tables)


# ----------------------------------------------------------------------
# DbtYamlAnalyzer (extracts ref/source from dbt YAML files)
# ----------------------------------------------------------------------
class DbtYamlAnalyzer:
    def extract_lineage(self, file_path):
        edges = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
        except Exception as e:
            logger.warning(f"Failed to parse YAML {file_path}: {e}")
            return edges

        if not data or not isinstance(data, dict):
            return edges

        # Extract from 'models' section: each model may have dependencies expressed via ref() in its SQL,
        # but also sometimes in YAML via 'depends_on'. For simplicity, we only extract explicit ref patterns from raw content.
        # Also look for sources defined.
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        ref_pattern = re.compile(r"ref\(['\"]([\w_]+)['\"]\)")
        source_pattern = re.compile(r"source\(['\"]([\w_]+)['\"],\s*['\"]([\w_]+)['\"]\)")
        for ref in ref_pattern.findall(content):
            edges.append((ref, os.path.basename(file_path).replace('.yml', '')))
        for m in source_pattern.findall(content):
            edges.append((f"{m[0]}.{m[1]}", os.path.basename(file_path).replace('.yml', '')))
        return edges


# ----------------------------------------------------------------------
# DataLineageGraph (NetworkX wrapper)
# ----------------------------------------------------------------------
class DataLineageGraph:
    def __init__(self):
        self.graph = nx.DiGraph()

    def add_edge(self, source, target, **attrs):
        self.graph.add_edge(source, target, **attrs)

    def add_node(self, node, **attrs):
        self.graph.add_node(node, **attrs)

    def blast_radius(self, node):
        if node not in self.graph:
            return []
        descendants = nx.descendants(self.graph, node)
        return list(descendants) + [node]

    def find_sources(self):
        return [n for n, d in self.graph.in_degree() if d == 0]

    def find_sinks(self):
        return [n for n, d in self.graph.out_degree() if d == 0]

    def to_json_serializable(self):
        return nx.node_link_data(self.graph)

    @classmethod
    def from_json(cls, data):
        g = cls()
        g.graph = nx.node_link_graph(data)
        return g


# ----------------------------------------------------------------------
# HydrologistAgent (main agent)
# ----------------------------------------------------------------------
class HydrologistAgent:
    def __init__(self):
        self.py_analyzer = PythonDataFlowAnalyzer()
        self.sql_analyzer = SQLLineageAnalyzer(dialect='duckdb')
        self.yaml_analyzer = DbtYamlAnalyzer()
        self.lineage_graph = DataLineageGraph()

    def analyze_repo(self, repo_path):
        """
        Walk the repository and collect lineage from all relevant files.
        Returns a DataLineageGraph.
        """
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
            dataset = op['dataset']
            if dataset and isinstance(dataset, str) and not dataset.startswith('dynamic'):
                self.lineage_graph.add_node(dataset, type='dataset')
                # For now, just record the node; edges will come from SQL/YAML

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