# src/analyzers/dag_config_parser.py
import yaml
import os
import re
import logging

logger = logging.getLogger(__name__)

class DbtYamlAnalyzer:
    """
    Parses dbt schema.yml files to extract model dependencies.
    """
    def extract_lineage(self, file_path):
        """
        Returns a list of edges (source, target) where source is a ref/source and target is the model name.
        """
        edges = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
        except Exception as e:
            logger.warning(f"Failed to parse YAML {file_path}: {e}")
            return edges

        if not data or not isinstance(data, dict):
            return edges

        # Look for 'models' section
        models = data.get('models', [])
        for model in models:
            if not isinstance(model, dict):
                continue
            model_name = model.get('name')
            if not model_name:
                continue
            # Check for 'ref' or 'source' in description or config? In schema.yml, dependencies are usually in the SQL, not YAML.
            # Actually, dbt schema.yml rarely contains explicit dependencies. They are in the SQL files.
            # The YAML can define sources, though: e.g., sources: [name: source_name, tables: ...]
            # For now, we'll use YAML only to register source tables.
            sources_section = model.get('sources', [])
            for src in sources_section:
                if not isinstance(src, dict):
                    continue
                source_name = src.get('name')
                if source_name:
                    edges.append((source_name, model_name))  # source -> model

        # Also look for 'sources' top-level
        sources_top = data.get('sources', [])
        for src in sources_top:
            if not isinstance(src, dict):
                continue
            src_name = src.get('name')
            tables = src.get('tables', [])
            for tbl in tables:
                if not isinstance(tbl, dict):
                    continue
                table_name = tbl.get('name')
                if src_name and table_name:
                    # This defines a source table, but not an edge yet.
                    # We'll store this as a source node.
                    pass  # We'll handle in graph building

        return edges