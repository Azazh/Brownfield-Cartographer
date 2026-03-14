# The Brownfield Cartographer

A multi‑agent codebase intelligence system for data engineering and data science projects.  
Built for the **TRP1 Week 4 Challenge** – a forward‑deployed engineering tool to rapidly map and understand unfamiliar production codebases.

## Features (Phase 2 – Interim)

**Surveyor Agent** – static structure analysis using tree‑sitter:
   - Extracts Python imports, public functions, classes, and inheritance.
   - Builds a module import graph (NetworkX) and identifies high‑velocity files via git log.
   - Detects circular dependencies and computes PageRank hubs.
**Hydrologist Agent** – data lineage analysis:
   - Python: extracts pandas read/write, Spark operations, SQLAlchemy `execute()` calls.
   - SQL: parses `.sql` files with `sqlglot` to find table dependencies (now supports dbt Jinja via preprocessor).
   - YAML: extracts dbt `ref()` and `source()` references from `schema.yml` and model files.
   - Merges all findings into a **DataLineageGraph** (NetworkX DiGraph) and provides `blast_radius()`, `find_sources()`, `find_sinks()`.
**Semanticist Agent** – LLM-powered semantic analysis:
   - Generates purpose statements for modules and datasets using LLMs.
   - Produces semantic index for CODEBASE.md and supports Navigator queries.
**Archivist Agent** – artifact/report generation:
   - Produces CODEBASE.md and onboarding_brief.md for FDE onboarding.
**Navigator Agent** – interactive codebase Q&A:
   - Provides four rubric-compliant tools: `find_implementation`, `trace_lineage`, `blast_radius`, `explain_module`.
   - All answers cite source files, line ranges, and analysis method.
Outputs are saved in `.cartography/` as JSON and Markdown files (see below).

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

To run the full analysis pipeline on any local or remote repository, use the Makefile for convenience:

```bash
# Full analysis (default: auto mode)
make run REPO=/path/to/target/repo OUTPUT=.cartography

# Force full analysis
make run REPO=/path/to/target/repo OUTPUT=.cartography RUN_MODE=full

# Force incremental analysis (if possible)
make run REPO=/path/to/target/repo OUTPUT=.cartography RUN_MODE=incremental
```

You can also run the CLI directly for advanced options:

```bash
.venv/bin/python -m src.cli --repo /path/to/target/repo --output .cartography --run-mode full
```

#### Arguments
- `REPO`: Path to local repo or GitHub URL (required)
- `OUTPUT`: Output directory for artifacts (default: .cartography)
- `RUN_MODE`: Run mode for analysis. One of:
   - `auto` (default): Use incremental if possible, else full
   - `full`: Force full analysis of all files
   - `incremental`: Force incremental analysis (if possible)

#### Outputs
Artifacts are saved in `.cartography/`:
- `module_graph.json`: Module import graph (static structure)

### Query Command (Navigator Agent)

To interactively query the codebase using the Navigator agent over existing `.cartography` artifacts, use the Makefile and override arguments as needed:

```bash
# Example: Find where a business concept is implemented
make run REPO=../jaffle-shop-classic OUTPUT=.cartography MODE=query QUERY_TOOL=find_implementation QUERY_ARG="customer"

# Example: Trace lineage for a dataset
make run REPO=../jaffle-shop-classic OUTPUT=.cartography MODE=query QUERY_TOOL=trace_lineage QUERY_ARG="stg_customers upstream"

# Example: Get blast radius for a module
make run REPO=../jaffle-shop-classic OUTPUT=.cartography MODE=query QUERY_TOOL=blast_radius QUERY_ARG="src/models/customers.sql"

# Example: Explain a module
make run REPO=../jaffle-shop-classic OUTPUT=.cartography MODE=query QUERY_TOOL=explain_module QUERY_ARG="src/models/customers.sql"
```

Supported query tools:
- `find_implementation <concept>`
- `trace_lineage <dataset> [direction]`
- `blast_radius <module_path>`
- `explain_module <path>`

### Incremental vs Full Analysis

By default, the pipeline will run in `auto` mode, using incremental analysis if there are new git commits since the last run. You can explicitly control this with the `RUN_MODE` Makefile variable:

- Force full analysis:
   ```bash
   make run REPO=../jaffle-shop-classic OUTPUT=.cartography RUN_MODE=full
   ```
- Force incremental analysis (if possible):
   ```bash
   make run REPO=../jaffle-shop-classic OUTPUT=.cartography RUN_MODE=incremental
   ```

If incremental is not possible (e.g., first run or no new commits), the pipeline will fall back to full analysis.
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

- Only Python grammar is built for tree-sitter; SQL and YAML are handled by other tools (`sqlglot`, `pyyaml`).
- Git velocity requires the target directory to be a git repository.
- LLM-based semantic analysis requires internet access and valid API keys for supported LLM providers.

## Future Work (Final Submission)

The following are now implemented and required for the final deliverable:
- Jinja pre‑processor for full dbt SQL parsing.
- Modular SQL and YAML parsing (tree-sitter, sqlglot, pyyaml).
- Semanticist (LLM‑based purpose statements) and Archivist (CODEBASE.md, onboarding brief).
- Navigator agent (LangGraph‑based query interface) with rubric-compliant evidence reporting.
- Incremental/full run support and robust artifact saving.

**Final Deliverable Protocols:**
- Submit `.cartography/module_graph.json` and `.cartography/lineage_graph.json` for interim review.
- For final submission, include all generated artifacts in `.cartography/` (including CODEBASE.md, onboarding_brief.md, semanticist and surveyor reports).
- Ensure README and Makefile are up to date and all commands work as documented.
- Provide at least one example run on a real-world codebase (e.g., dbt jaffle-shop-classic) and verify outputs.

## License

MIT 

---

For questions or issues, please open an issue on GitHub or contact the author.