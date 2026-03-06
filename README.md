# 🥗 Menu Green — Hệ điều hành Dinh dưỡng Thông minh

Hệ thống **Multi-Agent AI** giúp quản lý dinh dưỡng cá nhân, lập kế hoạch bữa ăn và tối ưu hóa sức khỏe.

**Tech Stack:** `LangGraph` · `Google Gemini` · `FastAPI` · `Supabase (PostgreSQL + pgvector)` · `Mem0` · `ChromaDB`

---

## 📚 Mục lục

- [Tính năng](#-tính-năng)
- [Kiến trúc hệ thống](#️-kiến-trúc-hệ-thống)
- [Cấu trúc thư mục](#-cấu-trúc-thư-mục)
- [Cài đặt & Cấu hình](#-cài-đặt--cấu-hình)
- [Database Setup](#️-database-setup)
- [Nạp dữ liệu](#-nạp-dữ-liệu)
- [Chạy ứng dụng](#-chạy-ứng-dụng)
- [API Endpoints](#-api-endpoints)
- [Subscription Tiers](#-subscription-tiers)
- [Testing & Debug](#-testing--debug)
- [Thêm Agent mới](#️-thêm-agent-mới)
- [Troubleshooting](#-troubleshooting)

---

## ✨ Tính năng

### Core Features

| Tính năng | Mô tả |
|-----------|-------|
| 🤖 **Multi-Agent AI** | 6 agents chuyên biệt: Recipe RAG, Nutrition, Inventory, Meal Planner, Web Browser, General |
| 🔍 **Vector Search (RAG)** | Semantic search công thức với pgvector + Gemini Embeddings (768D / 3072D) |
| 🧠 **Persistent Memory** | Mem0 + ChromaDB lưu sở thích người dùng; TTL-cache 5 phút |
| 📊 **Nutrition Calc** | Tính BMR/TDEE/Macros theo công thức Mifflin-St Jeor |
| 🥘 **Inventory Tracking** | Theo dõi hạn sử dụng, zero-waste meal matching |
| 📅 **Meal Planner** | Pipeline 5 bước tạo thực đơn 7 ngày có danh sách mua hàng |
| 🌐 **Web Browsing** | Crawl & tóm tắt công thức từ URL bất kỳ qua Jina Reader |
| 💰 **Subscription Tiers** | Free / Saving / Energy / Performance |
| 📈 **Observability** | Prometheus metrics tại `/metrics`; middleware đo latency mọi request |
| 🔁 **Retry & Resilience** | Decorator `with_retry` cho mọi LLM / Supabase call |
| 💾 **Persistence** | LangGraph PostgresSaver lưu conversation state theo `thread_id` |

---

## 🏗️ Kiến trúc hệ thống

```
┌───────────────────────────────────────────────────────────────┐
│                    FastAPI Gateway                             │
│              app/main.py  (port 8000)                         │
│  - POST /chat         (sync, 120s timeout)                    │
│  - POST /chat/stream  (Server-Sent Events)                    │
│  - GET  /health  /health/db  /metrics                         │
└───────────────────────────┬───────────────────────────────────┘
                            │
┌───────────────────────────▼───────────────────────────────────┐
│             LangGraph Orchestrator (Hub-and-Spoke)            │
│          app/agents/orchestrator.py                           │
│                                                               │
│  [START] → classify_intent → route_by_intent                  │
│                                   │                           │
│              ┌────────────────────┼────────────────────┐      │
│              ▼                    ▼                    ▼      │
│          [recipe]           [nutrition]         [inventory]   │
│          [web_browsing]     [general]           [meal_plan]   │
│          [permission_denied]                                  │
│              │                                                │
│              └──────────────→ save_memory → [END]            │
└───────────────────────────────────────────────────────────────┘
                            │
┌───────────────────────────▼───────────────────────────────────┐
│              Meal Plan Subgraph (5-step pipeline)             │
│                                                               │
│  nutrition_analyzer → recipe_retriever → meal_planner         │
│                    → recipe_adapter → validation_shopping      │
└───────────────────────────────────────────────────────────────┘
                            │
┌───────────────────────────▼───────────────────────────────────┐
│           Data Layer                                          │
│  Supabase (PostgreSQL + pgvector)  ←→  ChromaDB (Mem0)        │
│  - users, recipes, ingredients, inventory, daily_logs         │
│  - 768D / 3072D recipe embeddings (match_recipes RPC)         │
└───────────────────────────────────────────────────────────────┘
```

**Luồng xử lý request:**

1. Request gửi đến FastAPI → lấy user profile + inventory song song (asyncio.gather)
2. `classify_intent` — heuristic URL check → Gemini Flash phân loại intent
3. Mem0 inject user memories vào context
4. `route_by_intent` — kiểm tra subscription permissions → chọn agent
5. Agent xử lý → `save_memory` lưu interaction → trả response

---

## 📁 Cấu trúc thư mục

```
Model_RAG_MenuGreen/
│
├── app/
│   ├── main.py                   # FastAPI entry point, endpoints, middleware
│   ├── agents/
│   │   ├── state.py              # AgentState TypedDict (shared graph state)
│   │   ├── orchestrator.py       # LangGraph graph, intent router, all agent nodes
│   │   ├── nutrition.py          # BMR/TDEE/Macro calculator
│   │   ├── inventory.py          # Expiry tracking, inventory alerts
│   │   ├── rag_tool.py           # RAGTool: pgvector semantic search
│   │   ├── web_browser.py        # Jina Reader URL crawler
│   │   └── meal_planner.py       # 5-agent meal planning pipeline
│   │
│   ├── core/
│   │   ├── config.py             # Settings via pydantic-settings (.env)
│   │   ├── supabase_client.py    # Supabase CRUD + async helpers
│   │   ├── memory.py             # Mem0 MemoryManager (singleton, TTL cache)
│   │   ├── matching.py           # Ingredient matching logic
│   │   ├── errors.py             # Custom exceptions & ErrorResponse models
│   │   ├── metrics.py            # Prometheus counters/gauges/histograms
│   │   └── retry_utils.py        # with_retry decorator, safe_llm_call
│   │
│   └── data_pipeline/
│       ├── ingest.py             # CLI: --mode synthetic|csv|scrape|file
│       ├── cleaner.py            # LLM normalization + contextual tagging
│       ├── scraper.py            # BeautifulSoup + Jina web scraper
│       ├── csv_ingest.py         # Food.com / Recipe1M+ CSV importer
│       └── auto_discovery.py     # Auto-crawl recipe discovery agent
│
├── schema.sql                    # Full database schema
├── match_recipes_function.sql    # pgvector RPC function
├── fix_rls.sql                   # RLS policy fixes
├── checkpoints.sql               # LangGraph checkpoint tables
│
├── tests/                        # pytest test suite
├── monitoring/                   # Prometheus/Grafana configs
│
├── evaluate_pipeline.py          # Pipeline evaluation script
├── requirements.txt
├── .env.example
└── README.md
```

---

## 🚀 Cài đặt & Cấu hình

### Prerequisites

- Python **3.10+**
- Supabase account (hoặc local Supabase via Docker)
- Google Gemini API key

### 1. Cài đặt dependencies

```bash
git clone https://github.com/yourusername/menu_green.git
cd menu_green
pip install -r requirements.txt
```

### 2. Tạo file `.env`

```bash
cp .env.example .env
```

Điền vào các giá trị:

```env
# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-or-service-role-key
POSTGRES_URL=postgresql://postgres:password@db.xxx.supabase.co:5432/postgres

# Google Gemini
GOOGLE_API_KEY=your-gemini-api-key
LLM_MODEL=gemini-2.5-flash
EMBEDDING_MODEL=models/gemini-embedding-001

# App
APP_NAME=Menu Green
DEBUG=false

# Optional: Jina Reader (web browsing)
JINA_API_KEY=your-jina-api-key

# Optional: Auto-discovery tuning
DISCOVERY_DELAY_SECONDS=2.0
DISCOVERY_MAX_PER_RUN=20
```

> **Lấy API Keys:**
> - **Supabase**: Settings → API → URL + `anon` key
> - **Google Gemini**: [Google AI Studio](https://makersuite.google.com/app/apikey)
> - **Jina**: [jina.ai](https://jina.ai) (miễn phí, tùy chọn)

---

## 🗄️ Database Setup

### 1. Tạo schema

```bash
# Chạy trong Supabase SQL Editor
psql -h your-db-host -d postgres -U postgres -f schema.sql
```

**Tables:**

| Table | Mô tả |
|-------|-------|
| `user_profiles` | Demographics, goals, health metrics |
| `recipes` | Recipes + pgvector embedding (768D) |
| `ingredients` | Master ingredient list |
| `recipe_ingredients` | Many-to-many |
| `user_inventory` | Pantry với expiry tracking |
| `daily_logs` | Health metrics & mood |

### 2. Tạo Vector Search Function

```bash
psql -h your-db-host -d postgres -U postgres -f match_recipes_function.sql
```

Tạo RPC `match_recipes(query_embedding, match_threshold, match_count)`.

### 3. LangGraph Persistence Tables

```bash
psql -h your-db-host -d postgres -U postgres -f checkpoints.sql
```

### 4. Row Level Security (RLS)

```bash
# Development (permissive)
psql ... -f fix_rls.sql

# Production (strict) — LUÔN dùng cho production!
```

> ⚠️ **Production RLS:** Users chỉ truy cập data của chính họ. Recipes/Ingredients: public read, admin-only write.

---

## 📥 Nạp dữ liệu

Recipes là "trí não" của hệ thống. Cần ingest trước khi chat.

### Option 1: Synthetic (Khuyến nghị — dùng Gemini)

```bash
# 20 recipes, tất cả category
python -m app.data_pipeline.ingest --mode synthetic --count 20

# Category cụ thể
python -m app.data_pipeline.ingest --mode synthetic --count 10 --category "Món Miền Nam"
```

**Vietnamese categories:** Món Miền Bắc/Trung/Nam, Món Chay, Món Âu, Món Á, Cơm, Phở/Bún/Miến, Canh/Súp, Nướng, Xào, Hấp, Salad, Smoothie, Tráng Miệng.

### Option 2: CSV (Food.com / Recipe1M+)

```bash
python -m app.data_pipeline.ingest --mode csv --input "path/to/recipes.csv" --limit 100
```

Columns cần: `name`, `ingredients`, `steps`, `nutrition`.

### Option 3: Scrape từ URL

```bash
python -m app.data_pipeline.ingest --mode scrape --urls "https://cookpad.com/vn/recipe/..."
```

### Option 4: Auto-Discovery

```bash
python run_auto_discovery.py
```

Agent tự crawl và phát hiện công thức mới theo lịch.

**Pipeline Flow:**

```
Ingest (raw data) → Cleaner (LLM normalize + tag) → Embed (768D) → Supabase (pgvector)
```

---

## 🎯 Chạy ứng dụng

### Development

```bash
uvicorn app.main:app --reload --port 8000
```

- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- Health check: [http://localhost:8000/health](http://localhost:8000/health)
- Prometheus metrics: [http://localhost:8000/metrics](http://localhost:8000/metrics)

### Production

```bash
# Gunicorn
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

# Docker
docker build -t menu-green .
docker run -p 8000:8000 --env-file .env menu-green
```

---

## 📡 API Endpoints

### `GET /health`

```json
{ "status": "healthy", "version": "0.1.0" }
```

### `GET /health/db`

Kiểm tra Supabase connection và PostgreSQL pool (nếu có).

### `GET /metrics`

Prometheus metrics (HTTP requests, latency, errors, cache stats, system health).

### `POST /chat`

```json
{
  "message": "Tìm món ăn từ cà chua và trứng",
  "user_id": "uuid-here",
  "thread_id": "optional-thread-id",
  "conversation_history": []
}
```

Response:

```json
{
  "response": "Tôi tìm được 3 món từ cà chua và trứng...",
  "intent": "recipe_search"
}
```

> Timeout: **120 giây**. `thread_id` dùng cho LangGraph persistence (nếu không truyền, dùng `user_id`).

### `POST /chat/stream`

Giống `/chat` nhưng trả về **Server-Sent Events**:

```
data: {"node": "recipe", "content": "Dựa vào..."}
data: {"node": "save_memory", "content": ""}
data: {"done": true}
```

Streaming theo từng node LangGraph. Có timeout check 120 giây.

### Error Response Format

```json
{
  "code": "subscription_required",
  "message": "This feature requires Saving tier or higher",
  "details": { "required_tier": "saving", "current_tier": "free", "feature": "inventory_management" },
  "suggestion": "Upgrade to Saving tier to access inventory management"
}
```

**Error Codes:** `unauthorized` · `subscription_required` · `invalid_input` · `rate_limit_exceeded` · `gemini_error` · `supabase_error` · `internal_error`

---

## 💰 Subscription Tiers

| Gói | Giá/tháng | Intent được phép |
|-----|-----------|-----------------|
| **Free** | $0 | `recipe_search`, `general`, `web_browsing` |
| **Saving** | $4.99 | + `inventory_check` |
| **Energy** | $9.99 | + `meal_plan` |
| **Performance** | $14.99 | + `nutrition_calc` |

**Feature Matrix:**

| Feature | Free | Saving | Energy | Performance |
|---------|------|--------|--------|-------------|
| Recipe search (RAG) | ✅ | ✅ | ✅ | ✅ |
| General Q&A | ✅ | ✅ | ✅ | ✅ |
| Web browsing | ✅ | ✅ | ✅ | ✅ |
| Inventory management | ❌ | ✅ | ✅ | ✅ |
| Expiry tracking | ❌ | ✅ | ✅ | ✅ |
| Meal planner (7 ngày) | ❌ | ❌ | ✅ | ✅ |
| Nutrition calc (BMR/TDEE) | ❌ | ❌ | ❌ | ✅ |
| Macro tracking | ❌ | ❌ | ❌ | ✅ |

---

## 🧪 Testing & Debug

### Integration Tests

```bash
python verify_supabase.py      # Test Supabase connection
python verify_gemini.py        # Test Gemini embeddings
python verify_crawling.py      # Test web browsing agent
python verify_mem0.py          # Test Mem0 memory
python verify_monitoring.py    # Test Prometheus metrics
python check_data.py           # Đếm số recipes trong DB
```

### Evaluation

```bash
python evaluate_pipeline.py    # Đánh giá chất lượng RAG pipeline
```

### Debug Tools

```bash
python debug_gemini.py         # Debug Gemini models available
python inspect_schema.py       # Inspect DB schema
```

### Pytest

```bash
pytest tests/ -v
pytest tests/ -v --asyncio-mode=auto
```

---

## 🛠️ Thêm Agent mới

### 1. Tạo agent file

```python
# app/agents/my_agent.py
from app.agents.state import AgentState
from langchain_core.messages import AIMessage

def my_agent(state: AgentState) -> dict:
    """Mô tả agent."""
    # Logic của bạn
    return {"messages": [AIMessage(content="Response")]}
```

### 2. Đăng ký vào Orchestrator (`app/agents/orchestrator.py`)

```python
# Bước 1: Thêm intent vào INTENT_PROMPT
# Bước 2: Thêm permission vào TIER_PERMISSIONS
TIER_PERMISSIONS = {
    "free": [..., "my_intent"],
    ...
}
# Bước 3: Thêm route
routes = { "my_intent": "my_agent_node", ... }
# Bước 4: Thêm node và edge vào graph
workflow.add_node("my_agent_node", my_agent)
workflow.add_edge("my_agent_node", "save_memory")
```

### 3. Viết tests

```python
# tests/agents/test_my_agent.py
```

---

## 🔧 Troubleshooting

| Lỗi | Giải pháp |
|-----|-----------|
| `Supabase connection failed` | Kiểm tra `SUPABASE_URL`, `SUPABASE_KEY` trong `.env`. Chạy `python verify_supabase.py` |
| `Gemini quota exceeded` | Giảm batch size, thêm `time.sleep()`, hoặc upgrade quota tại Google AI Studio |
| `No recipes found` | Chạy `python check_data.py` → nếu 0 recipes, chạy data ingestion |
| `Vector search no results` | Kiểm tra embedding dimension (768D). Verify `match_recipes` function tồn tại trong DB |
| `Permission denied (RLS)` | Đang dùng production RLS. Dùng `fix_rls.sql` cho dev |
| `asyncio.TimeoutError` | Orchestrator vượt 120s. Thử request đơn giản hơn |
| `Mem0 / ChromaDB error` | Xóa `mem0_chroma_db/` và `mem0_history.db`, khởi động lại |

### Enable Debug Logging

```python
# app/main.py hoặc khi start uvicorn
import logging
logging.basicConfig(level=logging.DEBUG)
```

---

## 📚 Tài liệu tham khảo

- [LangGraph Docs](https://langchain-ai.github.io/langgraph/)
- [Google Gemini API](https://ai.google.dev/docs)
- [Supabase Docs](https://supabase.com/docs)
- [pgvector](https://github.com/pgvector/pgvector)
- [Mem0 Docs](https://docs.mem0.ai)
- [Mifflin-St Jeor BMR Formula](https://en.wikipedia.org/wiki/Basal_metabolic_rate#BMR_estimation_formulas)

---

**Made with ❤️ and 🥗 by Menu Green Team**

_Last updated: March 2026_
