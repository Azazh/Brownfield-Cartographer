import os
import sys
import logging
from src.vectorstore.embedding import EmbeddingModel
from src.vectorstore.simple_numpy import SimpleNumpyVectorStore

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def read_codebase_md(md_path):
    if not os.path.exists(md_path):
        raise FileNotFoundError(f"CODEBASE.md not found at {md_path}")
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()
    # Split into sections (e.g., by headings)
    sections = []
    current = []
    for line in content.splitlines():
        if line.strip().startswith('#') and current:
            sections.append('\n'.join(current).strip())
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append('\n'.join(current).strip())
    # Filter out empty sections
    return [s for s in sections if s.strip()]

def main(md_path, index_path):
    logger.info(f"Reading CODEBASE.md from {md_path}")
    sections = read_codebase_md(md_path)
    logger.info(f"Found {len(sections)} sections to embed.")
    embedder = EmbeddingModel()
    embeddings = embedder.embed(sections)
    logger.info(f"Embeddings shape: {[e.shape for e in embeddings]}")
    # Build vector store
    store = SimpleNumpyVectorStore()
    for i, (section, emb) in enumerate(zip(sections, embeddings)):
        doc_id = f"section_{i}"
        store.add(doc_id, emb, {'section': section, 'section_id': i})
    store.persist(index_path)
    logger.info(f"Vector store persisted to {index_path}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python -m src.vectorstore.embed_codebase <CODEBASE.md path> <index output path>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])