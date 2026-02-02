#!/usr/bin/env python3
"""
Pre-Ingestion Check - Verify Milvus v2 and Fuseki are ready before ingestion.

This script ensures:
1. Milvus v2 collection exists (or will be auto-created)
2. Fuseki dataset exists
3. Services are healthy
4. Logging is configured

Usage:
    uv run python scripts/pre_ingestion_check.py
"""

import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "agents" / "src"))

from config import get_settings
from storage.vector.milvus_store import MilvusStore
from fuseki_client import FusekiClient
import httpx


def check_milvus_v2() -> tuple[bool, str]:
    """Check if Milvus v2 collection is ready."""
    try:
        settings = get_settings()
        store = MilvusStore(settings=settings)
        
        # Check if collection exists
        from pymilvus import utility
        collection_name = getattr(settings, "milvus_collection_v2", None)
        if not collection_name:
            collection_name = f"{settings.milvus_collection}_v2"
        
        if utility.has_collection(collection_name):
            # Get stats
            stats = store.get_collection_stats()
            return True, f"Milvus v2 collection '{collection_name}' exists ({stats.get('num_entities', 0)} entities)"
        else:
            return True, f"Milvus v2 collection '{collection_name}' will be auto-created on first ingestion"
    except Exception as e:
        return False, f"Milvus v2 check failed: {e}"


def check_fuseki_dataset() -> tuple[bool, str]:
    """Check if Fuseki dataset exists."""
    try:
        settings = get_settings()
        client = FusekiClient(settings=settings)
        
        # Check if dataset exists
        response = httpx.get(
            f"{settings.fuseki_url}/$/datasets",
            auth=(settings.fuseki_user, settings.fuseki_password) if settings.fuseki_user else None,
            timeout=10.0,
        )
        
        if response.status_code == 200:
            datasets = response.json().get("datasets", [])
            dataset_names = [ds["ds.name"].lstrip("/") for ds in datasets]
            
            if settings.fuseki_dataset in dataset_names:
                # Get triple count
                try:
                    count = client.get_triple_count()
                    return True, f"Fuseki dataset '{settings.fuseki_dataset}' exists ({count:,} triples)"
                except Exception:
                    return True, f"Fuseki dataset '{settings.fuseki_dataset}' exists"
            else:
                return False, f"Fuseki dataset '{settings.fuseki_dataset}' does not exist. Run: make data-setup-fuseki"
        else:
            return False, f"Failed to check Fuseki datasets: {response.status_code}"
    except httpx.ConnectError:
        return False, "Fuseki server is not running. Start with: cd docker && docker-compose up -d fuseki"
    except Exception as e:
        return False, f"Fuseki check failed: {e}"


def check_services() -> tuple[bool, str]:
    """Check if all services are running."""
    settings = get_settings()
    issues = []
    
    # Check Fuseki
    try:
        response = httpx.get(f"{settings.fuseki_url}/$/ping", timeout=5.0)
        if response.status_code != 200:
            issues.append("Fuseki not responding")
    except Exception:
        issues.append("Fuseki not running")
    
    # Check Milvus
    try:
        from pymilvus import connections
        connections.connect(
            alias="default",
            host=settings.milvus_host,
            port=settings.milvus_port,
        )
        connections.disconnect(alias="default")
    except Exception:
        issues.append("Milvus not accessible")
    
    if issues:
        return False, f"Service issues: {', '.join(issues)}"
    return True, "All services are running"


def check_logging() -> tuple[bool, str]:
    """Check if logging is configured."""
    try:
        from logging_config import get_log_dir
        
        log_dir = get_log_dir("ingestion")
        if log_dir.exists():
            return True, f"Logging configured: {log_dir}"
        else:
            log_dir.mkdir(parents=True, exist_ok=True)
            return True, f"Logging directory created: {log_dir}"
    except Exception as e:
        return False, f"Logging check failed: {e}"


def main():
    """Run all pre-ingestion checks."""
    print("=" * 70)
    print("🔍 Pre-Ingestion System Check")
    print("=" * 70)
    print()
    
    all_ok = True
    
    # Check 1: Services
    print("1️⃣  Checking services...")
    ok, msg = check_services()
    status = "✅" if ok else "❌"
    print(f"   {status} {msg}")
    if not ok:
        all_ok = False
    print()
    
    # Check 2: Milvus v2
    print("2️⃣  Checking Milvus v2 collection...")
    ok, msg = check_milvus_v2()
    status = "✅" if ok else "❌"
    print(f"   {status} {msg}")
    if not ok:
        all_ok = False
    print()
    
    # Check 3: Fuseki dataset
    print("3️⃣  Checking Fuseki dataset...")
    ok, msg = check_fuseki_dataset()
    status = "✅" if ok else "❌"
    print(f"   {status} {msg}")
    if not ok:
        all_ok = False
    print()
    
    # Check 4: Logging
    print("4️⃣  Checking logging configuration...")
    ok, msg = check_logging()
    status = "✅" if ok else "❌"
    print(f"   {status} {msg}")
    if not ok:
        all_ok = False
    print()
    
    # Summary
    print("=" * 70)
    if all_ok:
        print("✅ All checks passed! Ready for ingestion.")
        print()
        print("📝 Notes:")
        print("   • Milvus v2 collection will be auto-created if needed")
        print("   • Summaries and dual embeddings will be stored")
        print("   • All ingestion steps will be logged")
        print()
        sys.exit(0)
    else:
        print("❌ Some checks failed. Please fix issues above before ingestion.")
        print()
        print("💡 Quick fixes:")
        print("   • Start services: cd docker && docker-compose up -d")
        print("   • Setup Fuseki: make data-setup-fuseki")
        print("   • Load ontology: make data-load-ontology")
        print()
        sys.exit(1)


if __name__ == "__main__":
    main()
