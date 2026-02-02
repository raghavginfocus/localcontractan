#!/usr/bin/env python3
"""
Analyze Ingestion Pipeline Logs

Parses ingestion.log and generates a comprehensive summary report of each pipeline run.

Usage:
    cd agents
    PYTHONPATH=src uv run python ../scripts/analyze_ingestion_logs.py
    PYTHONPATH=src uv run python ../scripts/analyze_ingestion_logs.py --output report.md
    PYTHONPATH=src uv run python ../scripts/analyze_ingestion_logs.py --last 5  # Last 5 runs
"""

import argparse
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class StepMetrics:
    """Metrics for a single pipeline step."""
    name: str = ""
    started_at: str = ""
    completed_at: str = ""
    duration_ms: int = 0
    success: bool = True
    error: str | None = None
    warnings: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineRun:
    """Represents a complete ingestion pipeline run."""
    run_id: int = 0
    started_at: str = ""
    completed_at: str = ""
    document_id: str = ""
    total_duration_sec: float = 0.0
    steps: dict[str, StepMetrics] = field(default_factory=dict)
    summary: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    schema_evolution: dict[str, Any] = field(default_factory=dict)


class IngestionLogAnalyzer:
    """Analyzes ingestion pipeline logs."""
    
    # Step patterns
    STEP_PATTERNS = {
        "document_extraction": r"STEP 1|Starting document_extraction|Completed document_extraction",
        "clause_extraction": r"STEP 2: CLAUSE EXTRACTION|Starting clause_extraction|Completed clause_extraction|Extracted \d+ clauses",
        "entity_extraction": r"STEP 3: ENTITY EXTRACTION|Starting entity_extraction|Completed entity_extraction|Extracted \d+ entities",
        "obligation_risk": r"STEP 4: OBLIGATION/RISK EXTRACTION|Starting obligation_risk_extraction|Completed obligation_risk_extraction|Extracted \d+ obligations",
        "ontology_alignment": r"STEP 5: ONTOLOGY ALIGNMENT|Starting ontology_alignment|Completed ontology_alignment|Mapped \d+ concepts",
        "schema_evolution": r"STEP 5\.5: SCHEMA EVOLUTION|Processing:.*\(NewClass\)|Rules generated:",
        "rdf_generation": r"STEP 6: RDF GENERATION|Starting rdf_generation|Completed rdf_generation|Generated \d+ RDF triples",
        "validation": r"STEP 7: VALIDATION|Starting rdf_validation|Completed rdf_validation|Validation passed",
        "fuseki_load": r"STEP 8: FUSEKI LOAD|Starting fuseki_load|Completed fuseki_load|Loaded \d+ triples",
        "reasoning": r"STEP 9: REASONING|Starting reasoning|Completed reasoning|Inferred \d+ new facts",
        "vector_indexing": r"Starting vector_indexing|Completed vector_indexing",
    }
    
    def __init__(self, log_file: Path):
        self.log_file = log_file
        self.runs: list[PipelineRun] = []
    
    def parse(self) -> list[PipelineRun]:
        """Parse the log file and extract pipeline runs."""
        if not self.log_file.exists():
            print(f"❌ Log file not found: {self.log_file}")
            return []
        
        with open(self.log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        current_run: PipelineRun | None = None
        current_step: StepMetrics | None = None
        run_id = 0
        
        for line in lines:
            # Parse log line: timestamp | level | module | message
            match = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \| (\w+)\s+\| [^|]+\| (.+)", line)
            if not match:
                continue
            
            timestamp, level, message = match.groups()
            
            # Detect pipeline start
            if "Starting ingestion pipeline" in message:
                if current_run:
                    self._finalize_run(current_run)
                run_id += 1
                current_run = PipelineRun(run_id=run_id, started_at=timestamp)
                current_step = None
            
            if not current_run:
                continue
            
            # Detect pipeline completion
            if "Ingestion completed" in message:
                current_run.completed_at = timestamp
                self._finalize_run(current_run)
                current_run = None
                current_step = None
                continue
            
            # Extract document ID
            doc_match = re.search(r"doc_[\w]+", message)
            if doc_match and not current_run.document_id:
                current_run.document_id = doc_match.group()
            
            # Process steps
            self._process_step_message(current_run, timestamp, level, message)
            
            # Extract metrics
            self._extract_metrics(current_run, message, level)
        
        # Finalize last run if exists
        if current_run:
            self._finalize_run(current_run)
        
        return self.runs
    
    def _process_step_message(self, run: PipelineRun, timestamp: str, level: str, message: str):
        """Process step-related messages."""
        step_name = None
        
        # Identify step from message
        for step, pattern in self.STEP_PATTERNS.items():
            if re.search(pattern, message, re.IGNORECASE):
                step_name = step
                break
        
        if not step_name:
            return
        
        if step_name not in run.steps:
            run.steps[step_name] = StepMetrics(name=step_name)
        
        step = run.steps[step_name]
        
        # Step start
        if "Starting" in message:
            step.started_at = timestamp
        
        # Step completion
        if "Completed" in message:
            step.completed_at = timestamp
            if step.started_at:
                try:
                    start = datetime.strptime(step.started_at, "%Y-%m-%d %H:%M:%S")
                    end = datetime.strptime(step.completed_at, "%Y-%m-%d %H:%M:%S")
                    step.duration_ms = int((end - start).total_seconds() * 1000)
                except:
                    pass
        
        # Errors
        if level == "ERROR":
            step.success = False
            if message not in step.warnings:
                step.error = message
                run.errors.append(f"{step_name}: {message}")
        
        # Warnings
        if level == "WARNING":
            if message not in step.warnings:
                step.warnings.append(message)
                run.warnings.append(f"{step_name}: {message}")
    
    def _extract_metrics(self, run: PipelineRun, message: str, level: str):
        """Extract metrics from log messages."""
        # Clauses
        match = re.search(r"Extracted (\d+) clauses", message)
        if match:
            run.summary["clauses_extracted"] = int(match.group(1))
            run.steps.get("clause_extraction", StepMetrics()).metrics["count"] = int(match.group(1))
        
        # Clause types
        match = re.search(r"Types: \[(.*?)\]", message)
        if match:
            types = [t.strip().strip("'\"") for t in match.group(1).split(",")]
            run.summary["clause_types"] = types
        
        # Entities
        match = re.search(r"Extracted (\d+) entities", message)
        if match:
            run.summary["entities_extracted"] = int(match.group(1))
        
        match = re.search(r"Parties: (\d+), Dates: (\d+), Amounts: (\d+)", message)
        if match:
            run.summary["parties"] = int(match.group(1))
            run.summary["dates"] = int(match.group(2))
            run.summary["amounts"] = int(match.group(3))
        
        # Obligations and Risks
        match = re.search(r"Extracted (\d+) obligations, (\d+) risks", message)
        if match:
            run.summary["obligations"] = int(match.group(1))
            run.summary["risks"] = int(match.group(2))
        
        # Ontology alignment
        match = re.search(r"Mapped (\d+) concepts", message)
        if match:
            run.summary["concepts_mapped"] = int(match.group(1))
        
        match = re.search(r"Score: ([\d.]+), Suggestions: (\d+)", message)
        if match:
            run.summary["alignment_score"] = float(match.group(1))
            run.summary["alignment_suggestions"] = int(match.group(2))
        
        # Schema evolution
        if "Processing:" in message and "NewClass" in message:
            match = re.search(r"Processing: (\w+) \(NewClass\)", message)
            if match:
                if "new_classes" not in run.schema_evolution:
                    run.schema_evolution["new_classes"] = []
                run.schema_evolution["new_classes"].append(match.group(1))
        
        match = re.search(r"Rules generated: (\d+)", message)
        if match:
            run.schema_evolution["rules_generated"] = int(match.group(1))
        
        match = re.search(r"Patterns detected: (\d+)", message)
        if match:
            run.schema_evolution["patterns_detected"] = int(match.group(1))
        
        # RDF generation
        match = re.search(r"Generated (\d+) RDF triples", message)
        if match:
            run.summary["triples_generated"] = int(match.group(1))
        
        # Validation
        match = re.search(r"Validation passed \(syntax: (\w+), SHACL: (\w+)\)", message)
        if match:
            run.summary["validation_syntax"] = match.group(1) == "True"
            run.summary["validation_shacl"] = match.group(2) == "True"
        
        # Fuseki load
        match = re.search(r"Loaded (\d+) triples to graph: (.+)", message)
        if match:
            run.summary["triples_loaded"] = int(match.group(1))
            run.summary["graph_uri"] = match.group(2)
        
        # Reasoning
        match = re.search(r"Inferred (\d+) new facts", message)
        if match:
            run.summary["facts_inferred"] = int(match.group(1))
        
        match = re.search(r"Rules applied: (.+)", message)
        if match:
            rules = [r.strip() for r in match.group(1).split(",")]
            run.summary["rules_applied"] = rules
        
        # Rule file used
        match = re.search(r"Using (?:default|generated) rule file: (.+)", message)
        if match:
            run.summary["rule_file"] = match.group(1)
        
        # Duration
        match = re.search(r"Duration: (\d+)ms", message)
        if match and "step" in locals():
            step = run.steps.get("clause_extraction")
            if step:
                step.duration_ms = int(match.group(1))
    
    def _finalize_run(self, run: PipelineRun):
        """Finalize a pipeline run and calculate total duration."""
        if run.started_at and run.completed_at:
            try:
                start = datetime.strptime(run.started_at, "%Y-%m-%d %H:%M:%S")
                end = datetime.strptime(run.completed_at, "%Y-%m-%d %H:%M:%S")
                run.total_duration_sec = (end - start).total_seconds()
            except:
                pass
        
        self.runs.append(run)
    
    def generate_report(self, output_file: Path | None = None, last_n: int | None = None) -> str:
        """Generate a markdown report."""
        runs = self.runs
        if last_n:
            runs = runs[-last_n:]
        
        if not runs:
            return "# Ingestion Pipeline Analysis\n\nNo pipeline runs found in logs.\n"
        
        report = []
        report.append("# Ingestion Pipeline Analysis Report\n")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        report.append(f"Total Runs Analyzed: {len(runs)}\n")
        report.append(f"Log File: {self.log_file}\n\n")
        report.append("---\n\n")
        
        # Summary statistics
        report.append("## Summary Statistics\n\n")
        total_clauses = sum(r.summary.get("clauses_extracted", 0) for r in runs)
        total_entities = sum(r.summary.get("entities_extracted", 0) for r in runs)
        total_obligations = sum(r.summary.get("obligations", 0) for r in runs)
        total_risks = sum(r.summary.get("risks", 0) for r in runs)
        total_triples = sum(r.summary.get("triples_generated", 0) for r in runs)
        total_facts = sum(r.summary.get("facts_inferred", 0) for r in runs)
        total_duration = sum(r.total_duration_sec for r in runs)
        successful_runs = sum(1 for r in runs if not r.errors)
        
        report.append(f"- **Total Runs**: {len(runs)}\n")
        report.append(f"- **Successful Runs**: {successful_runs} ({successful_runs/len(runs)*100:.1f}%)\n")
        report.append(f"- **Total Duration**: {total_duration:.1f}s ({total_duration/60:.1f} minutes)\n")
        report.append(f"- **Average Duration per Run**: {total_duration/len(runs):.1f}s\n")
        report.append(f"- **Total Clauses Extracted**: {total_clauses}\n")
        report.append(f"- **Total Entities Extracted**: {total_entities}\n")
        report.append(f"- **Total Obligations**: {total_obligations}\n")
        report.append(f"- **Total Risks**: {total_risks}\n")
        report.append(f"- **Total Triples Generated**: {total_triples}\n")
        report.append(f"- **Total Facts Inferred**: {total_facts}\n\n")
        report.append("---\n\n")
        
        # Individual runs
        for i, run in enumerate(reversed(runs), 1):
            report.append(f"## Run #{i}: {run.document_id or 'Unknown'}\n\n")
            
            # Basic info
            report.append(f"**Started**: {run.started_at}\n")
            report.append(f"**Completed**: {run.completed_at or 'Incomplete'}\n")
            report.append(f"**Duration**: {run.total_duration_sec:.1f}s ({run.total_duration_sec/60:.1f} min)\n")
            report.append(f"**Status**: {'✅ Success' if not run.errors else '❌ Failed'}\n\n")
            
            # Metrics summary
            report.append("### Metrics Summary\n\n")
            if run.summary:
                metrics = [
                    ("Clauses Extracted", run.summary.get("clauses_extracted", 0)),
                    ("Entities Extracted", run.summary.get("entities_extracted", 0)),
                    ("Obligations", run.summary.get("obligations", 0)),
                    ("Risks", run.summary.get("risks", 0)),
                    ("Triples Generated", run.summary.get("triples_generated", 0)),
                    ("Triples Loaded", run.summary.get("triples_loaded", 0)),
                    ("Facts Inferred", run.summary.get("facts_inferred", 0)),
                ]
                
                for label, value in metrics:
                    if value or value == 0:
                        report.append(f"- **{label}**: {value}\n")
                
                if run.summary.get("clause_types"):
                    report.append(f"- **Clause Types**: {', '.join(run.summary['clause_types'])}\n")
                
                if run.summary.get("alignment_score") is not None:
                    report.append(f"- **Alignment Score**: {run.summary['alignment_score']:.2f}\n")
                    report.append(f"- **Alignment Suggestions**: {run.summary.get('alignment_suggestions', 0)}\n")
                
                if run.summary.get("rules_applied"):
                    report.append(f"- **Rules Applied**: {len(run.summary['rules_applied'])} rules\n")
                    report.append(f"  - {', '.join(run.summary['rules_applied'][:5])}")
                    if len(run.summary['rules_applied']) > 5:
                        report.append(f"  - ... and {len(run.summary['rules_applied']) - 5} more")
                    report.append("\n")
            
            report.append("\n")
            
            # Steps timeline
            report.append("### Pipeline Steps\n\n")
            step_order = [
                "document_extraction", "clause_extraction", "entity_extraction",
                "obligation_risk", "ontology_alignment", "schema_evolution",
                "rdf_generation", "validation", "fuseki_load", "reasoning", "vector_indexing"
            ]
            
            for step_name in step_order:
                if step_name in run.steps:
                    step = run.steps[step_name]
                    status = "✅" if step.success else "❌"
                    duration = f"{step.duration_ms/1000:.1f}s" if step.duration_ms else "N/A"
                    report.append(f"- {status} **{step_name.replace('_', ' ').title()}**: {duration}\n")
                    if step.warnings:
                        for warning in step.warnings[:3]:
                            report.append(f"  - ⚠️ {warning[:100]}...\n" if len(warning) > 100 else f"  - ⚠️ {warning}\n")
                    if step.error:
                        report.append(f"  - ❌ Error: {step.error[:200]}...\n" if len(step.error) > 200 else f"  - ❌ Error: {step.error}\n")
            
            report.append("\n")
            
            # Schema evolution
            if run.schema_evolution:
                report.append("### Schema Evolution\n\n")
                if run.schema_evolution.get("new_classes"):
                    report.append(f"- **New Classes**: {', '.join(run.schema_evolution['new_classes'])}\n")
                if run.schema_evolution.get("rules_generated"):
                    report.append(f"- **Rules Generated**: {run.schema_evolution['rules_generated']}\n")
                if run.schema_evolution.get("patterns_detected"):
                    report.append(f"- **Patterns Detected**: {run.schema_evolution['patterns_detected']}\n")
                report.append("\n")
            
            # Errors and warnings
            if run.errors:
                report.append("### Errors\n\n")
                for error in run.errors[:5]:
                    report.append(f"- ❌ {error[:200]}...\n" if len(error) > 200 else f"- ❌ {error}\n")
                if len(run.errors) > 5:
                    report.append(f"- ... and {len(run.errors) - 5} more errors\n")
                report.append("\n")
            
            if run.warnings:
                report.append("### Warnings\n\n")
                for warning in run.warnings[:10]:
                    report.append(f"- ⚠️ {warning[:150]}...\n" if len(warning) > 150 else f"- ⚠️ {warning}\n")
                if len(run.warnings) > 10:
                    report.append(f"- ... and {len(run.warnings) - 10} more warnings\n")
                report.append("\n")
            
            report.append("---\n\n")
        
        report_text = "".join(report)
        
        if output_file:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(report_text)
            print(f"✅ Report saved to: {output_file}")
        
        return report_text


def main():
    parser = argparse.ArgumentParser(description="Analyze ingestion pipeline logs")
    parser.add_argument(
        "--log-file",
        type=Path,
        default=Path("agents/logs/ingestion/ingestion.log"),
        help="Path to ingestion log file"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output file path (default: print to stdout)"
    )
    parser.add_argument(
        "--last",
        type=int,
        help="Analyze only the last N runs"
    )
    
    args = parser.parse_args()
    
    # Resolve log file path
    log_file = args.log_file
    if not log_file.is_absolute():
        log_file = Path(__file__).parent.parent / log_file
    
    analyzer = IngestionLogAnalyzer(log_file)
    runs = analyzer.parse()
    
    if not runs:
        print("❌ No pipeline runs found in logs.")
        return
    
    print(f"✅ Found {len(runs)} pipeline run(s)")
    
    report = analyzer.generate_report(output_file=args.output, last_n=args.last)
    
    if not args.output:
        print("\n" + "=" * 70)
        print(report)


if __name__ == "__main__":
    main()
