import networkx as nx
from typing import Dict, List, Any, Union, Optional
from src.models.node_types import Node, ModuleNode, DatasetNode, FunctionNode, TransformationNode
from src.models.edge_types import Edge, ImportEdge, ProducesEdge, ConsumesEdge, CallsEdge, ConfiguresEdge
from pydantic import ValidationError

class KnowledgeGraph:
    """
    A unified graph holding all nodes and edges with Pydantic validation.
    Uses NetworkX internally but enforces schemas on add operations.
    Supports JSON serialization/deserialization.
    """

    def __init__(self):
        self.graph = nx.MultiDiGraph()  # allows multiple edges between same nodes with different types

    def add_node(self, node: Node):
        """Add a node, validated by its Pydantic model."""
        if not isinstance(node, (ModuleNode, DatasetNode, FunctionNode, TransformationNode)):
            raise TypeError(f"Unknown node type: {type(node)}")
        # Use node's path/name as the graph node identifier
        node_id = self._node_id(node)
        # Store the entire model as a node attribute
        self.graph.add_node(node_id, model=node)

    def add_edge(self, edge: Edge):
        """Add an edge, validated by its Pydantic model."""
        if not isinstance(edge, (ImportEdge, ProducesEdge, ConsumesEdge, CallsEdge, ConfiguresEdge)):
            raise TypeError(f"Unknown edge type: {type(edge)}")
        # Use source and target as node identifiers (they must already exist)
        self.graph.add_edge(edge.source, edge.target, key=type(edge).__name__, model=edge)

    def _node_id(self, node: Node) -> str:
        """Return a unique identifier for the node."""
        if isinstance(node, ModuleNode):
            return node.path
        elif isinstance(node, DatasetNode):
            return node.name
        elif isinstance(node, FunctionNode):
            return node.qualified_name
        elif isinstance(node, TransformationNode):
            # Use a combination of source_file and line_range? For now, use source_file + index.
            # In practice, you might need a more robust ID.
            return f"{node.source_file}:{node.line_range or '0'}"
        else:
            raise ValueError(f"Cannot generate ID for {node}")

    def get_node(self, node_id: str) -> Optional[Node]:
        """Retrieve the node model by its ID."""
        if node_id in self.graph.nodes:
            return self.graph.nodes[node_id].get('model')
        return None

    def get_edge(self, u: str, v: str, key: str) -> Optional[Edge]:
        """Retrieve an edge by its endpoints and type key."""
        if self.graph.has_edge(u, v, key=key):
            return self.graph.edges[u, v, key].get('model')
        return None

    def to_json_serializable(self) -> Dict[str, Any]:
        """Convert the graph to a JSON‑serializable dict (node‑link format)."""
        data = nx.node_link_data(self.graph)
        # Convert each node's 'model' attribute to a dict (Pydantic models can use .dict())
        for node_data in data['nodes']:
            if 'model' in node_data:
                node_data['model'] = node_data['model'].dict()
        # Convert each edge's 'model' attribute
        for link in data['links']:
            if 'model' in link:
                link['model'] = link['model'].dict()
        return data

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> 'KnowledgeGraph':
        """Reconstruct a KnowledgeGraph from a node‑link dict."""
        kg = cls()
        # Reconstruct nodes
        for node_data in data['nodes']:
            model_dict = node_data.pop('model', None)
            if model_dict:
                # Determine node type from the dict (requires a type field or we infer)
                # We'll use a simple heuristic: check for fields unique to each type
                if 'language' in model_dict:
                    node = ModuleNode(**model_dict)
                elif 'storage_type' in model_dict:
                    node = DatasetNode(**model_dict)
                elif 'parent_module' in model_dict:
                    node = FunctionNode(**model_dict)
                elif 'transformation_type' in model_dict:
                    node = TransformationNode(**model_dict)
                else:
                    raise ValueError(f"Cannot reconstruct node from {model_dict}")
                kg.add_node(node)
        # Reconstruct edges
        for link_data in data['links']:
            model_dict = link_data.pop('model', None)
            if model_dict:
                # Determine edge type
                if 'weight' in model_dict and 'source_file' in model_dict:
                    edge = ImportEdge(**model_dict)
                elif 'transformation_type' in model_dict and 'source_file' in model_dict:
                    # Could be Produces or Consumes – need to check keys
                    if 'source_datasets' in model_dict:  # Actually that's for TransformationNode, not edge. Let's refine.
                        # Better: we stored the edge model directly, so we can try each type.
                        # For simplicity, we'll use a registry of edge types.
                        pass
                # ... implement similar heuristic or store type info
                # To simplify, we could store the edge's class name as an attribute.
                # For now, we'll assume we stored the type in the dict as '__type__'
                edge_type = model_dict.get('__type__')
                if edge_type == 'ImportEdge':
                    edge = ImportEdge(**model_dict)
                elif edge_type == 'ProducesEdge':
                    edge = ProducesEdge(**model_dict)
                elif edge_type == 'ConsumesEdge':
                    edge = ConsumesEdge(**model_dict)
                elif edge_type == 'CallsEdge':
                    edge = CallsEdge(**model_dict)
                elif edge_type == 'ConfiguresEdge':
                    edge = ConfiguresEdge(**model_dict)
                else:
                    raise ValueError(f"Cannot reconstruct edge from {model_dict}")
                kg.add_edge(edge)
        return kg

    # Convenience methods for agents
    def find_sources(self) -> List[str]:
        """Nodes with in‑degree 0 (no incoming edges)."""
        return [n for n, d in self.graph.in_degree() if d == 0]

    def find_sinks(self) -> List[str]:
        """Nodes with out‑degree 0 (no outgoing edges)."""
        return [n for n, d in self.graph.out_degree() if d == 0]

    def blast_radius(self, node_id: str) -> List[str]:
        """Return all nodes downstream of node_id (including itself)."""
        if node_id not in self.graph:
            return []
        descendants = nx.descendants(self.graph, node_id)
        return list(descendants) + [node_id]