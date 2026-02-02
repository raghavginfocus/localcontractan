#!/usr/bin/env python3
"""
Test API Queries from YAML Files

Sends queries from test case YAML files to the running API endpoint
and displays results with timing and logging improvements.
"""

import argparse
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import httpx
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

console = Console()


def load_test_cases(yaml_file: Path) -> List[Dict[str, Any]]:
    """Load test cases from YAML file."""
    with open(yaml_file) as f:
        data = yaml.safe_load(f)
    return data.get("test_cases", [])


def send_query(
    api_url: str, question: str, timeout: int = 300
) -> Dict[str, Any]:
    """Send query to API endpoint."""
    try:
        response = httpx.post(
            f"{api_url}/api/v1/query",
            json={
                "query": question,
                "max_results": 10,
                "include_reasoning": True,
            },
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        console.print(f"[red]HTTP Error: {e}[/red]")
        return {"error": str(e)}
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return {"error": str(e)}


def display_result(
    test_case: Dict[str, Any], result: Dict[str, Any], elapsed: float
):
    """Display query result in a formatted way."""
    # Create result table
    table = Table(title=f"Test: {test_case['name']}", show_header=True)
    table.add_column("Field", style="cyan", width=20)
    table.add_column("Value", style="white")

    # Add test case info
    table.add_row("ID", test_case["id"])
    table.add_row("Question", test_case["question"])
    table.add_row("Category", test_case.get("category", "N/A"))
    table.add_row("Level", test_case.get("level", "N/A"))
    table.add_row("Time Taken", f"{elapsed:.2f}s")

    # Add result info
    if "error" in result:
        table.add_row("Status", "[red]ERROR[/red]")
        table.add_row("Error", result["error"])
    else:
        table.add_row("Status", "[green]SUCCESS[/green]")
        
        # Extract answer
        answer = result.get("answer", "No answer")
        if len(answer) > 200:
            answer = answer[:200] + "..."
        table.add_row("Answer", answer)
        
        # Show source info if available
        if "metadata" in result:
            metadata = result["metadata"]
            if "kg_facts_count" in metadata:
                table.add_row("KG Facts", str(metadata["kg_facts_count"]))
            if "vector_results_count" in metadata:
                table.add_row("Vector Results", str(metadata["vector_results_count"]))
            if "total_time_ms" in metadata:
                table.add_row("Total Time", f"{metadata['total_time_ms']:.2f}ms")

    console.print(table)
    console.print()


def main():
    parser = argparse.ArgumentParser(
        description="Test API queries from YAML files"
    )
    parser.add_argument(
        "--yaml",
        type=Path,
        required=True,
        help="Path to YAML test cases file",
    )
    parser.add_argument(
        "--api-url",
        default="http://localhost:8001",
        help="API base URL (default: http://localhost:8001)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Request timeout in seconds (default: 300)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of test cases to run",
    )
    
    args = parser.parse_args()

    # Check if YAML file exists
    if not args.yaml.exists():
        console.print(f"[red]Error: YAML file not found: {args.yaml}[/red]")
        sys.exit(1)

    # Load test cases
    console.print(f"[blue]Loading test cases from {args.yaml}...[/blue]")
    test_cases = load_test_cases(args.yaml)
    
    if args.limit:
        test_cases = test_cases[:args.limit]
    
    console.print(f"[green]✅ Loaded {len(test_cases)} test case(s)[/green]\n")

    # Display header
    console.print(
        Panel.fit(
            f"[bold]Contract KG RAG - API Query Test[/bold]\n"
            f"API URL: {args.api_url}\n"
            f"Test Cases: {len(test_cases)}\n"
            f"Timeout: {args.timeout}s",
            border_style="blue",
        )
    )
    console.print()

    # Run test cases
    results = []
    for i, test_case in enumerate(test_cases, 1):
        console.print(
            f"[bold cyan][{i}/{len(test_cases)}] Running: {test_case['name']}[/bold cyan]"
        )
        
        # Send query with progress indicator
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(
                f"Querying API...", total=None
            )
            
            start_time = time.time()
            result = send_query(
                args.api_url, test_case["question"], args.timeout
            )
            elapsed = time.time() - start_time
            
            progress.update(task, completed=True)

        # Display result
        display_result(test_case, result, elapsed)
        
        # Store result
        results.append({
            "test_case": test_case,
            "result": result,
            "elapsed": elapsed,
            "success": "error" not in result,
        })

    # Display summary
    console.print("\n" + "=" * 70)
    console.print("[bold]Summary[/bold]")
    console.print("=" * 70)
    
    success_count = sum(1 for r in results if r["success"])
    total_time = sum(r["elapsed"] for r in results)
    avg_time = total_time / len(results) if results else 0
    
    summary_table = Table(show_header=False)
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Value", style="white")
    
    summary_table.add_row("Total Tests", str(len(results)))
    summary_table.add_row(
        "Successful",
        f"[green]{success_count}[/green]",
    )
    summary_table.add_row(
        "Failed",
        f"[red]{len(results) - success_count}[/red]",
    )
    summary_table.add_row("Total Time", f"{total_time:.2f}s")
    summary_table.add_row("Average Time", f"{avg_time:.2f}s")
    
    console.print(summary_table)
    
    # Exit with error code if any tests failed
    if success_count < len(results):
        sys.exit(1)


if __name__ == "__main__":
    main()


