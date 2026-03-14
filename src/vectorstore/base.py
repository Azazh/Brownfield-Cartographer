from typing import List, Dict, Any
import numpy as np

class VectorStoreBase:
    """
    Abstract base class for a vector store.
    """
    def add(self, doc_id: str, embedding: np.ndarray, metadata: Dict[str, Any]):
        raise NotImplementedError

    def search(self, query_embedding: np.ndarray, top_k: int = 5) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def persist(self, path: str):
        raise NotImplementedError

    def load(self, path: str):
        raise NotImplementedError
