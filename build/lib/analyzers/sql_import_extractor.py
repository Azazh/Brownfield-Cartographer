"""
SQL Import Extractor – extracts table dependencies from SQL files using sqlglot.
"""

import os
import sqlglot
from sqlglot import exp
import logging

logger = logging.getLogger(__name__)

class SQLImportExtractor:
    """
    Extracts table names (sources) from a SQL file.
    Returns a list of table names referenced in FROM, JOIN, and CTE clauses.
    """

    def __init__(self, dialect=None):
        # Set the SQL dialect to match your target (e.g., 'snowflake', 'bigquery', 'duckdb')
        self.dialect = dialect or 'duckdb'

    def extract_imports(self, file_path):
        """
        Parse the SQL file and return a list of table names that are read/imported.
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            sql = f.read()

        try:
            parsed = sqlglot.parse_one(sql, dialect=self.dialect)
        except Exception as e:
            logger.warning(f"Failed to parse {file_path}: {e}")
            return []

        # Find all table expressions (sources)
        tables = set()
        for table in parsed.find_all(exp.Table):
            # table.sql() returns the fully qualified name
            tables.add(table.sql(dialect=self.dialect))

        return list(tables)