#!/usr/bin/env python3
"""
Health Check Script - Verify all system components are operational.

Usage:
    python scripts/health_check.py
    python scripts/health_check.py --json  # Output as JSON
    python scripts/health_check.py --component fuseki  # Check specific component
"""

import asyncio
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from health import HealthChecker, ComponentHealth
from config import get_settings


def print_health_status(health: ComponentHealth):
    """Print health status for a component."""
    status_icon = "✓" if health.healthy else "✗"
    status_color = "green" if health.healthy else "red"
    
    print(f"  {status_icon} {health.name.upper()}: {health.status}")
    print(f"    Response time: {health.response_time_ms:.1f}ms")
    
    if health.details:
        for key, value in health.details.items():
            print(f"    {key}: {value}")
    
    if health.error:
        print(f"    Error: {health.error}")
    
    print()


async def main():
    """Run health checks."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Check system health")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )
    parser.add_argument(
        "--component",
        type=str,
        choices=["fuseki", "milvus", "llm", "ontology_manager", "all"],
        default="all",
        help="Component to check (default: all)",
    )
    
    args = parser.parse_args()
    
    settings = get_settings()
    checker = HealthChecker(settings=settings)
    
    print("🔍 System Health Check")
    print("=" * 60)
    print()
    
    if args.component == "all":
        system_health = await checker.check_all()
        
        if args.json:
            print(json.dumps(system_health.model_dump(), indent=2, default=str))
            return
        
        print(f"Overall Status: {'✓ HEALTHY' if system_health.overall_healthy else '✗ UNHEALTHY'}")
        print(f"Timestamp: {system_health.timestamp}")
        print()
        
        for component in system_health.components:
            print_health_status(component)
        
        # Summary
        healthy_count = sum(1 for c in system_health.components if c.healthy)
        total_count = len(system_health.components)
        
        print("=" * 60)
        print(f"Summary: {healthy_count}/{total_count} components healthy")
        
        if not system_health.overall_healthy:
            sys.exit(1)
    
    else:
        # Check specific component
        if args.component == "fuseki":
            component = await checker.check_fuseki()
        elif args.component == "milvus":
            component = await checker.check_milvus()
        elif args.component == "llm":
            component = await checker.check_llm()
        elif args.component == "ontology_manager":
            component = await checker.check_ontology_manager()
        
        if args.json:
            print(json.dumps(component.model_dump(), indent=2, default=str))
        else:
            print_health_status(component)
        
        if not component.healthy:
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
