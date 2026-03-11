"""
Orchestrator – runs Surveyor and Hydrologist sequentially,
saves artifacts, and provides progress logging.
"""

import os
import json
import datetime
import logging
from src.agents.dynamic_surveyor import DynamicSurveyor
from src.agents.hydrologist import HydrologistAgent
from src.graph.knowledge_graph import KnowledgeGraph

logger = logging.getLogger(__name__)

def run_analysis(repo_path: str, output_dir: str = '.cartography'):
    """
    Run the full analysis pipeline.
    - repo_path: local path to the repository (already cloned if needed)
    - output_dir: directory where artifacts will be saved
    """
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Shared knowledge graph
    kg = KnowledgeGraph()
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')

    # Phase 1: Surveyor
    logger.info("=" * 50)
    logger.info("Phase 1: Surveyor – static structure analysis")
    logger.info("=" * 50)
    surveyor = DynamicSurveyor(kg)
    report = surveyor.analyze_repo(repo_path)   # returns surveyor report

    # Save surveyor report
    report_path = os.path.join(output_dir, f'surveyor_report_{timestamp}.json')
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2)
    logger.info(f"Surveyor report saved to {report_path}")

    # Phase 2: Hydrologist
    logger.info("=" * 50)
    logger.info("Phase 2: Hydrologist – data lineage analysis")
    logger.info("=" * 50)
    hydrologist = HydrologistAgent(kg)
    hydrologist.analyze_repo(repo_path)

    # Save unified knowledge graph
    kg_path = os.path.join(output_dir, f'knowledge_graph_{timestamp}.json')
    with open(kg_path, 'w', encoding='utf-8') as f:
        json.dump(kg.to_json_serializable(), f, indent=2)
    logger.info(f"Knowledge graph saved to {kg_path}")

    logger.info("=" * 50)
    logger.info("Analysis complete. Artifacts are in: %s", output_dir)
    logger.info("=" * 50)