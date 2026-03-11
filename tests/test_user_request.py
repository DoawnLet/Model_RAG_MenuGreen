"""Quick test với mẫu request của user"""
import requests
import json

response = requests.post(
    "http://localhost:8000/chat",
    json={
        "message": "Hôm nay tôi muốn ăn đồ ăn nhẹ",
        "user_id": "550e8400-e29b-41d4-a716-446655440000",
        "thread_id": "string",
        "conversation_history": []
    }
)

print(f"Status: {response.status_code}")
print("\nResponse:")
print(json.dumps(response.json(), indent=2, ensure_ascii=False))
