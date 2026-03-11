import os
import json
import datetime
import logging
from src.agents.dynamic_surveyor import DynamicSurveyor
from src.agents.hydrologist import HydrologistAgent
from src.graph.knowledge_graph import KnowledgeGraph

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

    # Phase 2: Hydrologist
    logger.info("=" * 50)
    logger.info("Phase 2: Hydrologist – data lineage analysis")
    logger.info("=" * 50)
    hydrologist = HydrologistAgent(kg, sql_dialect=sql_dialect)
    hydrologist.analyze_repo(repo_path)

    kg_path = os.path.join(output_dir, f'knowledge_graph_{timestamp}.json')
    with open(kg_path, 'w', encoding='utf-8') as f:
        json.dump(kg.to_json_serializable(), f, indent=2)
    logger.info(f"Knowledge graph saved to {kg_path}")

    logger.info("=" * 50)
    logger.info("Analysis complete. Artifacts are in: %s", output_dir)
    logger.info("=" * 50)