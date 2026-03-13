import os
import json
import datetime
import logging
from src.agents.dynamic_surveyor import DynamicSurveyor
from src.agents.hydrologist import HydrologistAgent
from src.agents.semanticist import SemanticistAgent
from src.graph.knowledge_graph import KnowledgeGraph

# Load .env if present (redundant if already loaded in CLI, but safe for direct use)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)

def run_analysis(repo_path: str, output_dir: str = '.cartography', sql_dialect: str = 'duckdb'):
    """
    Run the full analysis pipeline.
    - repo_path: local path to the repository
    - output_dir: directory where artifacts will be saved
    - sql_dialect: SQL dialect to use in lineage extraction
    """
    os.makedirs(output_dir, exist_ok=True)

    kg = KnowledgeGraph()
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    from src.agents.trace_logger import TraceLogger
    trace_log_path = os.path.join(output_dir, 'cartography_trace.jsonl')
    trace_logger = TraceLogger(trace_log_path)

    # --- Incremental update logic ---
    last_commit_path = os.path.join(output_dir, 'last_commit.txt')
    last_commit = None
    changed_files, added_files, deleted_files = [], [], []
    current_commit = None
    try:
        import subprocess
        # Get current HEAD commit
        current_commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo_path).decode().strip()
        if os.path.exists(last_commit_path):
            with open(last_commit_path, 'r') as f:
                last_commit = f.read().strip()
            if last_commit:
                # Get changed/added/deleted files since last commit
                diff_cmd = ['git', 'diff', '--name-status', f'{last_commit}..{current_commit}']
                diff_out = subprocess.check_output(diff_cmd, cwd=repo_path).decode().splitlines()
                for line in diff_out:
                    status, path = line.split('\t', 1)
                    if status == 'A':
                        added_files.append(path)
                    elif status == 'M':
                        changed_files.append(path)
                    elif status == 'D':
                        deleted_files.append(path)
        else:
            # No last commit, treat as full run
            changed_files = added_files = deleted_files = []
    except Exception as e:
        logger.warning(f"Could not determine git commit or diff: {e}. Running full analysis.")
        changed_files = added_files = deleted_files = []

    # If no last commit or no changes, do full run
    incremental = bool(last_commit and (changed_files or added_files or deleted_files))
    if not incremental:
        logger.info("No previous commit or no changes detected. Running full analysis.")
        changed_files = added_files = deleted_files = []

    # --- Phase 1: Surveyor ---
    logger.info("=" * 50)
    logger.info("Phase 1: Surveyor – static structure analysis")
    logger.info("=" * 50)
    surveyor = DynamicSurveyor(kg, trace_logger=trace_logger)
    report = surveyor.analyze_repo(repo_path, changed_files=changed_files, added_files=added_files, deleted_files=deleted_files)
    trace_logger.log(agent="Surveyor", action="analyze_repo", input_data={"repo_path": repo_path, "changed": changed_files, "added": added_files, "deleted": deleted_files}, output_data="survey_report", evidence=None)

    report_path = os.path.join(output_dir, f'surveyor_report_{timestamp}.json')
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2)
    logger.info(f"Surveyor report saved to {report_path}")

    # Save module import graph (only module nodes and import edges)
    module_nodes = []
    import_edges = []
    for n, data in kg.graph.nodes(data=True):
        model = data.get('model')
        if model and type(model).__name__ == 'ModuleNode':
            module_nodes.append(model.dict())
    for u, v, k, data in kg.graph.edges(keys=True, data=True):
        model = data.get('model')
        if model and type(model).__name__ == 'ImportEdge':
            import_edges.append(model.dict())
    module_graph = {'nodes': module_nodes, 'edges': import_edges}
    module_graph_path = os.path.join(output_dir, 'module_graph.json')
    with open(module_graph_path, 'w', encoding='utf-8') as f:
        json.dump(module_graph, f, indent=2)
    logger.info(f"Module graph saved to {module_graph_path}")

    # --- Phase 2: Hydrologist ---
    logger.info("=" * 50)
    logger.info("Phase 2: Hydrologist – data lineage analysis")
    logger.info("=" * 50)
    hydrologist = HydrologistAgent(kg, sql_dialect=sql_dialect, trace_logger=trace_logger)
    hydrologist.analyze_repo(repo_path, changed_files=changed_files, added_files=added_files, deleted_files=deleted_files)
    trace_logger.log(agent="Hydrologist", action="analyze_repo", input_data={"repo_path": repo_path, "changed": changed_files, "added": added_files, "deleted": deleted_files}, output_data="lineage_graph", evidence=None)

    # Save full knowledge graph (all nodes/edges)
    kg_path = os.path.join(output_dir, f'knowledge_graph_{timestamp}.json')
    with open(kg_path, 'w', encoding='utf-8') as f:
        json.dump(kg.to_json_serializable(), f, indent=2)
    logger.info(f"Knowledge graph saved to {kg_path}")

    # Save DataLineageGraph (only dataset/transformation nodes and lineage edges)
    lineage_nodes = []
    lineage_edges = []
    for n, data in kg.graph.nodes(data=True):
        model = data.get('model')
        if model and type(model).__name__ in ('DatasetNode', 'TransformationNode'):
            lineage_nodes.append(model.dict())
    for u, v, k, data in kg.graph.edges(keys=True, data=True):
        model = data.get('model')
        if model and type(model).__name__ in ('ProducesEdge', 'ConsumesEdge'):
            lineage_edges.append(model.dict())
    lineage_graph = {'nodes': lineage_nodes, 'edges': lineage_edges}
    lineage_path = os.path.join(output_dir, 'lineage_graph.json')
    with open(lineage_path, 'w', encoding='utf-8') as f:
        json.dump(lineage_graph, f, indent=2)
    logger.info(f"Lineage graph saved to {lineage_path}")

    # --- Phase 3: Semanticist ---
    logger.info("=" * 50)
    logger.info("Phase 3: Semanticist – semantic analysis (LLM-powered)")
    logger.info("=" * 50)
    from src.llm import LLMClient
    llm_client = LLMClient()
    semanticist = SemanticistAgent(kg, llm_client=llm_client, trace_logger=trace_logger)
    semantic_report = semanticist.analyze_repo(repo_path, surveyor_report=report, hydrologist_report={}, changed_files=changed_files, added_files=added_files, deleted_files=deleted_files)
    trace_logger.log(agent="Semanticist", action="analyze_repo", input_data={"repo_path": repo_path, "changed": changed_files, "added": added_files, "deleted": deleted_files}, output_data="semantic_report", evidence=None)
    semantic_report_path = os.path.join(output_dir, f'semanticist_report_{timestamp}.json')
    with open(semantic_report_path, 'w', encoding='utf-8') as f:
        json.dump(semantic_report, f, indent=2)
    logger.info(f"Semanticist report saved to {semantic_report_path}")

    # --- Phase 4: Archivist ---
    logger.info("=" * 50)
    logger.info("Phase 4: Archivist – generating CODEBASE.md")
    logger.info("=" * 50)
    from src.agents.archivist import ArchivistAgent
    hydrologist_report = {}
    hydrologist_report_path = os.path.join(output_dir, f'hydrologist_report_{timestamp}.json')
    if os.path.exists(hydrologist_report_path):
        with open(hydrologist_report_path, 'r', encoding='utf-8') as f:
            hydrologist_report = json.load(f)
    archivist = ArchivistAgent(kg, report, hydrologist_report, semantic_report, trace_logger=trace_logger)
    codebase_md_path = os.path.join(output_dir, 'CODEBASE.md')
    archivist.generate_CODEBASE_md(codebase_md_path, changed_files=changed_files, added_files=added_files, deleted_files=deleted_files)
    trace_logger.log(agent="Archivist", action="generate_CODEBASE_md", input_data={"changed": changed_files, "added": added_files, "deleted": deleted_files}, output_data=codebase_md_path, evidence=None)
    logger.info(f"CODEBASE.md generated at {codebase_md_path}")
    onboarding_brief_path = os.path.join(output_dir, 'onboarding_brief.md')
    archivist.generate_onboarding_brief_md(onboarding_brief_path, changed_files=changed_files, added_files=added_files, deleted_files=deleted_files)
    trace_logger.log(agent="Archivist", action="generate_onboarding_brief_md", input_data={"changed": changed_files, "added": added_files, "deleted": deleted_files}, output_data=onboarding_brief_path, evidence=None)
    logger.info(f"onboarding_brief.md generated at {onboarding_brief_path}")

    # --- Update last_commit.txt ---
    if current_commit:
        with open(last_commit_path, 'w') as f:
            f.write(current_commit + '\n')
    logger.info("=" * 50)
    logger.info("Analysis complete. Artifacts are in: %s", output_dir)
    logger.info("=" * 50)

# --- Navigator Agent Query Interface ---
def run_query(repo_path: str, output_dir: str, query_tool: str, query_arg: list):
    """
    Run a Navigator agent query against the codebase knowledge graph and semantic index.
    query_tool: one of 'find_implementation', 'trace_lineage', 'blast_radius', 'explain_module'
    query_arg: list of arguments for the tool
    """
    import json
    import os
    from src.agents.navigator import NavigatorAgent
    from src.agents.semanticist import SemanticistAgent
    from src.llm import LLMClient
    from src.graph.knowledge_graph import KnowledgeGraph

    # Load knowledge graph from .cartography/module_graph.json (or reconstruct)
    kg_path = os.path.join(output_dir, 'module_graph.json')
    if not os.path.exists(kg_path):
        raise FileNotFoundError(f"Knowledge graph not found at {kg_path}. Run analysis first.")
    with open(kg_path, 'r', encoding='utf-8') as f:
        kg_data = json.load(f)
    kg = KnowledgeGraph.from_json(kg_data)

    # Optionally load vector store/semantic index (not implemented here)
    vector_store = None
    # Optionally load semanticist for LLM explanations
    llm_client = LLMClient()
    semanticist = SemanticistAgent(kg, llm_client=llm_client)
    navigator = NavigatorAgent(kg, vector_store=vector_store, semanticist=semanticist)

    # Dispatch query
    if query_tool == 'find_implementation':
        if not query_arg or len(query_arg) < 1:
            print("Error: --query-arg <concept> required for find_implementation")
            return
        result = navigator.find_implementation(query_arg[0])
    elif query_tool == 'trace_lineage':
        if not query_arg or len(query_arg) < 1:
            print("Error: --query-arg <dataset> [direction] required for trace_lineage")
            return
        dataset = query_arg[0]
        direction = query_arg[1] if len(query_arg) > 1 else 'upstream'
        result = navigator.trace_lineage(dataset, direction)
    elif query_tool == 'blast_radius':
        if not query_arg or len(query_arg) < 1:
            print("Error: --query-arg <module_path> required for blast_radius")
            return
        result = navigator.blast_radius(query_arg[0])
    elif query_tool == 'explain_module':
        if not query_arg or len(query_arg) < 1:
            print("Error: --query-arg <path> required for explain_module")
            return
        result = navigator.explain_module(query_arg[0])
    else:
        print(f"Unknown query tool: {query_tool}")
        return
    # Print result as pretty JSON
    print(json.dumps(result, indent=2, ensure_ascii=False))