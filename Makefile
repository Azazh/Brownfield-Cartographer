PYTHON = .venv/bin/python

.PHONY: run test

run:
	$(PYTHON) -m src.cli --repo $(REPO) --output $(OUTPUT)

test:
	$(PYTHON) -m unittest discover -s tests
