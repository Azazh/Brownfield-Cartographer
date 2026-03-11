import os
import logging
import sqlglot
from sqlglot import exp
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class SQLAnalyzer:
    """
    Analyzes SQL files using sqlglot to extract table dependencies.
    Provides structured output similar to a tree‑sitter analyzer.
    """

    def __init__(self, dialect: str = 'duckdb'):
        self.dialect = dialect

    def analyze_file(self, path: str) -> Optional[Dict[str, Any]]:
        """
        Return a dict with:
          - tables: list of table names referenced
          - operations: list of DML/DDL operations
          - errors: any parsing errors
        """
        try:
            with open(path, 'r', encoding='utf-8') as f:
                sql = f.read()
        except Exception as e:
            logger.error(f"Failed to read {path}: {e}")
            return None

        try:
            parsed = sqlglot.parse_one(sql, dialect=self.dialect)
        except Exception as e:
            logger.warning(f"Failed to parse {path}: {e}")
            return {'tables': [], 'operations': [], 'error': str(e)}

        tables = self._extract_tables(parsed)
        operations = self._extract_operations(parsed)

        return {
            'tables': tables,
            'operations': operations,
            'error': None
        }

    def _extract_tables(self, parsed) -> List[str]:
        tables = set()
        for table in parsed.find_all(exp.Table):
            tables.add(table.sql(dialect=self.dialect))
        return list(tables)

    def _extract_operations(self, parsed) -> List[str]:
        ops = []
        for node in parsed.find_all(exp.Create, exp.Insert, exp.Update, exp.Delete, exp.Merge):
            ops.append(node.key.upper())
        return ops