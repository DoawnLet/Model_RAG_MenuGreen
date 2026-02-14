"""
Menu Green API - Test Script
Run tests against the Menu Green API to verify functionality
"""

import requests
import json
from typing import Dict, Any

BASE_URL = "http://localhost:8000"

def print_response(test_name: str, response: requests.Response):
    """Pretty print test response"""
    print(f"\n{'='*60}")
    print(f"TEST: {test_name}")
    print(f"{'='*60}")
    print(f"Status Code: {response.status_code}")
    print(f"Response:")
    try:
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    except:
        print(response.text)
    print(f"{'='*60}\n")

def test_1_simple_chat():
    """Test chat với message đơn giản"""
    response = requests.post(
        f"{BASE_URL}/chat",
        json={
            "message": "Hôm nay tôi muốn ăn đồ ăn nhẹ"
        }
    )
    print_response("1. Simple Chat (Anonymous)", response)
    return response

def test_2_chat_with_valid_uuid():
    """Test chat với user_id hợp lệ (UUID format)"""
    response = requests.post(
        f"{BASE_URL}/chat",
        json={
            "message": "Tìm món ăn với trứng và thịt gà",
            "user_id": "550e8400-e29b-41d4-a716-446655440000"
        }
    )
    print_response("2. Chat with Valid User ID", response)
    return response

def test_3_chat_with_invalid_uuid():
    """Test chat với user_id không hợp lệ (vẫn hoạt động)"""
    response = requests.post(
        f"{BASE_URL}/chat",
        json={
            "message": "Tôi muốn ăn món Việt",
            "user_id": "user_123"
        }
    )
    print_response("3. Chat with Invalid User ID (Fallback)", response)
    return response

def test_4_chat_with_thread():
    """Test chat với thread_id"""
    response = requests.post(
        f"{BASE_URL}/chat",
        json={
            "message": "Tìm món chay",
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
            "thread_id": "test_thread_001"
        }
    )
    print_response("4. Chat with Thread ID", response)
    return response

def test_5_chat_with_history():
    """Test chat với conversation history"""
    response = requests.post(
        f"{BASE_URL}/chat",
        json={
            "message": "Vậy món gỏi cuốn thì sao?",
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
            "thread_id": "test_thread_002",
            "conversation_history": [
                {
                    "role": "user",
                    "content": "Tôi muốn tìm món ăn nhẹ"
                },
                {
                    "role": "assistant",
                    "content": "Bạn có thể thử các món như: nem rán, chả giò, bánh bao, hoặc gỏi cuốn. Bạn thích món nào?"
                }
            ]
        }
    )
    print_response("5. Chat with Conversation History", response)
    return response

def test_6_recipe_search():
    """Test tìm kiếm công thức"""
    response = requests.post(
        f"{BASE_URL}/chat",
        json={
            "message": "Tìm công thức món phở bò"
        }
    )
    print_response("6. Recipe Search", response)
    return response

def test_7_meal_planning():
    """Test meal planning (cần user profile)"""
    response = requests.post(
        f"{BASE_URL}/chat",
        json={
            "message": "Lập kế hoạch ăn uống 7 ngày cho tôi",
            "user_id": "550e8400-e29b-41d4-a716-446655440000"
        }
    )
    print_response("7. Meal Planning", response)
    return response

def test_8_nutrition_advice():
    """Test nutrition advice"""
    response = requests.post(
        f"{BASE_URL}/chat",
        json={
            "message": "Tôi cần ăn bao nhiêu protein mỗi ngày?",
            "user_id": "550e8400-e29b-41d4-a716-446655440000"
        }
    )
    print_response("8. Nutrition Advice", response)
    return response

def test_9_health_check():
    """Test health check endpoint"""
    response = requests.get(f"{BASE_URL}/health")
    print_response("9. Health Check", response)
    return response

def test_10_db_health():
    """Test database health check"""
    response = requests.get(f"{BASE_URL}/health/db")
    print_response("10. Database Health Check", response)
    return response

def test_11_streaming():
    """Test streaming endpoint"""
    print(f"\n{'='*60}")
    print(f"TEST: 11. Streaming Chat")
    print(f"{'='*60}")
    
    response = requests.post(
        f"{BASE_URL}/chat/stream",
        json={
            "message": "Lập kế hoạch ăn uống 3 ngày",
            "user_id": "550e8400-e29b-41d4-a716-446655440000"
        },
        stream=True
    )
    
    print(f"Status Code: {response.status_code}")
    print("Streaming events:")
    
    for line in response.iter_lines():
        if line:
            decoded = line.decode('utf-8')
            if decoded.startswith('data: '):
                try:
                    data = json.loads(decoded[6:])
                    print(f"  → {json.dumps(data, ensure_ascii=False)}")
                except:
                    print(f"  → {decoded}")
    
    print(f"{'='*60}\n")
    return response

def test_error_missing_message():
    """Test error case: missing message"""
    try:
        response = requests.post(
            f"{BASE_URL}/chat",
            json={
                "user_id": "550e8400-e29b-41d4-a716-446655440000"
            }
        )
        print_response("ERROR TEST: Missing Message", response)
        return response
    except Exception as e:
        print(f"Exception: {e}")

def run_all_tests():
    """Run all test cases"""
    print("\n" + "🚀" * 30)
    print("MENU GREEN API - AUTOMATED TESTS")
    print("🚀" * 30)
    
    results = []
    
    # Basic tests
    print("\n📝 BASIC TESTS")
    results.append(("Simple Chat", test_1_simple_chat()))
    results.append(("Valid UUID", test_2_chat_with_valid_uuid()))
    results.append(("Invalid UUID", test_3_chat_with_invalid_uuid()))
    results.append(("With Thread", test_4_chat_with_thread()))
    results.append(("With History", test_5_chat_with_history()))
    
    # Intent-based tests
    print("\n🎯 INTENT-BASED TESTS")
    results.append(("Recipe Search", test_6_recipe_search()))
    results.append(("Meal Planning", test_7_meal_planning()))
    results.append(("Nutrition Advice", test_8_nutrition_advice()))
    
    # Health checks
    print("\n💚 HEALTH CHECKS")
    results.append(("Health Check", test_9_health_check()))
    results.append(("DB Health", test_10_db_health()))
    
    # Streaming
    print("\n📡 STREAMING TEST")
    results.append(("Streaming", test_11_streaming()))
    
    # Error cases
    print("\n❌ ERROR TESTS")
    results.append(("Missing Message", test_error_missing_message()))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for test_name, response in results:
        if response and 200 <= response.status_code < 300:
            print(f"✅ {test_name}: PASSED (Status {response.status_code})")
            passed += 1
        elif response and response.status_code == 422:
            print(f"⚠️  {test_name}: EXPECTED ERROR (Status {response.status_code})")
        else:
            status = response.status_code if response else "N/A"
            print(f"❌ {test_name}: FAILED (Status {status})")
            failed += 1
    
    print(f"\n📊 Total: {passed + failed} tests")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print("=" * 60 + "\n")

def run_quick_test():
    """Run a quick smoke test"""
    print("\n🔥 QUICK SMOKE TEST")
    
    # Test 1: Health
    health = requests.get(f"{BASE_URL}/health")
    print(f"1. Health: {health.status_code} {'✅' if health.status_code == 200 else '❌'}")
    
    # Test 2: Simple chat
    chat = requests.post(
        f"{BASE_URL}/chat",
        json={"message": "Xin chào"}
    )
    print(f"2. Chat: {chat.status_code} {'✅' if chat.status_code == 200 else '❌'}")
    
    # Test 3: Metrics
    metrics = requests.get(f"{BASE_URL}/metrics")
    print(f"3. Metrics: {metrics.status_code} {'✅' if metrics.status_code == 200 else '❌'}")
    
    if all(r.status_code == 200 for r in [health, chat, metrics]):
        print("\n✅ API IS HEALTHY AND READY!")
    else:
        print("\n❌ API HAS ISSUES!")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "quick":
        run_quick_test()
    else:
        run_all_tests()
