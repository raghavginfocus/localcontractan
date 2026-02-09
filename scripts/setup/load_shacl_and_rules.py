#!/usr/bin/env python3
"""
Load SHACL shapes and reasoning rules into Fuseki.
"""
import sys
import os
from pathlib import Path

# Set env file path before importing config
os.environ.setdefault("ENV_FILE", str(Path(__file__).parent.parent.parent / "agents" / ".env"))

# Add agents/src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "agents" / "src"))

from config import Settings
from fuseki_client import FusekiClient
import asyncio


def get_settings_with_env():
    """Load settings from agents/.env file."""
    env_file = Path(__file__).parent.parent.parent / "agents" / ".env"
    return Settings(_env_file=str(env_file))


async def load_shacl_shapes():
    """Load all SHACL shapes into Fuseki."""
    settings = get_settings_with_env()
    client = FusekiClient(settings)
    
    shacl_dir = Path("agents/data/generated/shacl")
    if not shacl_dir.exists():
        print(f"⚠️  SHACL directory not found: {shacl_dir}")
        return 0
    
    shacl_files = list(shacl_dir.glob("*.ttl"))
    print(f"\n📋 Found {len(shacl_files)} SHACL shape files")
    
    loaded_count = 0
    for shacl_file in shacl_files:
        try:
            with open(shacl_file, 'r') as f:
                content = f.read()
            
            # Load into a SHACL-specific graph
            graph_uri = f"http://procurement.kg/shacl#{shacl_file.stem}"
            success = client.load_turtle(content, graph_uri=graph_uri)
            
            if success:
                loaded_count += 1
                print(f"  ✓ Loaded: {shacl_file.name}")
            else:
                print(f"  ✗ Failed: {shacl_file.name}")
        except Exception as e:
            print(f"  ✗ Error loading {shacl_file.name}: {e}")
    
    print(f"\n✅ Loaded {loaded_count}/{len(shacl_files)} SHACL shapes")
    return loaded_count


async def load_reasoning_rules():
    """Load reasoning rules into Fuseki."""
    settings = get_settings_with_env()
    client = FusekiClient(settings)
    
    rules_dir = Path("agents/data/generated/rules")
    if not rules_dir.exists():
        print(f"⚠️  Rules directory not found: {rules_dir}")
        return 0
    
    # Load .sparql files (SPARQL CONSTRUCT rules)
    rule_files = list(rules_dir.glob("*.sparql"))
    print(f"\n📋 Found {len(rule_files)} reasoning rule files")
    
    loaded_count = 0
    for rule_file in rule_files:
        try:
            with open(rule_file, 'r') as f:
                sparql_query = f.read()
            
            # Execute CONSTRUCT query to materialize inferences
            # Store results in a rules graph
            graph_uri = f"http://procurement.kg/rules#{rule_file.stem}"
            
            # For now, just load the rule definition as metadata
            # Actual rule execution would need Jena reasoner
            rule_metadata = f"""
@prefix rule: <http://procurement.kg/rules#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

<{graph_uri}> a rule:ReasoningRule ;
    rdfs:label "{rule_file.stem}" ;
    rule:sparqlQuery \"\"\"
{sparql_query}
\"\"\" .
"""
            
            success = client.load_turtle(rule_metadata, graph_uri=graph_uri)
            
            if success:
                loaded_count += 1
                print(f"  ✓ Loaded: {rule_file.name}")
            else:
                print(f"  ✗ Failed: {rule_file.name}")
        except Exception as e:
            print(f"  ✗ Error loading {rule_file.name}: {e}")
    
    print(f"\n✅ Loaded {loaded_count}/{len(rule_files)} reasoning rules")
    return loaded_count


async def main():
    """Main function."""
    print("=" * 60)
    print("LOADING SHACL SHAPES AND REASONING RULES")
    print("=" * 60)
    
    shacl_count = await load_shacl_shapes()
    rules_count = await load_reasoning_rules()
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"SHACL shapes loaded: {shacl_count}")
    print(f"Reasoning rules loaded: {rules_count}")
    print(f"Total artifacts loaded: {shacl_count + rules_count}")
    print("\n✅ Loading complete!")


if __name__ == "__main__":
    asyncio.run(main())

# Made with Bob
