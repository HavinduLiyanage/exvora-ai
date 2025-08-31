#!/usr/bin/env python3
"""Benchmark script for Exvora AI API latency."""

import time
import statistics
import os
import sys
from typing import List, Dict, Any

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import requests

def benchmark_endpoint(url: str, request_data: Dict[str, Any], iterations: int = 10) -> Dict[str, Any]:
    """Benchmark an endpoint and return latency statistics."""
    latencies = []
    
    print(f"Benchmarking {url} with {iterations} iterations...")
    
    for i in range(iterations):
        start_time = time.time()
        try:
            response = requests.post(url, json=request_data, timeout=30)
            response.raise_for_status()
            latency = (time.time() - start_time) * 1000  # Convert to milliseconds
            latencies.append(latency)
            print(f"  Request {i+1}: {latency:.1f}ms")
        except Exception as e:
            print(f"  Request {i+1}: Failed - {e}")
    
    if not latencies:
        return {"error": "All requests failed"}
    
    return {
        "count": len(latencies),
        "p50": statistics.median(latencies),
        "p95": statistics.quantiles(latencies, n=20)[18],  # 95th percentile
        "mean": statistics.mean(latencies),
        "min": min(latencies),
        "max": max(latencies)
    }

def main():
    """Run latency benchmarks."""
    base_url = os.getenv("EXVORA_API_URL", "http://localhost:8000")
    
    # Sample request data
    request_data = {
        "trip_context": {
            "date_range": {
                "start": "2025-09-10",
                "end": "2025-09-12"
            },
            "day_template": {
                "start": "09:00",
                "end": "18:00",
                "pace": "moderate"
            },
            "base_place_id": "colombo_fort",
            "modes": ["DRIVE", "WALK"]
        },
        "preferences": {
            "themes": ["culture", "history"],
            "avoid_tags": ["crowded"]
        },
        "constraints": {
            "daily_budget_cap": 100,
            "max_transfer_minutes": 30
        },
        "locks": []
    }
    
    print("Exvora AI API Latency Benchmark")
    print("=" * 40)
    print(f"Base URL: {base_url}")
    print()
    
    # Test with heuristic transfers (default)
    print("1. Heuristic Transfers (USE_GOOGLE_ROUTES=false)")
    heuristic_results = benchmark_endpoint(f"{base_url}/v1/itinerary", request_data)
    
    if "error" not in heuristic_results:
        print(f"   P50: {heuristic_results['p50']:.1f}ms")
        print(f"   P95: {heuristic_results['p95']:.1f}ms")
        print(f"   Mean: {heuristic_results['mean']:.1f}ms")
        print(f"   Range: {heuristic_results['min']:.1f}ms - {heuristic_results['max']:.1f}ms")
    else:
        print(f"   Error: {heuristic_results['error']}")
    
    print()
    
    # Test with Google Routes if enabled
    if os.getenv("USE_GOOGLE_ROUTES") == "true" and os.getenv("GOOGLE_MAPS_API_KEY"):
        print("2. Google Routes (USE_GOOGLE_ROUTES=true)")
        google_results = benchmark_endpoint(f"{base_url}/v1/itinerary", request_data)
        
        if "error" not in google_results:
            print(f"   P50: {google_results['p50']:.1f}ms")
            print(f"   P95: {google_results['p95']:.1f}ms")
            print(f"   Mean: {google_results['mean']:.1f}ms")
            print(f"   Range: {google_results['min']:.1f}ms - {google_results['max']:.1f}ms")
        else:
            print(f"   Error: {google_results['error']}")
        
        print()
        
        # Comparison table
        if "error" not in heuristic_results and "error" not in google_results:
            print("Comparison:")
            print(f"{'Metric':<10} {'Heuristic':<12} {'Google':<12} {'Diff':<10}")
            print("-" * 44)
            print(f"{'P50':<10} {heuristic_results['p50']:<12.1f} {google_results['p50']:<12.1f} {google_results['p50'] - heuristic_results['p50']:<+10.1f}")
            print(f"{'P95':<10} {heuristic_results['p95']:<12.1f} {google_results['p95']:<12.1f} {google_results['p95'] - heuristic_results['p95']:<+10.1f}")
            print(f"{'Mean':<10} {heuristic_results['mean']:<12.1f} {google_results['mean']:<12.1f} {google_results['mean'] - heuristic_results['mean']:<+10.1f}")
    
    # Save results to docs/qa/latency.md
    os.makedirs("docs/qa", exist_ok=True)
    
    with open("docs/qa/latency.md", "w") as f:
        f.write("# Exvora AI API Latency Benchmark Results\n\n")
        f.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}\n\n")
        f.write(f"Base URL: {base_url}\n\n")
        
        f.write("## Heuristic Transfers\n\n")
        if "error" not in heuristic_results:
            f.write(f"- P50: {heuristic_results['p50']:.1f}ms\n")
            f.write(f"- P95: {heuristic_results['p95']:.1f}ms\n")
            f.write(f"- Mean: {heuristic_results['mean']:.1f}ms\n")
            f.write(f"- Range: {heuristic_results['min']:.1f}ms - {heuristic_results['max']:.1f}ms\n")
        else:
            f.write(f"- Error: {heuristic_results['error']}\n")
        
        if os.getenv("USE_GOOGLE_ROUTES") == "true" and os.getenv("GOOGLE_MAPS_API_KEY"):
            f.write("\n## Google Routes\n\n")
            if "error" not in google_results:
                f.write(f"- P50: {google_results['p50']:.1f}ms\n")
                f.write(f"- P95: {google_results['p95']:.1f}ms\n")
                f.write(f"- Mean: {google_results['mean']:.1f}ms\n")
                f.write(f"- Range: {google_results['min']:.1f}ms - {google_results['max']:.1f}ms\n")
            else:
                f.write(f"- Error: {google_results['error']}\n")
    
    print(f"\nResults saved to docs/qa/latency.md")

if __name__ == "__main__":
    main()
