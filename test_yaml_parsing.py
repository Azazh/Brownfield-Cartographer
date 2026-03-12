import sys
import os
from src.analyzers.tree_sitter_analyzer import TreeSitterAnalyzer

def main():
    yaml_code = """
    foo: 1
    bar:
      - baz
      - qux: 2
    """
    analyzer = TreeSitterAnalyzer()
    root = analyzer.analyze(yaml_code, 'yaml')
    print("YAML AST Root:", root)
    # Optionally, extract top-level keys using the analyzer's method if available
    if hasattr(analyzer, '_analyze_yaml'):
      result = analyzer._analyze_yaml(root, yaml_code, '<test>')
      print("Extracted top-level keys:", result.get('top_level_keys'))

if __name__ == "__main__":
    main()
