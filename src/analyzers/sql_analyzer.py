"""
Enhanced SQL lineage analyzer using sqlglot.
Supports CTEs, subqueries, dialect configuration, and dbt Jinja patterns.
Returns structured output with read/write distinction and line ranges.
"""

import os
import logging
import re
import sqlglot
from sqlglot import exp
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class SQLAnalyzer:
    def __init__(self, dialect: str = 'duckdb'):
        self.dialect = dialect

    def analyze_file(self, path: str) -> Dict[str, Any]:
        """
        Analyze a SQL file and return a dict with:
          - read_tables: list of tables read (SELECT, FROM, JOIN, etc.)
          - write_tables: list of tables written (CREATE, INSERT, etc.)
          - operations: list of DML/DDL operations with line ranges
          - errors: any parsing errors
        """
        try:
            with open(path, 'r', encoding='utf-8') as f:
                sql = f.read()
        except Exception as e:
            logger.error(f"Failed to read {path}: {e}")
            return {'read_tables': [], 'write_tables': [], 'operations': [], 'error': str(e)}

        # Preprocess for dbt Jinja (simple removal for now)
        sql_no_jinja = self._strip_jinja(sql)

        try:
            parsed = sqlglot.parse_one(sql_no_jinja, dialect=self.dialect)
        except Exception as e:
            logger.warning(f"Failed to parse {path}: {e}")
            # Even on parse error, try to extract ref/source via regex
            refs = self._extract_refs(sql)
            return {
                'read_tables': refs,
                'write_tables': [],
                'operations': [],
                'error': str(e)
            }

        # Analyze the parsed AST
        read_tables = self._extract_read_tables(parsed)
        write_tables = self._extract_write_tables(parsed)
        operations = self._extract_operations_with_lines(parsed, sql)

        # Also include dbt ref/source from raw text if present
        refs = self._extract_refs(sql)
        read_tables.extend(refs)

        return {
            'read_tables': list(set(read_tables)),
            'write_tables': list(set(write_tables)),
            'operations': operations,
            'error': None
        }

    def _strip_jinja(self, sql: str) -> str:
        """
        Crudely strip dbt Jinja templates by replacing {{ ref('model') }} with the model name.
        For better lineage, we'd need a proper Jinja parser, but this suffices for now.
        """
        # Replace {{ ref('model') }} with 'model'
        sql = re.sub(r"\{\{\s*ref\(['\"]([\w_]+)['\"]\)\s*\}\}", r"\1", sql)
        # Replace {{ source('src', 'table') }} with 'src.table'
        sql = re.sub(r"\{\{\s*source\(['\"]([\w_]+)['\"]\s*,\s*['\"]([\w_]+)['\"]\)\s*\}\}", r"\1.\2", sql)
        # Remove other Jinja blocks (for statements, etc.)
        sql = re.sub(r"\{\{.*?\}\}", "", sql, flags=re.DOTALL)
        sql = re.sub(r"\{%.*?%\}", "", sql, flags=re.DOTALL)
        return sql

    def _extract_read_tables(self, parsed) -> List[str]:
        """Extract tables that are read (in FROM, JOIN, subqueries, CTEs)."""
        tables = []
        for table in parsed.find_all(exp.Table):
            # Tables in FROM, JOIN, etc. are reads
            parent = table.parent
            if parent and parent.key in ('from', 'join'):
                tables.append(table.sql(dialect=self.dialect))
        return tables

    def _extract_write_tables(self, parsed) -> List[str]:
        """Extract tables that are written (CREATE, INSERT, etc.)."""
        writes = []
        for node in parsed.find_all(exp.Create, exp.Insert, exp.Update, exp.Delete, exp.Merge):
            if isinstance(node, exp.Create) and node.this:
                writes.append(node.this.sql(dialect=self.dialect))
            elif isinstance(node, exp.Insert) and node.this:
                writes.append(node.this.sql(dialect=self.dialect))
            elif isinstance(node, (exp.Update, exp.Delete, exp.Merge)):
                if hasattr(node, 'this') and node.this:
                    writes.append(node.this.sql(dialect=self.dialect))
        return writes

    def _extract_operations_with_lines(self, parsed, original_sql: str) -> List[Dict[str, Any]]:
        """Extract DML/DDL operations with line numbers (if available)."""
        ops = []
        for node in parsed.find_all(exp.Create, exp.Insert, exp.Update, exp.Delete, exp.Merge):
            op_type = node.key.upper()
            # Attempt to get line/col from node (sqlglot may provide this)
            start_line = node.start.line if hasattr(node, 'start') and node.start else None
            start_col = node.start.column if hasattr(node, 'start') and node.start else None
            end_line = node.end.line if hasattr(node, 'end') and node.end else None
            end_col = node.end.column if hasattr(node, 'end') and node.end else None
            ops.append({
                'type': op_type,
                'start_line': start_line,
                'start_col': start_col,
                'end_line': end_line,
                'end_col': end_col
            })
        return ops

    def _extract_refs(self, sql: str) -> List[str]:
        """Extract dbt ref() and source() calls using regex."""
        refs = []
        ref_pattern = re.compile(r"ref\(['\"]([\w_]+)['\"]\)")
        source_pattern = re.compile(r"source\(['\"]([\w_]+)['\"],\s*['\"]([\w_]+)['\"]\)")
        for ref in ref_pattern.findall(sql):
            refs.append(ref)
        for m in source_pattern.findall(sql):
            refs.append(f"{m[0]}.{m[1]}")
        return refs