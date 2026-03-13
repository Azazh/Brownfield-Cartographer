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
        for node_id, node_model in self.kg.graph.nodes(data='model'):
            if hasattr(node_model, 'purpose_statement') and node_model.purpose_statement:
                node_ids.append(node_id)
                purposes.append(node_model.purpose_statement)
        if not purposes:
            return {}
        # Embed with TF-IDF
        vectorizer = TfidfVectorizer(stop_words='english')
        X = vectorizer.fit_transform(purposes)
        # K-means clustering
        k = min(k, len(purposes))
        kmeans = KMeans(n_clusters=k, n_init=10, random_state=42)
        labels = kmeans.fit_predict(X)
        # Simple domain label: top TF-IDF word in each cluster
        domain_labels = []
        for i in range(k):
            idxs = np.where(labels == i)[0]
            if len(idxs) == 0:
                domain_labels.append(f"domain_{i}")
                continue
            cluster_text = ' '.join([purposes[j] for j in idxs])
            tfidf = vectorizer.transform([cluster_text])
            top_word = vectorizer.get_feature_names_out()[np.argmax(tfidf.toarray())]
            domain_labels.append(top_word)
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
        Use LLM to synthesize answers to the Five FDE Day-One Questions, citing evidence.
        """
        if not self.llm_client:
            return {"error": "No LLM client configured"}
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
        response = self.llm_client.call_gemini(prompt, max_tokens=1024)
        try:
            return json.loads(response)
        except Exception:
            return {"raw_response": response}
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
        for node_id, node_model in self.kg.graph.nodes(data='model'):
            if isinstance(node_model, ModuleNode):
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
