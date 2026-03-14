import numpy as np
from typing import List, Dict, Any
from .base import VectorStoreBase
import pickle
import os

class SimpleNumpyVectorStore(VectorStoreBase):
    """
    In-memory vector store using numpy arrays and cosine similarity.
    Suitable for small to medium codebases.
    """
    def __init__(self):
        self.embeddings = []  # List[np.ndarray]
        self.doc_ids = []     # List[str]
        self.metadata = []    # List[Dict[str, Any]]

    def add(self, doc_id: str, embedding: np.ndarray, metadata: Dict[str, Any]):
        self.doc_ids.append(doc_id)
        self.embeddings.append(embedding)
        self.metadata.append(metadata)

    def search(self, query_embedding: np.ndarray, top_k: int = 5) -> List[Dict[str, Any]]:
        if not self.embeddings:
            return []
        embs = np.stack(self.embeddings)
        query = query_embedding / (np.linalg.norm(query_embedding) + 1e-8)
        embs_norm = embs / (np.linalg.norm(embs, axis=1, keepdims=True) + 1e-8)
        scores = embs_norm @ query
        top_idx = np.argsort(scores)[::-1][:top_k]
        results = []
        for idx in top_idx:
            results.append({
                'node_id': self.doc_ids[idx],
                'score': float(scores[idx]),
                'metadata': self.metadata[idx]
            })
        return results

    def persist(self, path: str):
        with open(path, 'wb') as f:
            pickle.dump({'doc_ids': self.doc_ids, 'embeddings': self.embeddings, 'metadata': self.metadata}, f)

    def load(self, path: str):
        if not os.path.exists(path):
            raise FileNotFoundError(f"Vector store file not found: {path}")
        with open(path, 'rb') as f:
            data = pickle.load(f)
            self.doc_ids = data['doc_ids']
            self.embeddings = data['embeddings']
            self.metadata = data['metadata']
