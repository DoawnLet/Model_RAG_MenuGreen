# Menu Green API - Test Examples

## 1. Test đơn giản (Chỉ message)

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  --data-raw '{
    "message": "Hôm nay tôi muốn ăn đồ ăn nhẹ"
  }'
```

**JSON Body:**

```json
{
  "message": "Hôm nay tôi muốn ăn đồ ăn nhẹ"
}
```

---

## 2. Test với user_id hợp lệ (UUID format)

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  --data-raw '{
    "message": "Hôm nay tôi muốn ăn đồ ăn nhẹ",
    "user_id": "550e8400-e29b-41d4-a716-446655440000"
  }'
```

**JSON Body:**

```json
{
  "message": "Hôm nay tôi muốn ăn đồ ăn nhẹ",
  "user_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

## 3. Test với thread_id (để lưu conversation)

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  --data-raw '{
    "message": "Hôm nay tôi muốn ăn đồ ăn nhẹ",
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "thread_id": "conversation_001"
  }'
```

**JSON Body:**

```json
{
  "message": "Hôm nay tôi muốn ăn đồ ăn nhẹ",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "thread_id": "conversation_001"
}
```

---

## 4. Test với conversation history

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  --data-raw '{
    "message": "Vậy món gỏi cuốn thì sao?",
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "thread_id": "conversation_001",
    "conversation_history": [
      {
        "role": "user",
        "content": "Tôi muốn tìm món ăn nhẹ"
      },
      {
        "role": "assistant",
        "content": "Bạn có thể thử các món như: nem rán, chả giò, hoặc bánh bao. Bạn thích món nào?"
      }
    ]
  }'
```

**JSON Body:**

```json
{
  "message": "Vậy món gỏi cuốn thì sao?",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "thread_id": "conversation_001",
  "conversation_history": [
    {
      "role": "user",
      "content": "Tôi muốn tìm món ăn nhẹ"
    },
    {
      "role": "assistant",
      "content": "Bạn có thể thử các món như: nem rán, chả giò, hoặc bánh bao. Bạn thích món nào?"
    }
  ]
}
```

---

## 5. Test tìm kiếm recipes

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  --data-raw '{
    "message": "Tìm món ăn với trứng và thịt gà",
    "user_id": "550e8400-e29b-41d4-a716-446655440000"
  }'
```

**JSON Body:**

```json
{
  "message": "Tìm món ăn với trứng và thịt gà",
  "user_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

## 6. Test meal planning (cần user profile)

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  --data-raw '{
    "message": "Lập kế hoạch ăn uống 7 ngày cho tôi",
    "user_id": "550e8400-e29b-41d4-a716-446655440000"
  }'
```

**JSON Body:**

```json
{
  "message": "Lập kế hoạch ăn uống 7 ngày cho tôi",
  "user_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

## 7. Test với invalid user_id (vẫn hoạt động)

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  --data-raw '{
    "message": "Hôm nay tôi muốn ăn đồ ăn nhẹ",
    "user_id": "user_123"
  }'
```

**JSON Body:**

```json
{
  "message": "Hôm nay tôi muốn ăn đồ ăn nhẹ",
  "user_id": "user_123"
}
```

**Lưu ý:** API sẽ tự động fallback thành anonymous user nếu user_id không hợp lệ.

---

## 8. Test streaming endpoint

```bash
curl -N -X POST http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  --data-raw '{
    "message": "Lập kế hoạch ăn uống 7 ngày",
    "user_id": "550e8400-e29b-41d4-a716-446655440000"
  }'
```

**JSON Body:**

```json
{
  "message": "Lập kế hoạch ăn uống 7 ngày",
  "user_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Output format (Server-Sent Events):**

```
data: {"node":"classify_intent","content":"Đang phân tích yêu cầu..."}

data: {"node":"meal_planning_agent","content":"✅Step 1/5: Đã phân tích dinh dưỡng..."}

data: {"node":"meal_planning_agent","content":"✅Step 2/5: Đã tìm thấy 25 công thức..."}

data: {"done":true}
```

---

## Test Cases theo Intent

### Intent: recipe_search

```json
{
  "message": "Tìm công thức món pasta carbonara"
}
```

### Intent: meal_planning

```json
{
  "message": "Lập thực đơn 7 ngày giảm cân",
  "user_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Intent: nutrition_advice

```json
{
  "message": "Tôi cần ăn bao nhiêu protein mỗi ngày?",
  "user_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Intent: inventory_management

```json
{
  "message": "Tôi có gì trong kho?",
  "user_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Intent: general

```json
{
  "message": "Xin chào, bạn là ai?"
}
```

---

## Error Cases

### Missing message

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  --data-raw '{
    "user_id": "550e8400-e29b-41d4-a716-446655440000"
  }'
```

**Expected:** 422 Unprocessable Entity

### Empty message

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  --data-raw '{
    "message": ""
  }'
```

**Expected:** 400 Bad Request hoặc generic response

---

## Health Checks

### Basic health

```bash
curl http://localhost:8000/health
```

**Expected:**

```json
{
  "status": "healthy",
  "version": "0.1.0"
}
```

### Database health

```bash
curl http://localhost:8000/health/db
```

**Expected:**

```json
{
  "status": "healthy",
  "supabase": "connected",
  "postgres_pool": "disabled",
  "note": "Postgres pool is optional for persistence only"
}
```

### Prometheus metrics

```bash
curl http://localhost:8000/metrics
```

---

## Python Test Script

```python
import requests
import json

BASE_URL = "http://localhost:8000"

def test_simple_chat():
    """Test case 1: Simple chat"""
    response = requests.post(
        f"{BASE_URL}/chat",
        json={
            "message": "Hôm nay tôi muốn ăn đồ ăn nhẹ"
        }
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    return response

def test_chat_with_user():
    """Test case 2: Chat with user_id"""
    response = requests.post(
        f"{BASE_URL}/chat",
        json={
            "message": "Tìm món ăn với trứng",
            "user_id": "550e8400-e29b-41d4-a716-446655440000"
        }
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    return response

def test_chat_with_history():
    """Test case 3: Chat with conversation history"""
    response = requests.post(
        f"{BASE_URL}/chat",
        json={
            "message": "Vậy món gỏi cuốn thì sao?",
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
            "thread_id": "test_thread_1",
            "conversation_history": [
                {
                    "role": "user",
                    "content": "Tôi muốn tìm món ăn nhẹ"
                },
                {
                    "role": "assistant",
                    "content": "Bạn có thể thử nem rán, chả giò, hoặc bánh bao"
                }
            ]
        }
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    return response

def test_streaming():
    """Test case 4: Streaming endpoint"""
    response = requests.post(
        f"{BASE_URL}/chat/stream",
        json={
            "message": "Lập kế hoạch ăn uống 7 ngày",
            "user_id": "550e8400-e29b-41d4-a716-446655440000"
        },
        stream=True
    )

    print(f"Status: {response.status_code}")
    print("Streaming response:")
    for line in response.iter_lines():
        if line:
            decoded = line.decode('utf-8')
            if decoded.startswith('data: '):
                data = json.loads(decoded[6:])
                print(f"Event: {data}")

if __name__ == "__main__":
    print("=" * 60)
    print("Test 1: Simple chat")
    print("=" * 60)
    test_simple_chat()

    print("\n" + "=" * 60)
    print("Test 2: Chat with user_id")
    print("=" * 60)
    test_chat_with_user()

    print("\n" + "=" * 60)
    print("Test 3: Chat with history")
    print("=" * 60)
    test_chat_with_history()

    print("\n" + "=" * 60)
    print("Test 4: Streaming")
    print("=" * 60)
    test_streaming()
```

**Run script:**

```bash
python test_chat.py
```

---

## Postman Collection

Import this JSON into Postman:

```json
{
  "info": {
    "name": "Menu Green API",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "item": [
    {
      "name": "Chat - Simple",
      "request": {
        "method": "POST",
        "header": [
          {
            "key": "Content-Type",
            "value": "application/json"
          }
        ],
        "body": {
          "mode": "raw",
          "raw": "{\n  \"message\": \"Hôm nay tôi muốn ăn đồ ăn nhẹ\"\n}"
        },
        "url": {
          "raw": "http://localhost:8000/chat",
          "protocol": "http",
          "host": ["localhost"],
          "port": "8000",
          "path": ["chat"]
        }
      }
    },
    {
      "name": "Chat - With User ID",
      "request": {
        "method": "POST",
        "header": [
          {
            "key": "Content-Type",
            "value": "application/json"
          }
        ],
        "body": {
          "mode": "raw",
          "raw": "{\n  \"message\": \"Tìm món ăn với trứng\",\n  \"user_id\": \"550e8400-e29b-41d4-a716-446655440000\"\n}"
        },
        "url": {
          "raw": "http://localhost:8000/chat",
          "protocol": "http",
          "host": ["localhost"],
          "port": "8000",
          "path": ["chat"]
        }
      }
    },
    {
      "name": "Health Check",
      "request": {
        "method": "GET",
        "url": {
          "raw": "http://localhost:8000/health",
          "protocol": "http",
          "host": ["localhost"],
          "port": "8000",
          "path": ["health"]
        }
      }
    }
  ]
}
```

---

## Notes

- **user_id**: Phải là UUID format (ví dụ: `550e8400-e29b-41d4-a716-446655440000`)
- **thread_id**: String tùy ý để track conversation
- **conversation_history**: Array of objects với `role` và `content`
- **Streaming**: Sử dụng `/chat/stream` endpoint với `-N` flag trong curl

## API Documentation

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
