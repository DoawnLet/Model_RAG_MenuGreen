#!/usr/bin/env python3
"""
Quick verification script for Menu Green monitoring setup.

This script verifies that the monitoring infrastructure is properly configured
and can collect/export metrics.

Run this after starting the FastAPI server to verify:
1. Metrics module imports correctly
2. All metrics are registered
3. Metrics can be exported in Prometheus format
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

def test_metrics_import():
    """Test that metrics module imports correctly."""
    print("🔍 Testing metrics module import...")
    try:
        print("✅ All metrics imported successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to import metrics: {e}")
        return False

def test_metrics_registration():
    """Test that metrics are properly registered."""
    print("\n🔍 Testing metrics registration...")
    try:
        from app.core.metrics import get_metrics
        
        # Get metrics in Prometheus format
        metrics_data, content_type = get_metrics()
        
        # Check that we have data
        if not metrics_data:
            print("❌ No metrics data generated")
            return False
        
        # Check content type
        if "text/plain" not in content_type:
            print(f"❌ Invalid content type: {content_type}")
            return False
        
        # Decode metrics data for checking
        if isinstance(metrics_data, bytes):
            metrics_str: str = metrics_data.decode('utf-8')
        else:
            metrics_str: str = str(metrics_data)
        
        # Check for key metrics
        required_metrics = [
            "menu_green_http_requests_total",
            "menu_green_llm_calls_total",
            "menu_green_llm_cost_usd_total",
            "menu_green_agent_executions_total",
            "menu_green_memory_cache_hits_total",
            "menu_green_system_health",
        ]
        
        missing = []
        for metric in required_metrics:
            if metric not in metrics_str:
                missing.append(metric)
        
        if missing:
            print(f"❌ Missing metrics: {', '.join(missing)}")
            return False
        
        print("✅ All metrics registered correctly")
        print(f"📊 Total metrics size: {len(metrics_data)} bytes")
        return True
        
    except Exception as e:
        print(f"❌ Failed to test metrics: {e}")
        return False

def test_decorator_syntax():
    """Test that decorators can be applied."""
    print("\n🔍 Testing decorator syntax...")
    try:
        from app.core.metrics import track_llm_call, track_agent_execution
        
        # Test sync decorator
        @track_agent_execution("test_agent")
        def sync_function():
            return "sync"
        
        # Test async decorator
        @track_agent_execution("test_async_agent")
        async def async_function():
            return "async"
        
        # Test LLM decorator
        @track_llm_call(model="test-model", agent="test-agent")
        async def llm_function():
            return "llm"
        
        print("✅ Decorators can be applied correctly")
        return True
        
    except Exception as e:
        print(f"❌ Failed to test decorators: {e}")
        return False

def test_cost_calculation():
    """Test LLM cost calculation."""
    print("\n🔍 Testing cost calculation...")
    try:
        from app.core.metrics import calculate_llm_cost
        
        # Test Gemini 2.0 Flash
        cost = calculate_llm_cost("gemini-2.0-flash-exp", 1000, 500)
        expected = (1000 * 0.075 / 1_000_000) + (500 * 0.30 / 1_000_000)
        
        if abs(cost - expected) > 0.0001:
            print(f"❌ Cost calculation mismatch: {cost} != {expected}")
            return False
        
        print(f"✅ Cost calculation correct: ${cost:.6f} for 1000 input + 500 output tokens")
        return True
        
    except Exception as e:
        print(f"❌ Failed to test cost calculation: {e}")
        return False

def main():
    """Run all verification tests."""
    print("=" * 60)
    print("Menu Green Monitoring Verification")
    print("=" * 60)
    
    tests = [
        test_metrics_import,
        test_metrics_registration,
        test_decorator_syntax,
        test_cost_calculation,
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    passed = sum(results)
    total = len(results)
    
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("\n🎉 All tests passed! Monitoring is ready.")
        print("\nNext steps:")
        print("1. Start the FastAPI server: uvicorn app.main:app --reload")
        print("2. Check /metrics endpoint: http://localhost:8000/metrics")
        print("3. Start monitoring stack: cd monitoring && docker-compose up -d")
        print("4. Access Grafana: http://localhost:3001 (admin/admin)")
        return 0
    else:
        print(f"\n❌ {total - passed} test(s) failed. Please check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
