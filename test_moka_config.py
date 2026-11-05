#!/usr/bin/env python3
"""Quick test script for Moka LLM configuration."""

import json
import sys
from scripts.collaboration.llm_backend import create_backend

def test_moka_connection():
    """Test Moka LLM connection with config from moka_ai.json"""
    
    # Load config
    try:
        with open('moka_ai.json') as f:
            config = json.load(f)
    except Exception as e:
        print(f"❌ Failed to load moka_ai.json: {e}")
        return False
    
    print("=" * 60)
    print("🧪 Testing Moka LLM Configuration")
    print("=" * 60)
    print(f"URL:   {config['url']}")
    print(f"Model: {config['model']}")
    print(f"Key:   {config['key'][:10]}...{config['key'][-10:]}")
    print()
    
    # Create backend
    try:
        backend = create_backend(
            'moka',
            api_key=config['key'],
            base_url=config['url'],
            model=config['model']
        )
        print("✅ Backend created successfully")
    except Exception as e:
        print(f"❌ Failed to create backend: {e}")
        return False
    
    # Test is_available()
    try:
        available = backend.is_available()
        if available:
            print("✅ Backend.is_available() = True")
        else:
            print("⚠️  Backend.is_available() = False")
            return False
    except Exception as e:
        print(f"❌ is_available() failed: {e}")
        return False
    
    # Test simple generation
    try:
        print("\n🔄 Testing simple generation...")
        response = backend.generate(
            "Say 'Connection test successful' in one sentence.",
            max_tokens=50
        )
        print(f"✅ Generation successful!")
        print(f"Response: {response}")
    except Exception as e:
        print(f"❌ Generation failed: {e}")
        return False
    
    # Test streaming
    try:
        print("\n🔄 Testing streaming generation...")
        chunks = list(backend.generate_stream(
            "Count from 1 to 3, one number per word.",
            max_tokens=30
        ))
        print(f"✅ Streaming successful! Received {len(chunks)} chunks")
        print(f"Full response: {''.join(chunks)}")
    except Exception as e:
        print(f"❌ Streaming failed: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("✅ All Moka LLM tests passed!")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = test_moka_connection()
    sys.exit(0 if success else 1)
