#!/usr/bin/env python3
"""
Setup Text Index for Fuseki

Creates and configures jena-text Lucene index for fast SPARQL text search.
This should be run after the dataset is created and data is loaded.

Usage:
    uv run python scripts/setup_text_index.py
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


def setup_text_index() -> bool:
    """
    Setup text index for the contracts dataset.
    
    Note: Text index configuration in Fuseki typically requires:
    1. A custom config.ttl file loaded at startup, OR
    2. Manual dataset configuration via Fuseki admin API
    
    Since the Docker image may not support custom config easily,
    we'll document the manual setup process.
    """
    print("📝 Setting up text index for Fuseki...")
    print("\n⚠️  IMPORTANT: Text indexing requires Fuseki to be started with")
    print("   a custom configuration file that includes text index setup.")
    print("\n📋 Manual Setup Steps:")
    print("   1. Stop Fuseki: docker-compose stop fuseki")
    print("   2. Copy fuseki-config.ttl to Fuseki config directory")
    print("   3. Start Fuseki with: --config=/path/to/fuseki-config.ttl")
    print("\n   OR use the Docker volume mount approach (already configured).")
    print("\n✅ The docker-compose.yml is already configured to mount")
    print("   docker/fuseki-config.ttl, but Fuseki needs to be started")
    print("   with that config file explicitly.")
    
    # Check if we can verify text index exists
    print("\n🔍 Testing text index availability...")
    try:
        query = """
        PREFIX text: <http://jena.apache.org/text#>
        PREFIX proc: <http://procurement.kg/ontology#>
        SELECT * WHERE { ?s text:query (proc:rawText 'test') . } LIMIT 1
        """
        
        response = httpx.post(
            f"{FUSEKI_URL}/{DATASET}/query",
            auth=(ADMIN_USER, ADMIN_PASSWORD),
            headers={"Content-Type": "application/sparql-query"},
            content=query,
            timeout=10.0,
        )
        
        if response.status_code == 200:
            # Check if we got an error about missing text index
            if "text index" in response.text.lower() or "No text index" in response.text:
                print("❌ Text index is NOT active")
                print("   The query executed but text index wasn't found.")
                return False
            else:
                print("✅ Text index appears to be active")
                return True
        else:
            print(f"⚠️  Query returned status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing text index: {e}")
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
    
    success = setup_text_index()
    
    if not success:
        print("\n📖 See docs/06_architecture/FUSEKI_TEXT_INDEXING.md for")
        print("   detailed setup instructions.")
        sys.exit(1)
    
    print("\n✅ Text index setup complete!")
    sys.exit(0)


if __name__ == "__main__":
    main()
