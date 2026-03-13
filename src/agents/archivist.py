import os
from typing import Dict, Any


class ArchivistAgent:
    def __init__(self, knowledge_graph, surveyor_report, hydrologist_report, semanticist_report, trace_logger=None):
        self.kg = knowledge_graph
        self.surveyor_report = surveyor_report
        self.hydrologist_report = hydrologist_report
        self.semanticist_report = semanticist_report
        self.trace_logger = trace_logger

    def generate_onboarding_brief_md(self, output_path: str, changed_files=None, added_files=None, deleted_files=None):
        """
        Generate onboarding_brief.md answering the Five FDE Day-One Questions with evidence citations.
        Sections:
        - Introduction
        - Q1-Q5: Each Day-One question, answer, and evidence
        Supports incremental update via changed_files, added_files, deleted_files.
        """
        if changed_files or added_files or deleted_files:
            if self.trace_logger:
                self.trace_logger.log(agent="Archivist", action="incremental_onboarding_brief_md", input_data={"changed": changed_files, "added": added_files, "deleted": deleted_files}, output_data=output_path, evidence=None)
            # For simplicity, regenerate the whole file, but in a real system, you could cache and update sections
        lines = []
        lines.append("# Onboarding Brief\n\n")
        lines.append("This onboarding brief answers the Five FDE Day-One Questions for rapid onboarding. Each answer cites evidence from the codebase analysis.\n\n")
        day_one = self.semanticist_report.get('day_one_answers')
        if not day_one:
            lines.append("Day-One answers not available. Please ensure the Semanticist phase ran successfully.\n")
        else:
            questions = [
                ("q1", "1. What is the primary data ingestion path?"),
                ("q2", "2. What are the 3-5 most critical output datasets/endpoints?"),
                ("q3", "3. What is the blast radius if the most critical module fails?"),
                ("q4", "4. Where is the business logic concentrated vs. distributed?"),
                ("q5", "5. What has changed most frequently in the last 90 days (git velocity map)?")
            ]
            for key, qtext in questions:
                answer = day_one.get(key, "No answer available.")
                lines.append(f"## {qtext}\n")
                if isinstance(answer, dict):
                    # If answer is structured, print answer and evidence
                    main = answer.get('answer', '')
                    evidence = answer.get('evidence', '')
                    lines.append(f"**Answer:** {main}\n\n")
                    lines.append(f"**Evidence:** {evidence}\n\n")
                else:
                    lines.append(f"{answer}\n\n")
        with open(output_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)

    def generate_CODEBASE_md(self, output_path: str, changed_files=None, added_files=None, deleted_files=None):
        """
        Generate CODEBASE.md with sections:
        - Architecture Overview
        - Critical Path
        - Data Sources & Sinks
        - Known Debt
        - Recent Change Velocity
        - Module Purpose Index
        Supports incremental update via changed_files, added_files, deleted_files.
        """
        if changed_files or added_files or deleted_files:
            if self.trace_logger:
                self.trace_logger.log(agent="Archivist", action="incremental_CODEBASE_md", input_data={"changed": changed_files, "added": added_files, "deleted": deleted_files}, output_data=output_path, evidence=None)
            # For simplicity, regenerate the whole file, but in a real system, you could cache and update sections
        lines = []
        lines.append("# CODEBASE.md\n")
        # Architecture Overview (stub)
        lines.append("## Architecture Overview\n")
        lines.append("This codebase was analyzed by the Brownfield Cartographer. The following sections provide a living map of its structure, data flows, and semantic purpose.\n")
        # Critical Path (top 5 modules by PageRank)
        lines.append("## Critical Path\n")
        cp = self.surveyor_report.get('critical_path', [])
        if cp:
            lines.append("Top 5 modules by PageRank:\n")
            for mod in cp:
                lines.append(f"- {mod}\n")
        else:
            lines.append("Critical path data not available.\n")
        # Data Sources & Sinks
        lines.append("\n## Data Sources & Sinks\n")
        sources = self.hydrologist_report.get('sources', [])
        sinks = self.hydrologist_report.get('sinks', [])
        lines.append("**Sources:**\n")
        for s in sources:
            lines.append(f"- {s}\n")
        lines.append("**Sinks:**\n")
        for s in sinks:
            lines.append(f"- {s}\n")
        # Known Debt (circular deps + doc drift flags)
        lines.append("\n## Known Debt\n")
        debt = self.surveyor_report.get('circular_dependencies', [])
        doc_drift = [k for k, v in self.semanticist_report.items() if isinstance(v, dict) and v.get('documentation_drift')]
        if debt:
            lines.append("Circular dependencies detected in:\n")
            for d in debt:
                lines.append(f"- {d}\n")
        if doc_drift:
            lines.append("Modules with documentation drift:\n")
            for d in doc_drift:
                lines.append(f"- {d}\n")
        if not debt and not doc_drift:
            lines.append("No known debt detected.\n")
        # Recent Change Velocity
        lines.append("\n## High-Velocity Files\n")
        hv = self.surveyor_report.get('high_velocity_files', [])
        if hv:
            for f in hv:
                lines.append(f"- {f}\n")
        else:
            lines.append("No high-velocity files detected.\n")
        # Module Purpose Index
        lines.append("\n## Module Purpose Index\n")
        for k, v in self.semanticist_report.items():
            if isinstance(v, dict) and v.get('purpose_statement'):
                lines.append(f"- {k}: {v['purpose_statement']}\n")
        with open(output_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
