# Orchestrator for running analysis pipeline
from src.agents.dynamic_surveyor import DynamicSurveyor
from src.agents.hydrologist import HydrologistAgent
from src.graph.knowledge_graph import KnowledgeGraph
import os
import json
import datetime

def run_analysis(repo_path):
    kg = KnowledgeGraph()

    # Phase 1: Surveyor
    surveyor = DynamicSurveyor(kg)
    report = surveyor.analyze_repo(repo_path)   # now returns a report

    # Phase 2: Hydrologist
    hydrologist = HydrologistAgent(kg)
    hydrologist.analyze_repo(repo_path)

    # Save unified knowledge graph
    output_dir = os.path.join(os.path.dirname(__file__), '..', '.cartography')
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')

    kg_path = os.path.join(output_dir, f'knowledge_graph_{timestamp}.json')
    with open(kg_path, 'w', encoding='utf-8') as f:
        json.dump(kg.to_json_serializable(), f, indent=2)

    # Save surveyor report
    report_path = os.path.join(output_dir, f'surveyor_report_{timestamp}.json')
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2)

    print(f"Knowledge graph saved to {kg_path}")
    print(f"Surveyor report saved to {report_path}")