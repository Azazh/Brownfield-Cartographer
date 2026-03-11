PYTHON = .venv/bin/python

.PHONY: run test

run:
	$(PYTHON) -m src.cli --repo ../ol-data-platform

test:
	$(PYTHON) -m unittest discover -s tests
