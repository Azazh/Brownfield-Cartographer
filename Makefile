


# Run full pipeline: clone and analyze (generates CODEBASE.md)
pipeline:
	@echo "[Pipeline] Running full analysis..."
	. .venv/bin/activate && python -m src.cli --repo $(REPO) --output $(OUTPUT)

# To run semantic indexing after CODEBASE.md is generated, run:
# make semantic-index

# Usage:
# make pipeline REPO=git@github.com:Azazh/project-chimera.git
# Semantic indexing of CODEBASE.md
semantic-index:
	@echo "[Semantic Index] Embedding and indexing .cartography/CODEBASE.md ..."
	. .venv/bin/activate && python -m src.vectorstore.embed_codebase .cartography/CODEBASE.md .cartography/codebase_index.npz
PYTHON = .venv/bin/python

.PHONY: run test



run:
	.venv/bin/python -m src.cli --repo $(REPO) --output $(OUTPUT)

test:
	$(PYTHON) -m unittest discover -s tests
