#!/usr/bin/env python3
"""
Test script to verify LLM provider abstraction layer.

This script tests:
1. Provider factory can create providers
2. Ollama provider works correctly
3. BaseAgent can use the provider abstraction
"""

import sys
from pathlib import Path

# Add agents/src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "agents" / "src"))

from config import get_settings
from llm.provider_factory import LLMProviderFactory
from agents.shared.base import BaseAgent


def test_provider_factory():
    """Test that provider factory works."""
    print("=" * 70)
    print("Testing LLM Provider Factory")
    print("=" * 70)
    
    # List available providers
    providers = LLMProviderFactory.list_providers()
    print(f"\n✅ Available providers: {providers}")
    
    # Test creating Ollama provider
    try:
        ollama_provider = LLMProviderFactory.create_provider("ollama")
        print(f"✅ Created Ollama provider: {ollama_provider.name}")
        print(f"   Capabilities: {ollama_provider.get_capabilities()}")
    except Exception as e:
        print(f"❌ Failed to create Ollama provider: {e}")
        return False
    
    # Test creating WatsonX provider
    try:
        watsonx_provider = LLMProviderFactory.create_provider("watsonx")
        print(f"✅ Created WatsonX provider: {watsonx_provider.name}")
        print(f"   Capabilities: {watsonx_provider.get_capabilities()}")
    except Exception as e:
        print(f"❌ Failed to create WatsonX provider: {e}")
        return False
    
    # Test invalid provider
    try:
        LLMProviderFactory.create_provider("invalid")
        print("❌ Should have raised ValueError for invalid provider")
        return False
    except ValueError:
        print("✅ Correctly raised ValueError for invalid provider")
    
    return True


def test_ollama_provider():
    """Test Ollama provider configuration validation."""
    print("\n" + "=" * 70)
    print("Testing Ollama Provider Configuration")
    print("=" * 70)
    
    settings = get_settings()
    provider = LLMProviderFactory.create_provider("ollama")
    
    # Validate configuration
    is_valid = provider.validate_config(settings)
    print(f"\n✅ Configuration valid: {is_valid}")
    
    if is_valid:
        print(f"   Ollama URL: {settings.ollama_base_url}")
        print(f"   Model: {settings.ollama_model}")
    
    return is_valid


def test_base_agent():
    """Test that BaseAgent can create LLM using provider abstraction."""
    print("\n" + "=" * 70)
    print("Testing BaseAgent LLM Creation")
    print("=" * 70)
    
    settings = get_settings()
    
    # Ensure we're using Ollama
    if settings.llm_provider.lower() != "ollama":
        print(f"⚠️  Warning: LLM provider is '{settings.llm_provider}', not 'ollama'")
        print("   Setting to 'ollama' for test...")
        settings.llm_provider = "ollama"
    
    try:
        # Use an actual agent (ClauseExtractionAgent) to test
        from agents.ingestion.clause_extraction import (
            ClauseExtractionAgent,
        )
        
        agent = ClauseExtractionAgent(settings=settings)
        print(f"\n✅ Agent created successfully using provider abstraction")
        print(f"   Agent type: {agent.__class__.__name__}")
        print(f"   LLM type: {type(agent.llm).__name__}")
        print(f"   Provider: {settings.llm_provider}")
        
        return True
    except Exception as e:
        print(f"\n❌ Failed to create agent: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("LLM Provider Abstraction Layer - Test Suite")
    print("=" * 70)
    
    results = []
    
    # Test 1: Provider Factory
    results.append(("Provider Factory", test_provider_factory()))
    
    # Test 2: Ollama Provider
    results.append(("Ollama Provider", test_ollama_provider()))
    
    # Test 3: BaseAgent Integration
    results.append(("BaseAgent Integration", test_base_agent()))
    
    # Summary
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    all_passed = all(result[1] for result in results)
    
    if all_passed:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print("\n⚠️  Some tests failed. Check output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
