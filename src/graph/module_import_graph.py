import os
import networkx as nx
from networkx.readwrite import json_graph


class ModuleImportGraph:
    """
    Directed graph of module import relationships using NetworkX.
    Nodes are module paths; edges represent imports (from_module imports to_module).
    Provides PageRank and circular dependency detection.
    """
    def __init__(self):
        self.graph = nx.DiGraph()
        print("[DEBUG] Initialized ModuleImportGraph.")

    def add_module(self, module_path: str):
        """Add a module node to the graph."""
        try:
            self.graph.add_node(module_path)
            print(f"[DEBUG] Added module node: {module_path}")
        except Exception as e:
            import traceback
            print(f"[ModuleImportGraph] Error adding module {module_path}:")
            traceback.print_exc()

    def add_import(self, from_module: str, to_module: str):
        """Add an import edge (from_module imports to_module), skipping self-loops."""
        try:
            if from_module == to_module:
                print(f"[DEBUG] Skipping self-loop edge: {from_module} -> {to_module}")
                return
            self.graph.add_edge(from_module, to_module)
            print(f"[DEBUG] Added import edge: {from_module} -> {to_module}")
        except Exception as e:
            import traceback
            print(f"[ModuleImportGraph] Error adding import {from_module} -> {to_module}:")
            traceback.print_exc()

    def pagerank(self):
        """Compute PageRank for modules (importance as import hubs)."""
        try:
            pr = nx.pagerank(self.graph)
            print(f"[DEBUG] Computed PageRank: {pr}")
            return pr
        except Exception as e:
            import traceback
            print("[ModuleImportGraph] Error computing pagerank:")
            traceback.print_exc()
            return {}

    def strongly_connected_components(self):
        """Find circular dependencies (strongly connected components >1 node)."""
        try:
            scc = [list(c) for c in nx.strongly_connected_components(self.graph) if len(c) > 1]
            print(f"[DEBUG] Strongly connected components: {scc}")
            return scc
        except Exception as e:
            import traceback
            print("[ModuleImportGraph] Error finding strongly connected components:")
            traceback.print_exc()
            return []

    def to_json(self, path: str):
        """Serialize the graph to JSON at the given path."""
        try:
            data = json_graph.node_link_data(self.graph)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                import json
                json.dump(data, f, indent=2)
            print(f"[DEBUG] Exported module graph to {path}")
        except Exception as e:
            import traceback
            print(f"[ModuleImportGraph] Error exporting graph to {path}:")
            traceback.print_exc()
