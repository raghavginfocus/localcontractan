#!/usr/bin/env python3
"""
Quick test script to verify rule generation fix.
"""

import asyncio
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent / "agents" / "src"))

from agents.schema_evolution.rule_generator import RuleGeneratorAgent, RulePattern
from config import get_settings


async def test_rule_generation():
    """Test rule generation with a simple pattern."""
    print("=" * 70)
    print("  🧪 TESTING RULE GENERATION FIX")
    print("=" * 70)
    
    settings = get_settings()
    print(f"\n  🤖 Using LLM: {settings.llm_provider} ({settings.ollama_model})")
    
    # Create agent
    agent = RuleGeneratorAgent(settings=settings)
    
    # Create a simple test pattern
    pattern = RulePattern(
        pattern_name="TestHighTerminationRisk",
        condition_class="proc:TerminationClause",
        condition_property="proc:noticePeriod",
        condition_operator="lessThan",
        condition_value=30,
        inferred_property="proc:hasRiskLevel",
        inferred_value="proc:HighTerminationRisk",
        description="Test rule: High termination risk when notice period < 30 days",
    )
    
    print(f"\n  📋 Test Pattern:")
    print(f"     Name: {pattern.pattern_name}")
    print(f"     Condition: {pattern.condition_class} has {pattern.condition_property} {pattern.condition_operator} {pattern.condition_value}")
    print(f"     Result: Add {pattern.inferred_property} = {pattern.inferred_value}")
    
    print(f"\n  ⏳ Generating rule...")
    
    try:
        result = await agent.process(pattern)
        
        if result.error:
            print(f"\n  ❌ ERROR: {result.error}")
            return False
        
        if result.is_valid:
            print(f"\n  ✅ SUCCESS! Rule generated and validated")
            print(f"\n  📄 Generated Jena Rule:")
            print(f"     {result.rule_text[:200]}...")
            print(f"\n  📄 Generated SPARQL:")
            print(f"     {result.sparql_equivalent[:200]}...")
            if result.file_path:
                print(f"\n  💾 Rule saved to: {result.file_path}")
            return True
        else:
            print(f"\n  ⚠️  Rule generated but validation failed")
            print(f"     Jena Rule: {result.rule_text[:100]}...")
            print(f"     SPARQL: {result.sparql_equivalent[:100]}...")
            return False
            
    except Exception as e:
        print(f"\n  ❌ EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_rule_generation())
    print("\n" + "=" * 70)
    if success:
        print("  ✅ TEST PASSED - Rule generation fix verified!")
    else:
        print("  ❌ TEST FAILED - Rule generation still has issues")
    print("=" * 70)
    sys.exit(0 if success else 1)
