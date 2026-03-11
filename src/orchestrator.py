# Orchestrator for running analysis pipeline
from src.agents.dynamic_surveyor import DynamicSurveyor
from src.agents.hydrologist import HydrologistAgent   # <-- import the new agent
import os
import json
import datetime

def run_analysis(repo_path):
    # Phase 1: Surveyor (unchanged)
    surveyor = DynamicSurveyor()
    surveyor_results = surveyor.analyze_repo(repo_path)

    # Save surveyor results (keep as before, or move to .cartography)
    output_dir = os.path.join(os.path.dirname(__file__), '..', '.cartography')  # per spec
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')

    surveyor_output_path = os.path.join(output_dir, f"analysis_results_{timestamp}.json")
    with open(surveyor_output_path, 'w', encoding='utf-8') as f:
        json.dump(surveyor_results, f, indent=2, ensure_ascii=False)

    # Phase 2: Hydrologist (new version)
    hydrologist = HydrologistAgent()
    lineage_graph = hydrologist.analyze_repo(repo_path)  # builds the DataLineageGraph

    # Save the lineage graph (required artifact)
    lineage_graph_path = os.path.join(output_dir, 'lineage_graph.json')
    with open(lineage_graph_path, 'w', encoding='utf-8') as f:
        json.dump(lineage_graph.to_json_serializable(), f, indent=2)

    # (Optional) Also save the raw per‑file results if needed for debugging
    # hydrologist_results = hydrologist.raw_results  # if you add a collector
    # hydrologist_output_path = os.path.join(output_dir, f"hydrologist_results_{timestamp}.json")
    # with open(hydrologist_output_path, 'w') as f:
    #     json.dump(hydrologist_results, f, indent=2)

    print(f"Surveyor results saved to {surveyor_output_path}")
    print(f"Lineage graph saved to {lineage_graph_path}")