# The Brownfield Cartographer

A multi‑agent codebase intelligence system for data engineering and data science projects.  
Built for the **TRP1 Week 4 Challenge** – a forward‑deployed engineering tool to rapidly map and understand unfamiliar production codebases.

## Features (Phase 2 – Interim)

- **Surveyor Agent** – static structure analysis using tree‑sitter:
  - Extracts Python imports, public functions, classes, and inheritance.
  - Builds a module import graph (NetworkX) and identifies high‑velocity files via git log.
  - Detects circular dependencies and computes PageRank hubs.
- **Hydrologist Agent** – data lineage analysis:
  - Python: extracts pandas read/write, Spark operations, SQLAlchemy `execute()` calls.
  - SQL: parses `.sql` files with `sqlglot` to find table dependencies (partial – dbt Jinja not yet supported).
  - YAML: extracts dbt `ref()` and `source()` references from `schema.yml` and model files.
  - Merges all findings into a **DataLineageGraph** (NetworkX DiGraph) and provides `blast_radius()`, `find_sources()`, `find_sinks()`.
- Outputs are saved in `.cartography/` as JSON files (`analysis_results_*.json`, `lineage_graph.json`).

## Project Structure

```
.
├── .cartography/            # Generated artifacts (surveyor results, lineage graph)
├── src/
│   ├── agents/
│   │   ├── dynamic_surveyor.py      # Surveyor agent (module graph, git velocity)
│   │   └── hydrologist.py           # Hydrologist agent (data lineage)
│   ├── analyzers/
│   │   ├── tree_sitter_analyzer.py  # Python AST parsing
│   │   ├── sql_import_extractor.py  # SQL dependency extraction (sqlglot)
│   │   ├── sql_lineage.py           # (optional) separate sqlglot module
│   │   └── dag_config_parser.py     # YAML/dbt parsing (used in hydrologist)
│   ├── models/
│   │   └── module_node.py           # Pydantic schema for modules
│   ├── graph/
│   │   └── module_import_graph.py   # NetworkX wrapper for import graph
│   └── utils/
│       └── language_loader.py       # Loads Python grammar from shared library
├── vendor/                  # tree‑sitter grammar sources (Python only)
├── build/                   # Compiled shared library (my-languages.so)
├── build_minimal.py         # Build script for shared library
├── pyproject.toml           # Project dependencies (uv)
├── Makefile                 # Convenience commands (make run)
└── README.md
```

## Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (fast Python package installer)
- Git

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/brownfield-cartographer.git
   cd brownfield-cartographer
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   uv venv
   source .venv/bin/activate
   uv pip install -e .              # if you have a pyproject.toml with all deps
   # or install manually:
   uv pip install tree-sitter==0.21.3 pyyaml networkx sqlglot
   ```

3. Build the shared library (contains only Python grammar):
   ```bash
   # Ensure vendor/tree-sitter-python exists (clone if missing)
   cd vendor
   git clone --depth 1 --branch v0.20.0 https://github.com/tree-sitter/tree-sitter-python.git
   cd ..
   python build_minimal.py          # creates build/my-languages.so
   ```

## Usage


### Analyze Command

To run the full analysis pipeline on any local or remote repository:

```bash
make run REPO=/path/to/target/repo OUTPUT=.cartography
# or directly
.venv/bin/python -m src.cli --repo /path/to/target/repo --output .cartography
```

#### Arguments
- `--repo`: Path to local repo or GitHub URL (required)
- `--output`: Output directory for artifacts (default: .cartography)
- `--sql-dialect`: SQL dialect for parsing (default: duckdb)

#### Outputs
Artifacts are saved in `.cartography/`:
- `module_graph.json`: Module import graph (static structure)
- `lineage_graph.json`: DataLineageGraph (dataset/transformation nodes and lineage edges)
- `knowledge_graph_<timestamp>.json`: Full knowledge graph (all nodes/edges)
- `surveyor_report_<timestamp>.json`: Surveyor static structure results

You must submit `.cartography/module_graph.json` and `.cartography/lineage_graph.json` for the interim deliverable.

#### Typical Workflow
1. Clone this repo and install dependencies (see Installation).
2. Build the tree-sitter shared library with all grammars (see Installation).
3. Run the analysis as above.
4. Inspect `.cartography/` for outputs. Use `module_graph.json` and `lineage_graph.json` for interim submission.

## Example

```bash
git clone https://github.com/dbt-labs/jaffle-shop-classic.git ../jaffle-shop-classic
make run --repo ../jaffle-shop-classic
```

After completion, inspect the outputs:

```bash
head -n 30 .cartography/lineage_graph.json
```

## Known Limitations (Interim)

- SQL lineage with `sqlglot` fails on dbt Jinja templating (`{{ ref(...) }}`, `{% ... %}`). Table names are not extracted from such files.
- Only Python grammar is built; SQL and YAML are handled by other tools (`sqlglot`, `pyyaml`). This meets the "partial lineage" requirement.
- Git velocity requires the target directory to be a git repository.

## Future Work (Final Submission)

- Add Jinja pre‑processor for full dbt SQL parsing.
- Build SQL and YAML grammars into the shared library.
- Implement Semanticist (LLM‑based purpose statements) and Archivist (CODEBASE.md, onboarding brief).
- Add Navigator agent (LangGraph‑based query interface).

## License

MIT 

