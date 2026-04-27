#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Async Integration Example

Demonstrates how to use async LLM cache and retry modules together
for optimal performance in asyncio applications.

This example shows:
- Async cache integration
- Async retry with fallback
- Combined usage patterns
- Performance monitoring
"""

import asyncio
import logging
import time
from typing import Optional

from llm_cache_async import get_async_llm_cache
from llm_retry_async import async_retry_with_fallback, get_async_retry_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Simulated async LLM API calls
async def mock_openai_api(prompt: str, model: str = "gpt-4") -> str:
    """Simulate OpenAI API call"""
    await asyncio.sleep(0.1)  # Simulate network latency
    return f"OpenAI {model} response to: {prompt}"


async def mock_anthropic_api(prompt: str, model: str = "claude-3") -> str:
    """Simulate Anthropic API call"""
    await asyncio.sleep(0.1)
    return f"Anthropic {model} response to: {prompt}"


# Example 1: Basic async cache usage
async def example_basic_cache():
    """Example: Basic async cache usage"""
    print("\n=== Example 1: Basic Async Cache ===")
    
    cache = get_async_llm_cache()
    prompt = "What is Python?"
    
    # First call - cache miss
    start = time.time()
    cached = await cache.get(prompt, "openai", "gpt-4")
    if not cached:
        response = await mock_openai_api(prompt)
        await cache.set(prompt, response, "openai", "gpt-4")
        print(f"Cache miss - API called ({time.time() - start:.3f}s)")
    
    # Second call - cache hit
    start = time.time()
    cached = await cache.get(prompt, "openai", "gpt-4")
    print(f"Cache hit - Response: {cached[:50]}... ({time.time() - start:.3f}s)")
    
    # Print stats
    stats = cache.get_stats()
    print(f"Cache stats: {stats['hits']} hits, {stats['misses']} misses, {stats['hit_rate']:.1%} hit rate")


# Example 2: Async retry with fallback
async def example_retry_fallback():
    """Example: Async retry with fallback"""
    print("\n=== Example 2: Async Retry with Fallback ===")
    
    call_count = {"count": 0}
    
    @async_retry_with_fallback(
        max_retries=3,
        initial_delay=0.1,
        fallback_backends=["anthropic"]
    )
    async def call_llm(prompt: str, backend: str = "openai"):
        call_count["count"] += 1
        print(f"  Attempt {call_count['count']}: Calling {backend}")
        
        # Simulate failure on first 2 attempts with openai
        if backend == "openai" and call_count["count"] < 3:
            raise Exception("503 Service Unavailable")
        
        if backend == "openai":
            return await mock_openai_api(prompt)
        else:
            return await mock_anthropic_api(prompt)
    
    try:
        result = await call_llm("Hello, world!")
        print(f"Success: {result}")
    except Exception as e:
        print(f"Failed: {e}")
    
    # Print stats
    manager = get_async_retry_manager()
    stats = manager.get_stats()
    print(f"Retry stats: {stats['retries']} retries, {stats['fallbacks']} fallbacks")


# Example 3: Combined cache + retry
async def example_combined():
    """Example: Combined cache and retry"""
    print("\n=== Example 3: Combined Cache + Retry ===")
    
    cache = get_async_llm_cache()
    
    @async_retry_with_fallback(
        max_retries=2,
        initial_delay=0.1,
        fallback_backends=["anthropic"]
    )
    async def cached_llm_call(prompt: str, backend: str = "openai", model: str = "gpt-4"):
        # Try cache first
        cached = await cache.get(prompt, backend, model)
        if cached:
            print(f"  Cache hit for {backend}")
            return cached
        
        # Cache miss - call API
        print(f"  Cache miss - calling {backend} API")
        if backend == "openai":
            response = await mock_openai_api(prompt, model)
        else:
            response = await mock_anthropic_api(prompt, model)
        
        # Save to cache
        await cache.set(prompt, response, backend, model)
        return response
    
    # First call - cache miss, API call
    result1 = await cached_llm_call("What is async/await?")
    print(f"Result 1: {result1[:50]}...")
    
    # Second call - cache hit, no API call
    result2 = await cached_llm_call("What is async/await?")
    print(f"Result 2: {result2[:50]}...")
    
    # Print combined stats
    cache_stats = cache.get_stats()
    retry_stats = get_async_retry_manager().get_stats()
    print(f"\nCache: {cache_stats['hit_rate']:.1%} hit rate")
    print(f"Retry: {retry_stats['successful_calls']}/{retry_stats['total_calls']} successful")


# Example 4: Concurrent requests
async def example_concurrent():
    """Example: Concurrent async requests"""
    print("\n=== Example 4: Concurrent Requests ===")
    
    cache = get_async_llm_cache()
    
    @async_retry_with_fallback(max_retries=2, initial_delay=0.1)
    async def cached_call(prompt: str, backend: str = "openai"):
        cached = await cache.get(prompt, backend, "gpt-4")
        if cached:
            return cached
        
        response = await mock_openai_api(prompt)
        await cache.set(prompt, response, backend, "gpt-4")
        return response
    
    # Make multiple concurrent requests
    prompts = [
        "What is Python?",
        "What is JavaScript?",
        "What is Rust?",
        "What is Python?",  # Duplicate - should hit cache
        "What is Go?"
    ]
    
    start = time.time()
    results = await asyncio.gather(*[cached_call(p) for p in prompts])
    elapsed = time.time() - start
    
    print(f"Processed {len(prompts)} requests in {elapsed:.3f}s")
    print(f"Average: {elapsed/len(prompts):.3f}s per request")
    
    # Print stats
    stats = cache.get_stats()
    print(f"Cache: {stats['hits']} hits, {stats['misses']} misses")


# Example 5: Error handling and circuit breaker
async def example_circuit_breaker():
    """Example: Circuit breaker in action"""
    print("\n=== Example 5: Circuit Breaker ===")
    
    failure_count = {"count": 0}
    
    @async_retry_with_fallback(
        max_retries=1,
        initial_delay=0.05,
        fallback_backends=["anthropic"]
    )
    async def unreliable_call(prompt: str, backend: str = "openai"):
        failure_count["count"] += 1
        
        # Simulate consistent failures to trigger circuit breaker
        if backend == "openai" and failure_count["count"] <= 6:
            raise Exception("503 Service Unavailable")
        
        if backend == "openai":
            return await mock_openai_api(prompt)
        else:
            return await mock_anthropic_api(prompt)
    
    # Make multiple calls to trigger circuit breaker
    for i in range(8):
        try:
            result = await unreliable_call(f"Request {i+1}")
            print(f"  Request {i+1}: Success - {result[:40]}...")
        except Exception as e:
            print(f"  Request {i+1}: Failed - {str(e)[:40]}...")
        
        await asyncio.sleep(0.05)
    
    # Print circuit breaker stats
    manager = get_async_retry_manager()
    stats = manager.get_stats()
    print(f"\nCircuit breaker trips: {stats['circuit_breaker_trips']}")
    print(f"Fallbacks: {stats['fallbacks']}")


# Main example runner
async def main():
    """Run all examples"""
    print("=" * 60)
    print("Async LLM Optimization Examples")
    print("=" * 60)
    
    await example_basic_cache()
    await asyncio.sleep(0.5)
    
    await example_retry_fallback()
    await asyncio.sleep(0.5)
    
    await example_combined()
    await asyncio.sleep(0.5)
    
    await example_concurrent()
    await asyncio.sleep(0.5)
    
    await example_circuit_breaker()
    
    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
