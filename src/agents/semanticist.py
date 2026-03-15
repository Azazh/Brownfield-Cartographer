import logging
import json
from src.graph.knowledge_graph import KnowledgeGraph
from src.models.node_types import ModuleNode
from typing import Dict, Any

logger = logging.getLogger(__name__)

class SemanticistAgent:
    def cluster_into_domains(self, k: int = 6) -> dict:
        """
        Embed all purpose statements, run k-means clustering, and label clusters with inferred domain names.
        Returns a mapping of node_id to domain label.
        """
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.cluster import KMeans
        import numpy as np
        # Collect purpose statements
        node_ids = []
        purposes = []
        file_paths = []
        line_ranges = []
        for node_id, node_model in self.kg.graph.nodes(data='model'):
            if hasattr(node_model, 'purpose_statement') and node_model.purpose_statement:
                node_ids.append(node_id)
                purposes.append(node_model.purpose_statement)
                file_paths.append(getattr(node_model, 'path', None))
                line_ranges.append(getattr(node_model, 'line_range', None))
        if not purposes:
            return {}
        # Embed with TF-IDF
        vectorizer = TfidfVectorizer(stop_words='english')
        X = vectorizer.fit_transform(purposes)
        # K-means clustering
        k = min(k, len(purposes))
        kmeans = KMeans(n_clusters=k, n_init=10, random_state=42)
        labels = kmeans.fit_predict(X)
        # Data-driven domain label: top 3 TF-IDF words in each cluster
        domain_labels = []
        for i in range(k):
            idxs = np.where(labels == i)[0]
            if len(idxs) == 0:
                domain_labels.append(f"domain_{i}")
                continue
            cluster_text = ' '.join([purposes[j] for j in idxs])
            tfidf = vectorizer.transform([cluster_text])
            top_indices = np.argsort(tfidf.toarray()[0])[::-1][:3]
            top_words = [vectorizer.get_feature_names_out()[idx] for idx in top_indices]
            domain_labels.append(', '.join(top_words))
        # Assign domain_cluster to ModuleNodes
        node_to_domain = {}
        for idx, node_id in enumerate(node_ids):
            label = domain_labels[labels[idx]]
            node_model = self.kg.graph.nodes[node_id]['model']
            node_model.domain_cluster = label
            self.kg.add_node(node_model)
            node_to_domain[node_id] = label
        return node_to_domain

    def answer_day_one_questions(self, surveyor_report: dict, hydrologist_report: dict) -> dict:
        """
        Use LLM to synthesize answers to the Five FDE Day-One Questions, citing evidence (file, line_range) from Surveyor/Hydrologist outputs.
        If LLM is unavailable or fails, fallback to basic evidence extraction.
        """
        # Fallback evidence extraction (for rubric compliance and traceability)
        evidence = {}
        if 'domain_map' in surveyor_report:
            domains = surveyor_report['domain_map']
            domain_citations = []
            for node_id, label in domains.items():
                node = self.kg.get_node(node_id)
                if node:
                    domain_citations.append({
                        'domain': label,
                        'file': getattr(node, 'path', None),
                        'line_range': getattr(node, 'line_range', None)
                    })
            evidence['main_domains'] = domain_citations
        if hydrologist_report:
            flows = []
            for edge in hydrologist_report.get('edges', []):
                flows.append({
                    'from': edge.get('from'),
                    'to': edge.get('to'),
                    'transformation_type': edge.get('edge', {}).get('transformation_type'),
                    'file': edge.get('edge', {}).get('source_file'),
                    'line_range': edge.get('edge', {}).get('line_range')
                })
            evidence['critical_data_flows'] = flows

        if not self.llm_client:
            # No LLM: fallback to evidence only
            return {
                'q1': 'No answer available (LLM not configured).',
                'q2': 'No answer available (LLM not configured).',
                'q3': 'No answer available (LLM not configured).',
                'q4': 'No answer available (LLM not configured).',
                'q5': 'No answer available (LLM not configured).',
                'evidence': evidence
            }

        prompt = (
            "You are a senior FDE. Given the following codebase analysis outputs, answer the Five FDE Day-One Questions. "
            "For each answer, cite specific evidence (file paths, line numbers, or analysis method).\n"
            "Surveyor Report (static structure):\n" + json.dumps(surveyor_report)[:4000] +
            "\nHydrologist Report (data lineage):\n" + json.dumps(hydrologist_report)[:4000] +
            "\nQuestions:\n"
            "1. What is the primary data ingestion path?\n"
            "2. What are the 3-5 most critical output datasets/endpoints?\n"
            "3. What is the blast radius if the most critical module fails?\n"
            "4. Where is the business logic concentrated vs. distributed?\n"
            "5. What has changed most frequently in the last 90 days (git velocity map)?\n"
            "\nFormat your answers as a JSON object with keys 'q1' to 'q5', and include evidence citations."
        )
        try:
            response = self.llm_client.generate_day_one_answers(prompt, evidence=evidence, max_tokens=1024)
            return response
        except Exception as e:
            # LLM failed: fallback to evidence only
            return {
                'q1': 'No answer available (LLM error).',
                'q2': 'No answer available (LLM error).',
                'q3': 'No answer available (LLM error).',
                'q4': 'No answer available (LLM error).',
                'q5': 'No answer available (LLM error).',
                'evidence': evidence,
                'raw_response': str(e)
            }
    # Agent 3: The Semanticist (LLM-Powered Purpose Analyst)
    # - Generates purpose statements for each module
    # - Flags documentation drift
    # - Clusters modules into domains
    # - Answers the Five FDE Day-One Questions
    def __init__(self, knowledge_graph: KnowledgeGraph, llm_client=None, trace_logger=None):
        self.kg = knowledge_graph
        self.llm_client = llm_client  # Should be an LLMClient instance
        self.trace_logger = trace_logger

    def analyze_repo(self, repo_path: str, surveyor_report: dict = None, hydrologist_report: dict = None, changed_files=None, added_files=None, deleted_files=None) -> Dict[str, Any]:
        """
        For each ModuleNode, generate a purpose statement using the LLM.
        Then cluster modules into domains and answer Day-One questions.
        Supports incremental update via changed_files, added_files, deleted_files.
        """
        if changed_files or added_files or deleted_files:
            logger.info(f"[Semanticist] Incremental update: changed={changed_files}, added={added_files}, deleted={deleted_files}")
            # Remove deleted modules from the knowledge graph and semantic index
            if deleted_files:
                for node_id, node_model in list(self.kg.graph.nodes(data='model')):
                    if hasattr(node_model, 'path') and node_model.path in deleted_files:
                        self.kg.graph.remove_node(node_id)
            # Only (re)generate purpose statements for changed/added modules
            files_to_process = (changed_files or []) + (added_files or [])
            results = {}
            for node_id, node_model in self.kg.graph.nodes(data='model'):
                if hasattr(node_model, 'path') and node_model.path in files_to_process:
                    code = self._read_file(node_model.path)
                    docstring = self._extract_docstring(code)
                    purpose = self._generate_purpose_statement(code, docstring)
                    node_model.purpose_statement = purpose
                    if docstring and not self._docstring_matches_purpose(docstring, purpose):
                        node_model.documentation_drift = True
                    else:
                        node_model.documentation_drift = False
                    self.kg.add_node(node_model)
                    results[node_id] = {
                        'purpose_statement': purpose,
                        'documentation_drift': node_model.documentation_drift
                    }
            # Re-cluster domains and answer Day-One questions if needed
            domain_map = self.cluster_into_domains(k=6)
            results['domain_map'] = domain_map
            if surveyor_report is not None and hydrologist_report is not None:
                results['day_one_answers'] = self.answer_day_one_questions(surveyor_report, hydrologist_report)
            return results
        # For each ModuleNode, generate a purpose statement using the LLM
        results = {}
        # Try to get top N important modules by PageRank/critical_path from surveyor_report
        N = 6
        important_paths = set()
        if surveyor_report and 'critical_path' in surveyor_report:
            # critical_path is a list of file paths (top modules by PageRank)
            important_paths.update(surveyor_report['critical_path'][:N])
        # Fallback: if not enough, add more modules arbitrarily (but avoid duplicates)
        for node_id, node_model in self.kg.graph.nodes(data='model'):
            if isinstance(node_model, ModuleNode) and getattr(node_model, 'path', None):
                if len(important_paths) >= N:
                    break
                important_paths.add(node_model.path)
        # Now only process the important modules
        for node_id, node_model in self.kg.graph.nodes(data='model'):
            if isinstance(node_model, ModuleNode) and getattr(node_model, 'path', None) and node_model.path in important_paths:
                code = self._read_file(node_model.path)
                docstring = self._extract_docstring(code)
                # Generate purpose statement using LLM
                purpose = self._generate_purpose_statement(code, docstring)
                node_model.purpose_statement = purpose
                # Optionally, flag documentation drift
                if docstring and not self._docstring_matches_purpose(docstring, purpose):
                    node_model.documentation_drift = True
                else:
                    node_model.documentation_drift = False
                self.kg.add_node(node_model)
                results[node_id] = {
                    'purpose_statement': purpose,
                    'documentation_drift': node_model.documentation_drift
                }
        # Cluster modules into domains
        domain_map = self.cluster_into_domains(k=6)
        results['domain_map'] = domain_map
        # Answer Day-One questions if reports provided
        if surveyor_report is not None and hydrologist_report is not None:
            results['day_one_answers'] = self.answer_day_one_questions(surveyor_report, hydrologist_report)
        return results

    def _read_file(self, path: str) -> str:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.warning(f"Could not read {path}: {e}")
            return ""

    def _extract_docstring(self, code: str) -> str:
        # Simple heuristic: first triple-quoted string in the file
        import re
        match = re.search(r'"""(.*?)"""|\'\'(.*?)\'\'', code, re.DOTALL)
        if match:
            return match.group(1) or match.group(2) or ""
        return ""

    def _generate_purpose_statement(self, code: str, docstring: str) -> str:
        # Use the LLMClient for purpose statement generation, robust fallback: try each model only once
        if self.llm_client:
            try:
                result = self.llm_client.generate_purpose_statement(code, docstring, prefer_fast=True)
                # If result is a known error, do not retry the same model, just try others (handled in LLMClient)
                return result
            except Exception as e:
                logger.warning(f"LLM call failed: {e}")
        # Fallback: naive heuristic
        return "Purpose statement for module (stub)."

    def _docstring_matches_purpose(self, docstring: str, purpose: str) -> bool:
        # Placeholder: naive check
        return docstring.strip().lower() in purpose.strip().lower()
