import os
import logging
import yaml
import re
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class YAMLAnalyzer:
    """
    Analyzes YAML files (especially dbt schema.yml) to extract ref/source dependencies.
    Provides structured output.
    """

    def analyze_file(self, path: str) -> Optional[Dict[str, Any]]:
        """
        Return a dict with:
          - models: list of model names defined
          - sources: list of source tables defined
          - dependencies: list of (source, target) tuples from ref/source calls
        """
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            logger.error(f"Failed to read {path}: {e}")
            return None

        try:
            data = yaml.safe_load(content)
        except Exception as e:
            logger.warning(f"Failed to parse YAML {path}: {e}")
            return {'models': [], 'sources': [], 'dependencies': [], 'error': str(e)}

        models = []
        sources = []
        dependencies = []

        # Extract models
        if data and isinstance(data, dict):
            for model in data.get('models', []):
                if isinstance(model, dict):
                    models.append(model.get('name'))
            for src in data.get('sources', []):
                if isinstance(src, dict):
                    src_name = src.get('name')
                    for table in src.get('tables', []):
                        sources.append(f"{src_name}.{table.get('name')}")

        # Extract ref/source from raw text (for Jinja)
        ref_pattern = re.compile(r"ref\(['\"]([\w_]+)['\"]\)")
        source_pattern = re.compile(r"source\(['\"]([\w_]+)['\"],\s*['\"]([\w_]+)['\"]\)")
        for ref in ref_pattern.findall(content):
            dependencies.append(('ref', ref))
        for m in source_pattern.findall(content):
            dependencies.append(('source', f"{m[0]}.{m[1]}"))

        return {
            'models': models,
            'sources': sources,
            'dependencies': dependencies,
            'error': None
        }