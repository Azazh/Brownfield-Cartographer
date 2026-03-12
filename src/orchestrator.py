
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

    # Phase 1: Surveyor
    logger.info("=" * 50)
    logger.info("Phase 1: Surveyor – static structure analysis")
    logger.info("=" * 50)
    surveyor = DynamicSurveyor(kg)
    report = surveyor.analyze_repo(repo_path)

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

    # Phase 2: Hydrologist
    logger.info("=" * 50)
    logger.info("Phase 2: Hydrologist – data lineage analysis")
    logger.info("=" * 50)
    hydrologist = HydrologistAgent(kg, sql_dialect=sql_dialect)
    hydrologist.analyze_repo(repo_path)

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

    # Phase 3: Semanticist
    logger.info("=" * 50)
    logger.info("Phase 3: Semanticist – semantic analysis (LLM-powered)")
    logger.info("=" * 50)
    from src.llm import LLMClient
    # Instantiate LLMClient with environment/config support
    llm_client = LLMClient()
    semanticist = SemanticistAgent(kg, llm_client=llm_client)
    # Pass surveyor and hydrologist reports for Day-One answers
    semantic_report = semanticist.analyze_repo(repo_path, surveyor_report=report, hydrologist_report={})
    semantic_report_path = os.path.join(output_dir, f'semanticist_report_{timestamp}.json')
    with open(semantic_report_path, 'w', encoding='utf-8') as f:
        json.dump(semantic_report, f, indent=2)
    logger.info(f"Semanticist report saved to {semantic_report_path}")

    logger.info("=" * 50)
    logger.info("Analysis complete. Artifacts are in: %s", output_dir)
    logger.info("=" * 50)