# src/analyzers/sql_lineage.py
import sqlglot
from sqlglot import exp
import logging

logger = logging.getLogger(__name__)

class SQLLineageAnalyzer:
    """
    Extracts table dependencies from a SQL file using sqlglot.
    Returns a list of edges (source, target) representing data flow.
    For a typical dbt model, the target is the model itself.
    """
    def __init__(self, dialect=None):
        # Set dialect based on your target (e.g., 'snowflake', 'bigquery', 'duckdb')
        self.dialect = dialect or 'duckdb'

    def extract_lineage(self, file_path):
        """
        Returns a dict: {
            'target': output_table_name,
            'sources': [list of input table names],
            'edges': [(source, target)]
        }
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            sql = f.read()
        try:
            # Parse into AST
            parsed = sqlglot.parse_one(sql, dialect=self.dialect)
        except Exception as e:
            logger.warning(f"Failed to parse {file_path}: {e}")
            return {'target': None, 'sources': [], 'edges': []}

        # Infer output table name: usually the last CREATE or INSERT target.
        # For a simple SELECT, there is no output – we'll treat the file name as target.
        output_table = self._extract_output_table(parsed, file_path)

        # Extract all table names referenced in FROM/JOIN
        source_tables = self._extract_source_tables(parsed)

        edges = [(src, output_table) for src in source_tables if src != output_table]
        return {
            'target': output_table,
            'sources': source_tables,
            'edges': edges
        }

    def _extract_output_table(self, parsed, file_path):
        """
        Heuristics to find the table being written.
        Looks for CREATE TABLE, INSERT INTO, etc.
        Fallback: file name (without extension).
        """
        # Find all top-level DDL/DML that define an output
        for node in parsed.find_all(exp.Create, exp.Insert):
            if isinstance(node, exp.Create):
                # CREATE TABLE table_name AS ...
                if node.this:
                    return node.this.sql(dialect=self.dialect)
            elif isinstance(node, exp.Insert):
                # INSERT INTO table_name ...
                if node.this:
                    return node.this.sql(dialect=self.dialect)
        # If no explicit output, use file stem
        import os
        return os.path.splitext(os.path.basename(file_path))[0]

    def _extract_source_tables(self, parsed):
        """
        Recursively find all table names in FROM, JOIN, and subqueries.
        """
        tables = set()
        for node in parsed.find_all(exp.Table):
            # Table name could be quoted, sqlglot extracts correctly
            tables.add(node.sql(dialect=self.dialect))
        return list(tables)