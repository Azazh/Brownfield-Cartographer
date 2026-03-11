import os
import logging
import sqlglot
from sqlglot import exp
import yaml
import re
from tree_sitter import Parser
from src.utils.language_loader import load_language
from src.graph.knowledge_graph import KnowledgeGraph
from src.models.node_types import DatasetNode, TransformationNode
from src.models.edge_types import ProducesEdge, ConsumesEdge

logger = logging.getLogger(__name__)

class PythonDataFlowAnalyzer:
    # ... (keep as previously defined, with the _make_result fix for line number)
    def __init__(self):
        self.language = load_language('python')
        self.parser = Parser()
        self.parser.set_language(self.language)

    def analyze_file(self, file_path):
        # ... (unchanged)
        pass

    # ... (all other methods unchanged, but ensure _make_result uses tuple access)
    def _make_result(self, typ, func, dataset, node, file_path):
        return {
            'type': typ,
            'operation': func,
            'dataset': dataset,
            'line': node.start_point[0] + 1,   # tuple indexing
            'source_file': file_path
        }

class SQLLineageAnalyzer:
    # ... (keep as before)
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
        return {
            'target': output_table,
            'sources': source_tables,
        }

    def _extract_output_table(self, parsed, file_path):
        for node in parsed.find_all(exp.Create, exp.Insert):
            if isinstance(node, exp.Create) and node.this:
                return node.this.sql(dialect=self.dialect)
            if isinstance(node, exp.Insert) and node.this:
                return node.this.sql(dialect=self.dialect)
        return os.path.splitext(os.path.basename(file_path))[0]

    def _extract_source_tables(self, parsed):
        tables = set()
        for table in parsed.find_all(exp.Table):
            tables.add(table.sql(dialect=self.dialect))
        return list(tables)

class DbtYamlAnalyzer:
    def extract_lineage(self, file_path):
        edges = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
        except Exception as e:
            logger.warning(f"Failed to parse YAML {file_path}: {e}")
            return edges
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        ref_pattern = re.compile(r"ref\(['\"]([\w_]+)['\"]\)")
        source_pattern = re.compile(r"source\(['\"]([\w_]+)['\"],\s*['\"]([\w_]+)['\"]\)")
        model_name = os.path.basename(file_path).replace('.yml', '')
        for ref in ref_pattern.findall(content):
            edges.append(('ref', ref, model_name))
        for m in source_pattern.findall(content):
            edges.append(('source', f"{m[0]}.{m[1]}", model_name))
        return edges

class HydrologistAgent:
    def __init__(self, knowledge_graph: KnowledgeGraph):
        self.kg = knowledge_graph
        self.py_analyzer = PythonDataFlowAnalyzer()
        self.sql_analyzer = SQLLineageAnalyzer(dialect='duckdb')
        self.yaml_analyzer = DbtYamlAnalyzer()

    def analyze_repo(self, repo_path):
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
            dataset_name = op['dataset']
            if dataset_name and isinstance(dataset_name, str) and not dataset_name.startswith('dynamic'):
                # Create DatasetNode if not exists
                dataset_node = DatasetNode(name=dataset_name, storage_type='file')
                self.kg.add_node(dataset_node)
                # For now, we don't create TransformationNode for Python operations
                # (could be added later)

    def _process_sql(self, file_path):
        lineage = self.sql_analyzer.extract_lineage(file_path)
        target = lineage['target']
        sources = lineage['sources']

        if not target:
            return

        # Create target dataset node
        target_node = DatasetNode(name=target, storage_type='table')
        self.kg.add_node(target_node)

        # Create source dataset nodes
        for src in sources:
            src_node = DatasetNode(name=src, storage_type='table')
            self.kg.add_node(src_node)

        # Create a transformation node for this SQL file
        trans_node = TransformationNode(
            source_datasets=sources,
            target_datasets=[target],
            transformation_type='sql',
            source_file=file_path
        )
        self.kg.add_node(trans_node)

        # Add edges: source -> transformation (consumes) and transformation -> target (produces)
        for src in sources:
            consume_edge = ConsumesEdge(
                source=file_path,          # using file path as transformation identifier
                target=src,
                transformation_type='sql',
                source_file=file_path
            )
            self.kg.add_edge(consume_edge)

        produce_edge = ProducesEdge(
            source=file_path,
            target=target,
            transformation_type='sql',
            source_file=file_path
        )
        self.kg.add_edge(produce_edge)

    def _process_yaml(self, file_path):
        edges = self.yaml_analyzer.extract_lineage(file_path)
        for etype, src, tgt in edges:
            src_node = DatasetNode(name=src, storage_type='table')
            tgt_node = DatasetNode(name=tgt, storage_type='table')
            self.kg.add_node(src_node)
            self.kg.add_node(tgt_node)

            # Create a transformation node for the YAML config (or treat as direct edge)
            trans_node = TransformationNode(
                source_datasets=[src],
                target_datasets=[tgt],
                transformation_type='dbt_yaml',
                source_file=file_path
            )
            self.kg.add_node(trans_node)

            consume_edge = ConsumesEdge(
                source=file_path,
                target=src,
                transformation_type='dbt_yaml',
                source_file=file_path
            )
            produce_edge = ProducesEdge(
                source=file_path,
                target=tgt,
                transformation_type='dbt_yaml',
                source_file=file_path
            )
            self.kg.add_edge(consume_edge)
            self.kg.add_edge(produce_edge)