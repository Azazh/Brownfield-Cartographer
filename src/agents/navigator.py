
import logging
import networkx as nx
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
        """Semantic search for where a business concept is implemented, with evidence citations."""
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
                        'line_range': getattr(node, 'line_range', None) if hasattr(node, 'line_range') else None,
                        'analysis_method': 'LLM (semantic search)'
                    })
        else:
            for node_id in self.kg.graph.nodes:
                node = self.kg.get_node(node_id)
                if isinstance(node, ModuleNode) and node.purpose_statement and concept.lower() in node.purpose_statement.lower():
                    results.append({
                        'path': node.path,
                        'purpose_statement': node.purpose_statement,
                        'score': 1.0,
                        'line_range': getattr(node, 'line_range', None) if hasattr(node, 'line_range') else None,
                        'analysis_method': 'LLM (purpose_statement substring)'
                    })
        return {'results': results}

    def trace_lineage(self, dataset: str, direction: str = 'upstream') -> Dict[str, Any]:
        """Trace lineage for a dataset (upstream or downstream), with evidence citations."""
        node = self.kg.get_node(dataset)
        if not node:
            return {'error': f'Dataset {dataset} not found'}
        method = 'static (graph traversal)'
        results = []
        if direction == 'upstream':
            ancestors = list(nx.ancestors(self.kg.graph, dataset))
            for anc in ancestors:
                anc_node = self.kg.get_node(anc)
                # Try to find the edge from anc to dataset for evidence
                edge_data = None
                for key in self.kg.graph[anc][dataset]:
                    edge = self.kg.graph[anc][dataset][key].get('model')
                    if edge:
                        edge_data = edge
                        break
                results.append({
                    'node_id': anc,
                    'path': getattr(anc_node, 'path', None) if anc_node else None,
                    'line_range': getattr(edge_data, 'line_range', None) if edge_data else getattr(anc_node, 'line_range', None) if anc_node else None,
                    'source_file': getattr(edge_data, 'source_file', None) if edge_data else getattr(anc_node, 'path', None) if anc_node else None,
                    'analysis_method': method
                })
            return {'dataset': dataset, 'upstream': results, 'analysis_method': method}
        else:
            descendants = list(nx.descendants(self.kg.graph, dataset))
            for desc in descendants:
                desc_node = self.kg.get_node(desc)
                edge_data = None
                for key in self.kg.graph[dataset][desc]:
                    edge = self.kg.graph[dataset][desc][key].get('model')
                    if edge:
                        edge_data = edge
                        break
                results.append({
                    'node_id': desc,
                    'path': getattr(desc_node, 'path', None) if desc_node else None,
                    'line_range': getattr(edge_data, 'line_range', None) if edge_data else getattr(desc_node, 'line_range', None) if desc_node else None,
                    'source_file': getattr(edge_data, 'source_file', None) if edge_data else getattr(desc_node, 'path', None) if desc_node else None,
                    'analysis_method': method
                })
            return {'dataset': dataset, 'downstream': results, 'analysis_method': method}

    def blast_radius(self, module_path: str) -> Dict[str, Any]:
        """Return all nodes that would be affected if this module changes, with evidence citations."""
        affected = self.kg.blast_radius(module_path)
        method = 'static (graph traversal)'
        results = []
        for node_id in affected:
            node = self.kg.get_node(node_id)
            results.append({
                'node_id': node_id,
                'path': getattr(node, 'path', None) if node else None,
                'line_range': getattr(node, 'line_range', None) if node else None,
                'analysis_method': method
            })
        return {
            'module': module_path,
            'affected_nodes': results,
            'analysis_method': method
        }

    def explain_module(self, path: str) -> Dict[str, Any]:
        """Return a generative explanation of a module, citing source, line range, and method."""
        node = self.kg.get_node(path)
        if not node or not isinstance(node, ModuleNode):
            return {'error': f'Module {path} not found'}
        if self.semanticist:
            explanation = self.semanticist._generate_purpose_statement(self._read_file(node.path), node.purpose_statement or "")
            method = 'LLM (purpose_statement)'
        else:
            explanation = node.purpose_statement or "No purpose statement available."
            method = 'LLM (cached purpose_statement)'
        return {
            'module': path,
            'explanation': explanation,
            'line_range': getattr(node, 'line_range', None) if hasattr(node, 'line_range') else None,
            'analysis_method': method
        }

    def _read_file(self, path: str) -> str:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.warning(f"Could not read {path}: {e}")
            return ""
