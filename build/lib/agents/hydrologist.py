"""
Hydrologist Agent: Phase 2 – Data Lineage Analyst
Combines Python, SQL, and YAML analyzers to build a unified DataLineageGraph.
Now with enriched edge metadata and more detailed Python data flow analysis.
"""

import os
import logging
from tree_sitter import Parser
from src.utils.language_loader import load_language
from src.graph.knowledge_graph import KnowledgeGraph
from src.models.node_types import DatasetNode, TransformationNode
from src.models.edge_types import ConsumesEdge, ProducesEdge
from src.analyzers.sql_analyzer import SQLAnalyzer
from src.analyzers.yaml_analyzer import YAMLAnalyzer

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# PythonDataFlowAnalyzer – extracts data operations from Python files
# ----------------------------------------------------------------------
class PythonDataFlowAnalyzer:
    """
    Analyzes Python files to find calls to data‑related functions:
      - pandas.read_csv, pandas.read_sql, pandas.read_parquet
      - df.to_csv, df.to_parquet (write operations)
      - spark.read.parquet, spark.write.csv
      - sqlalchemy.execute()
    Extracts dataset name, operation type, line range, and assignment target.
    """

    def __init__(self):
        self.language = load_language('python')
        self.parser = Parser()
        self.parser.set_language(self.language)

    def analyze_file(self, file_path):
        """Return a list of operation records (dicts)."""
        with open(file_path, 'r', encoding='utf-8') as f:
            code = f.read()
        try:
            tree = self.parser.parse(bytes(code, 'utf8'))
        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}", exc_info=True)
            return []
        return self._extract_data_operations(tree.root_node, code, file_path)
    def analyze_repo(self, repo_path):
        file_paths = []
        total_files = 0
        for root, _, files in os.walk(repo_path):
            for fname in files:
                total_files += 1
        processed = 0
        for root, _, files in os.walk(repo_path):
            for fname in files:
                processed += 1
                if processed % 100 == 0:
                    logger.info(f"Surveyor: processed {processed}/{total_files} files")
                # ... process file ...
        logger.info(f"Surveyor finished. Processed {processed} files.")

    def _extract_data_operations(self, root, code, file_path):
        results = []
        for node in self._walk(root):
            if node.type == 'call':
                func_name = self._get_func_name(node, code)
                if not func_name:
                    continue
                # Determine operation type and subtype
                op_type = self._categorize_operation(func_name)
                if op_type is None:
                    continue
                subtype = op_type['subtype']
                typ = op_type['type']
                dataset = self._extract_first_arg(node, code)
                target_var = self._get_assignment_target(node, code)
                line_range = f"{node.start_point[0]+1}-{node.end_point[0]+1}"
                results.append({
                    'type': typ,
                    'subtype': subtype,
                    'operation': func_name,
                    'dataset': dataset,
                    'target_variable': target_var,
                    'line': node.start_point[0] + 1,
                    'line_range': line_range,
                    'source_file': file_path
                })
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

    def _categorize_operation(self, func_name):
        """Return a dict {'type': 'pandas'|'spark'|'sqlalchemy', 'subtype': 'read'|'write'|'execute'} or None."""
        f = func_name.lower()
        if 'pandas' in f or 'pd.' in f:
            if 'read_' in f:
                return {'type': 'pandas', 'subtype': 'read'}
            elif 'to_' in f:
                return {'type': 'pandas', 'subtype': 'write'}
        elif 'spark' in f:
            if '.read.' in f:
                return {'type': 'spark', 'subtype': 'read'}
            elif '.write.' in f:
                return {'type': 'spark', 'subtype': 'write'}
        elif 'sqlalchemy' in f or '.execute' in f:
            return {'type': 'sqlalchemy', 'subtype': 'execute'}
        return None

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

    def _get_assignment_target(self, node, code):
        """If the call is part of an assignment, return the variable name."""
        parent = node.parent
        while parent:
            if parent.type == 'assignment':
                left = parent.child_by_field_name('left')
                if left and left.type == 'identifier':
                    return code[left.start_byte:left.end_byte]
            parent = parent.parent
        return None

# ----------------------------------------------------------------------
# HydrologistAgent – main agent that uses all analyzers and builds the KG
# ----------------------------------------------------------------------
class HydrologistAgent:
    def __init__(self, knowledge_graph: KnowledgeGraph, sql_dialect: str = 'duckdb'):
        self.kg = knowledge_graph
        self.sql_analyzer = SQLAnalyzer(dialect=sql_dialect)
        self.py_analyzer = PythonDataFlowAnalyzer()
        self.yaml_analyzer = YAMLAnalyzer()

    def analyze_repo(self, repo_path):
        """Walk the repository and add lineage nodes/edges to the knowledge graph."""
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

    def _process_python(self, file_path):
        operations = self.py_analyzer.analyze_file(file_path)
        for op in operations:
            dataset = op['dataset']
            if not dataset or not isinstance(dataset, str) or dataset.startswith('dynamic'):
                continue

            # Create a DatasetNode for the file/table
            ds_node = DatasetNode(name=dataset, storage_type='file')
            self.kg.add_node(ds_node)

            # Create a TransformationNode for this operation
            trans_node = TransformationNode(
                source_datasets=[dataset] if op['subtype'] == 'read' else [],
                target_datasets=[dataset] if op['subtype'] == 'write' else [],
                transformation_type=op['type'],
                source_file=file_path,
                line_range=op.get('line_range')
            )
            self.kg.add_node(trans_node)

            # Add edge based on subtype
            if op['subtype'] == 'read':
                edge = ConsumesEdge(
                    source=file_path,          # using file path as transformation ID
                    target=dataset,
                    transformation_type=op['type'],
                    source_file=file_path,
                    line_range=op.get('line_range')
                )
                self.kg.add_edge(edge)
            elif op['subtype'] == 'write':
                edge = ProducesEdge(
                    source=file_path,
                    target=dataset,
                    transformation_type=op['type'],
                    source_file=file_path,
                    line_range=op.get('line_range')
                )
                self.kg.add_edge(edge)
            # For 'execute', we don't create a dataset edge (could be added later)

    def _process_sql(self, file_path):
        result = self.sql_analyzer.analyze_file(file_path)
        if not result or result.get('error'):
            return

        read_tables = result.get('read_tables', [])
        write_tables = result.get('write_tables', [])
        operations = result.get('operations', [])

        # If no explicit write tables, assume the file name is the target (common in dbt)
        if not write_tables:
            target = os.path.splitext(os.path.basename(file_path))[0]
            write_tables = [target]

        # Create dataset nodes and edges
        for target in write_tables:
            target_node = DatasetNode(name=target, storage_type='table')
            self.kg.add_node(target_node)

            for src in read_tables:
                src_node = DatasetNode(name=src, storage_type='table')
                self.kg.add_node(src_node)

                # Create transformation node for this SQL file
                trans_node = TransformationNode(
                    source_datasets=[src],
                    target_datasets=[target],
                    transformation_type='sql',
                    source_file=file_path,
                    line_range=None  # could be derived from operations
                )
                self.kg.add_node(trans_node)

                # Add consumes edge (source → transformation)
                consume = ConsumesEdge(
                    source=file_path,
                    target=src,
                    transformation_type='sql',
                    source_file=file_path,
                    line_range=None
                )
                self.kg.add_edge(consume)

                # Add produces edge (transformation → target)
                produce = ProducesEdge(
                    source=file_path,
                    target=target,
                    transformation_type='sql',
                    source_file=file_path,
                    line_range=None
                )
                self.kg.add_edge(produce)

    def _process_yaml(self, file_path):
        result = self.yaml_analyzer.analyze_file(file_path)
        if not result or result.get('error'):
            return

        for dep in result.get('dependencies', []):
            dep_type, dep_name = dep
            model_name = os.path.basename(file_path).replace('.yml', '')
            if dep_type == 'ref':
                src = dep_name
                tgt = model_name
            else:  # source
                src = dep_name
                tgt = model_name

            # Create dataset nodes
            src_node = DatasetNode(name=src, storage_type='table')
            tgt_node = DatasetNode(name=tgt, storage_type='table')
            self.kg.add_node(src_node)
            self.kg.add_node(tgt_node)

            # Create transformation node for this YAML configuration
            trans_node = TransformationNode(
                source_datasets=[src],
                target_datasets=[tgt],
                transformation_type='dbt_yaml',
                source_file=file_path,
                line_range=None
            )
            self.kg.add_node(trans_node)

            # Add edges
            consume = ConsumesEdge(
                source=file_path,
                target=src,
                transformation_type='dbt_yaml',
                source_file=file_path,
                line_range=None
            )
            produce = ProducesEdge(
                source=file_path,
                target=tgt,
                transformation_type='dbt_yaml',
                source_file=file_path,
                line_range=None
            )
            self.kg.add_edge(consume)
            self.kg.add_edge(produce)