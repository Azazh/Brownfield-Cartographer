# The Brownfield Cartographer

A multi-agent codebase intelligence system for rapid FDE onboarding in production data engineering environments.

## Project Structure

- `src/` - Source code
  - `cli.py` - Command-line entry point
  - `orchestrator.py` - Pipeline orchestrator
  - `agents/` - Agent implementations
  - `analyzers/` - Static and semantic analyzers
  - `graph/` - Knowledge graph logic
  - `models/` - Pydantic schemas
- `.cartography/` - Generated artifacts (graphs, reports)
- `tests/` - Test suite
- `docs/` - Documentation

## Getting Started

1. Install dependencies: `poetry install`
2. Run analysis: `python src/cli.py --help`

## License
MIT
