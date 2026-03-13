import logging
from typing import List, Optional, Dict, Any
from src.graph.knowledge_graph import KnowledgeGraph
from src.models.node_types import ModuleNode, DatasetNode, FunctionNode, TransformationNode

logger = logging.getLogger(__name__)

class NavigatorAgent:
    """
    LangGraph-style agent for codebase querying. Provides four tools:
    - find_implementation(concept): semantic search for business logic
    - trace_lineage(dataset, direction): graph traversal for data lineage
    - blast_radius(module_path): graph traversal for downstream dependencies
    - explain_module(path): generative explanation of a module
    All answers cite source files, line ranges, and analysis method (static vs LLM).
    """
    def __init__(self, knowledge_graph: KnowledgeGraph, vector_store=None, semanticist=None):
        self.kg = knowledge_graph
        self.vector_store = vector_store  # Should support semantic search over purpose statements
        self.semanticist = semanticist    # For LLM-powered explanations

    def find_implementation(self, concept: str) -> Dict[str, Any]:
        """Semantic search for where a business concept is implemented."""
        # Use vector store if available, else fallback to purpose_statement substring search
        results = []
        if self.vector_store:
            hits = self.vector_store.search(concept, top_k=5)
            for hit in hits:
                node = self.kg.get_node(hit['node_id'])
                if node:
                    results.append({
                        'path': getattr(node, 'path', None),
                        'purpose_statement': getattr(node, 'purpose_statement', None),
                        'score': hit.get('score'),
                        'analysis_method': 'LLM (semantic search)'
                    })
        else:
            # Fallback: scan all ModuleNodes for concept in purpose_statement
            for node_id in self.kg.graph.nodes:
                node = self.kg.get_node(node_id)
                if isinstance(node, ModuleNode) and node.purpose_statement and concept.lower() in node.purpose_statement.lower():
                    results.append({
                        'path': node.path,
                        'purpose_statement': node.purpose_statement,
                        'score': 1.0,
                        'analysis_method': 'LLM (purpose_statement substring)'
                    })
        return {'results': results}

    def trace_lineage(self, dataset: str, direction: str = 'upstream') -> Dict[str, Any]:
        """Trace lineage for a dataset (upstream or downstream)."""
        # Find the node
        node = self.kg.get_node(dataset)
        if not node:
            return {'error': f'Dataset {dataset} not found'}
        # Traverse the graph
        if direction == 'upstream':
            # All ancestors
            ancestors = list(nx.ancestors(self.kg.graph, dataset))
            method = 'static (graph traversal)'
            return {'dataset': dataset, 'upstream': ancestors, 'analysis_method': method}
        else:
            # All descendants
            descendants = list(nx.descendants(self.kg.graph, dataset))
            method = 'static (graph traversal)'
            return {'dataset': dataset, 'downstream': descendants, 'analysis_method': method}

    def blast_radius(self, module_path: str) -> Dict[str, Any]:
        """Return all nodes that would be affected if this module changes."""
        affected = self.kg.blast_radius(module_path)
        return {
            'module': module_path,
            'affected_nodes': affected,
            'analysis_method': 'static (graph traversal)'
        }

    def explain_module(self, path: str) -> Dict[str, Any]:
        """Return a generative explanation of a module, citing source and method."""
        node = self.kg.get_node(path)
        if not node or not isinstance(node, ModuleNode):
            return {'error': f'Module {path} not found'}
        # Use LLM if available
        if self.semanticist:
            explanation = self.semanticist._generate_purpose_statement(self._read_file(node.path), node.purpose_statement or "")
            method = 'LLM (purpose_statement)'
        else:
            explanation = node.purpose_statement or "No purpose statement available."
            method = 'LLM (cached purpose_statement)'
        return {
            'module': path,
            'explanation': explanation,
            'analysis_method': method
        }

    def _read_file(self, path: str) -> str:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.warning(f"Could not read {path}: {e}")
            return ""
