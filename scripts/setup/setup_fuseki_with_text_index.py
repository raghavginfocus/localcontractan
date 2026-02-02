#!/usr/bin/env python3
"""
Setup Fuseki Dataset with Text Index

Creates the contracts dataset with TDB2 + text indexing enabled.
This script should be run once when setting up the system.

Usage:
    uv run python scripts/setup_fuseki_with_text_index.py
"""

import sys
from pathlib import Path

import httpx

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "agents" / "src"))

# Configuration
FUSEKI_URL = "http://localhost:3030"
ADMIN_USER = "admin"
ADMIN_PASSWORD = "admin123"
DATASET = "contracts"


def check_fuseki_running() -> bool:
    """Check if Fuseki server is running."""
    try:
        response = httpx.get(f"{FUSEKI_URL}/$/ping", timeout=5.0)
        return response.status_code == 200
    except httpx.ConnectError:
        return False


def setup_dataset_with_text_index() -> bool:
    """
    Setup dataset with text indexing.
    
    Note: Text indexing in Fuseki requires the dataset to be created
    with a configuration file that includes text index setup.
    
    The standard API endpoint doesn't support text index configuration,
    so we need to use a config file approach.
    """
    print("📝 Setting up Fuseki dataset with text indexing...")
    print("\n⚠️  IMPORTANT: Text indexing requires Fuseki to be configured")
    print("   with a custom config.ttl file.")
    print("\n📋 Setup Instructions:")
    print("   1. Ensure docker/fuseki-config.ttl exists")
    print("   2. The Docker Compose setup should mount this config")
    print("   3. Restart Fuseki: docker-compose restart fuseki")
    print("\n   For manual setup:")
    print("   - Copy docker/fuseki-config.ttl to Fuseki config directory")
    print("   - Start Fuseki with: --config=/path/to/fuseki-config.ttl")
    
    # Check if dataset exists
    try:
        response = httpx.get(
            f"{FUSEKI_URL}/$/datasets",
            auth=(ADMIN_USER, ADMIN_PASSWORD),
            timeout=10.0,
        )
        if response.status_code == 200:
            datasets = response.json().get("datasets", [])
            dataset_names = [ds["ds.name"].lstrip("/") for ds in datasets]
            
            if DATASET in dataset_names:
                print(f"\n✅ Dataset '{DATASET}' exists")
                
                # Test text index
                print("\n🔍 Testing text index...")
                test_query = """
                PREFIX text: <http://jena.apache.org/text#>
                PREFIX proc: <http://procurement.kg/ontology#>
                SELECT * WHERE { ?s text:query (proc:rawText 'test') . } LIMIT 1
                """
                
                test_response = httpx.post(
                    f"{FUSEKI_URL}/{DATASET}/query",
                    auth=(ADMIN_USER, ADMIN_PASSWORD),
                    headers={"Content-Type": "application/sparql-query"},
                    content=test_query,
                    timeout=10.0,
                )
                
                if test_response.status_code == 200:
                    response_text = test_response.text.lower()
                    if "text index" in response_text or "no text index" in response_text:
                        print("❌ Text index is NOT active")
                        print("   Dataset exists but text index is not configured.")
                        print("\n   To fix:")
                        print("   1. Stop Fuseki: docker-compose stop fuseki")
                        print("   2. Delete dataset: curl -X DELETE http://localhost:3030/$/datasets/contracts -u admin:admin123")
                        print("   3. Start Fuseki with config: docker-compose up -d fuseki")
                        print("   4. The config file should create dataset with text index")
                        return False
                    else:
                        print("✅ Text index appears to be active")
                        return True
                else:
                    print(f"⚠️  Test query returned status {test_response.status_code}")
                    return False
            else:
                print(f"\n⚠️  Dataset '{DATASET}' does not exist")
                print("   Creating basic dataset (text index will be configured via config file)...")
                
                # Create basic dataset
                create_response = httpx.post(
                    f"{FUSEKI_URL}/$/datasets",
                    auth=(ADMIN_USER, ADMIN_PASSWORD),
                    data={"dbName": DATASET, "dbType": "tdb2"},
                    timeout=30.0,
                )
                
                if create_response.status_code in (200, 201):
                    print(f"✅ Dataset '{DATASET}' created")
                    print("   Note: Text index will be enabled when Fuseki is restarted with config file")
                    return True
                else:
                    print(f"❌ Failed to create dataset: {create_response.status_code}")
                    return False
    except Exception as e:
        print(f"❌ Error checking dataset: {e}")
        return False


def main():
    print("=" * 60)
    print("Fuseki Text Index Setup")
    print("=" * 60)
    
    if not check_fuseki_running():
        print("❌ Fuseki server is not running!")
        print("   Start it with: cd docker && docker-compose up -d fuseki")
        sys.exit(1)
    
    print("✅ Fuseki server is running\n")
    
    success = setup_dataset_with_text_index()
    
    if success:
        print("\n✅ Setup complete!")
        print("\n📖 See docs/06_architecture/FUSEKI_TEXT_INDEXING.md for usage examples")
    else:
        print("\n⚠️  Setup incomplete - see instructions above")
        sys.exit(1)
    
    sys.exit(0)


if __name__ == "__main__":
    main()
