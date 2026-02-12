# Menu Green - Hệ điều hành Dinh dưỡng Thông minh

Một hệ thống Multi-Agent AI giúp quản lý dinh dưỡng cá nhân, lập kế hoạch bữa ăn, và tối ưu hóa sức khỏe.

**Tech Stack:** LangGraph + Google Gemini + FastAPI + Supabase (PostgreSQL + pgvector)

---

## 📚 Mục lục

- [Tính năng](#-tính-năng)
- [Kiến trúc](#-kiến-trúc-hệ-thống)
- [Cài đặt](#-cài-đặt)
- [Cấu hình](#-cấu-hình)
- [Database Setup](#-database-setup)
- [Nạp dữ liệu](#-nạp-dữ-liệu)
- [Chạy ứng dụng](#-chạy-ứng-dụng)
- [API Endpoints](#-api-endpoints)
- [Testing](#-testing)
- [Development](#-development)
- [Subscription Tiers](#-subscription-tiers)

---

## ✨ Tính năng

### Core Features

- 🤖 **Multi-Agent AI**: 6 agents chuyên biệt (Recipe, Nutrition, Inventory, Web Browser, General, Permission)
- 🔍 **Vector Search**: Tìm kiếm recipe bằng semantic search (pgvector + Gemini embeddings 768D)
- 🏷️ **Contextual Tagging**: `#no-sleepy`, `#warming`, `#quick-lunch`, `#office-friendly` cho gợi ý thông minh
- 📊 **Nutrition Calculation**: BMR/TDEE/Macros với công thức Mifflin-St Jeor
- 🥘 **Inventory Management**: Theo dõi hạn sử dụng, zero-waste meal planning
- 🌐 **Web Browsing**: Crawl recipe từ URL với Jina Reader API
- 💰 **Subscription Tiers**: Free, Saving, Energy, Performance

### Unique Features

- **Context-aware recommendations**: Gợi ý dựa trên thời tiết, vai trò công việc, thời gian
- **Vietnamese-first**: Native support cho tiếng Việt và ẩm thực Việt
- **Science-based**: Sử dụng công thức dinh dưỡng chuẩn y khoa

---

## 🏗️ Kiến trúc Hệ thống

```
┌─────────────────────────────────────────────────────────┐
│                 FastAPI Gateway                          │
│              (app/main.py)                               │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│          LangGraph Orchestrator                          │
│           (app/agents/orchestrator.py)                   │
│  ┌─────────────────────────────────────────────────┐    │
│  │     Intent Classifier (Gemini Flash)             │    │
│  └─────────────────────────────────────────────────┘    │
│                         │                                │
│    ┌────────────────────┼────────────────────┐          │
│    ▼                    ▼                    ▼          │
│ ┌──────────┐      ┌──────────┐        ┌──────────┐      │
│ │ Nutrition│      │ Inventory│        │  Recipe  │      │
│ │  Agent   │      │  Agent   │        │   RAG    │      │
│ └──────────┘      └──────────┘        └──────────┘      │
│    ▼                    ▼                    ▼          │
│ ┌──────────┐      ┌──────────┐        ┌──────────┐      │
│ │Web Browse│      │  General │        │Permission│      │
│ │  Agent   │      │  Agent   │        │  Denied  │      │
│ └──────────┘      └──────────┘        └──────────┘      │
└─────────────────────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│         Supabase (PostgreSQL + pgvector)                 │
│  - user_profiles, recipes (with 768D embeddings)        │
│  - user_inventory, ingredients, daily_logs               │
└─────────────────────────────────────────────────────────┘
```

**Agent Routing:**

1. User message → Intent Classification
2. Check subscription tier permissions
3. Route to appropriate agent
4. Fetch context (user profile, inventory)
5. Generate response with LLM
6. Return to user

---

## 🚀 Cài đặt

### Prerequisites

- Python 3.10+
- Supabase account (hoặc local Supabase via Docker)
- Google Gemini API key

### 1. Clone và cài dependencies

```bash
git clone https://github.com/yourusername/menu_green.git
cd menu_green
pip install -r requirements.txt
```

### 2. Verify installation

```bash
# Check Python version
python --version  # Should be 3.10+

# Test imports
python -c "import langchain; import supabase; import fastapi; print('✅ All imports successful')"
```

---

## ⚙️ Cấu hình

### Environment Variables

Tạo file `.env` trong thư mục root:

```bash
# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-or-service-role-key

# Google Gemini API
GOOGLE_API_KEY=your-gemini-api-key

# Model Configuration
LLM_MODEL=gemini-2.0-flash-exp
EMBEDDING_MODEL=models/text-embedding-004

# App Configuration
APP_NAME=Menu Green
DEBUG=true
```

**Lấy API Keys:**

1. **Supabase**:
   - Tạo project tại [supabase.com](https://supabase.com)
   - Vào Settings → API → Copy URL và `anon` key (hoặc `service_role` cho admin access)

2. **Google Gemini**:
   - Vào [Google AI Studio](https://makersuite.google.com/app/apikey)
   - Tạo API key mới

### Configuration Files

- `.env`: Environment variables (không commit vào Git)
- `app/core/config.py`: Settings management với Pydantic
- `models_list.json`: Reference cho available Gemini models

---

## 🗄️ Database Setup

### 1. Tạo Database Schema

```bash
# Chạy trong Supabase SQL Editor hoặc psql
psql -h your-db-host -d postgres -U postgres -f schema.sql
```

**Schema bao gồm:**

- `user_profiles`: User demographics & preferences
- `recipes`: Recipes với pgvector embeddings (768D)
- `ingredients`: Master ingredient list
- `recipe_ingredients`: Many-to-many relationship
- `user_inventory`: User pantry với expiry tracking
- `daily_logs`: Health metrics & mood

### 2. Tạo Vector Search Function

```bash
psql -h your-db-host -d postgres -U postgres -f match_recipes_function.sql
```

Hàm này tạo RPC `match_recipes(query_embedding, match_threshold, match_count)` cho vector similarity search.

### 3. Row Level Security (RLS)

**Development (permissive):**

```bash
psql -h your-db-host -d postgres -U postgres -f schema_rls_dev.sql
```

**Production (strict):**

```bash
psql -h your-db-host -d postgres -U postgres -f schema_rls_prod.sql
```

⚠️ **Quan trọng**: Luôn dùng `schema_rls_prod.sql` cho production để bảo vệ user data!

**RLS Policies Production:**

- Users chỉ xem/sửa profile của họ
- Users chỉ quản lý inventory của họ
- Recipes: Public read, admin-only write
- Ingredients: Public read, admin-only write

---

## 📥 Nạp dữ liệu

Dữ liệu là "trí não" của Menu Green. Cần nạp recipes trước khi sử dụng.

### Option 1: Tạo dữ liệu Synthetic (Recommended)

Sử dụng Gemini để generate Vietnamese recipes:

```bash
# Generate 20 recipes across all Vietnamese cuisine categories
python -m app.data_pipeline.ingest --mode synthetic --count 20

# Generate specific category
python -m app.data_pipeline.ingest --mode synthetic --count 10 --category "Món Miền Nam"
```

**Vietnamese categories supported:**

- Món Miền Bắc, Miền Trung, Miền Nam
- Món Chay, Món Âu, Món Á
- Cơm, Phở/Bún/Miến, Canh/Súp
- Món Nướng, Món Xào, Món Hấp
- Salad, Smoothie, Món Tráng Miệng

### Option 2: Nạp từ CSV (Food.com/Recipe1M+)

```bash
python -m app.data_pipeline.ingest --mode csv --input "path/to/recipes.csv" --limit 100
```

**CSV format cần:**

- Columns: `name`, `ingredients`, `steps`, `nutrition` (PDV format)

### Option 3: Scrape từ website

```bash
python -m app.data_pipeline.ingest --mode scrape --urls "https://cookpad.com/vn/recipe/..."
```

### Option 4: Import từ JSON

```bash
python -m app.data_pipeline.ingest --mode file --input "raw_recipes.json"
```

**Pipeline flow:**

1. **Ingest**: Load raw data (synthetic/scrape/file/csv)
2. **Clean**: LLM normalization + contextual tagging
3. **Embed**: Generate 768D vectors với Gemini Embedding-001
4. **Store**: Insert vào Supabase với retry logic

---

## 🎯 Chạy ứng dụng

### Development Server

```bash
uvicorn app.main:app --reload --port 8000
```

- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

### Production Server

```bash
# With Gunicorn
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

# With Docker
docker build -t menu-green .
docker run -p 8000:8000 --env-file .env menu-green
```

---

## 📡 API Endpoints

### Health Check

```bash
GET /health
```

Response:

```json
{
  "status": "healthy",
  "version": "0.1.0"
}
```

### Chat (Sync)

```bash
POST /chat
Content-Type: application/json

{
  "message": "Tìm món ăn từ cà chua và trứng",
  "user_id": "uuid-here",
  "history": []
}
```

Response:

```json
{
  "response": "Tôi tìm được 3 món từ cà chua và trứng...",
  "intent": "recipe_search"
}
```

### Chat (Streaming)

```bash
POST /chat/stream
Content-Type: application/json

{
  "message": "Tính TDEE cho tôi",
  "user_id": "uuid-here"
}
```

Response: Server-Sent Events (SSE)

```
data: {"content": "Dựa vào"}
data: {"content": " thông tin"}
data: {"content": " của bạn..."}
data: {"done": true}
```

### Error Response Format

```json
{
  "code": "subscription_required",
  "message": "This feature requires Saving tier or higher",
  "details": {
    "required_tier": "saving",
    "current_tier": "free",
    "feature": "inventory_management"
  },
  "suggestion": "Upgrade to Saving tier to access inventory management"
}
```

**Error Codes:**

- `unauthorized`: Chưa đăng nhập
- `subscription_required`: Cần nâng cấp gói
- `invalid_input`: Input không hợp lệ
- `rate_limit_exceeded`: Quá giới hạn requests
- `gemini_error`: Lỗi AI service
- `supabase_error`: Lỗi database
- `internal_error`: Lỗi hệ thống

---

## 🧪 Testing

### Unit Tests

```bash
# Test matching logic
python evaluate_pipeline.py

# Test orchestrator với mock
python test_context_mock.py

# Test với real API (cần API keys)
python test_context.py
```

### Integration Tests

```bash
# Test Supabase connection
python verify_supabase.py

# Test Gemini embeddings
python verify_gemini.py

# Test web browsing agent
python verify_crawling.py

# Check data count
python check_data.py
```

### Debug Tools

```bash
# Debug Gemini models
python debug_gemini.py

# Test different embedding dimensions
python verify_gemini.py --model models/text-embedding-004
```

---

## 🛠️ Development

### Project Structure

```
menu_green/
├── app/
│   ├── main.py              # FastAPI entry point
│   ├── agents/              # LangGraph agents
│   │   ├── orchestrator.py  # Central router
│   │   ├── nutrition.py     # BMR/TDEE calc
│   │   ├── inventory.py     # Expiry tracking
│   │   ├── rag_tool.py      # Vector search
│   │   └── web_browser.py   # Jina Reader
│   ├── core/                # Core utilities
│   │   ├── config.py        # Settings
│   │   ├── supabase_client.py
│   │   ├── matching.py      # Ingredient logic
│   │   └── errors.py        # Error handling
│   └── data_pipeline/       # Data ingestion
│       ├── ingest.py        # CLI orchestrator
│       ├── scraper.py       # Web scraping
│       ├── cleaner.py       # LLM normalization
│       └── csv_ingest.py    # CSV import
├── schema.sql               # Database schema
├── match_recipes_function.sql  # Vector search RPC
├── schema_rls_dev.sql       # Dev RLS policies
├── schema_rls_prod.sql      # Production RLS
├── requirements.txt
└── README.md
```

### Adding New Agents

1. **Create agent file**: `app/agents/my_agent.py`

```python
from app.agents.orchestrator import AgentState

def my_agent(state: AgentState) -> AgentState:
    """Agent description."""
    # Your logic here
    return state
```

2. **Update orchestrator**: `app/agents/orchestrator.py`

```python
# Add intent in classify_intent()
INTENT_PROMPT = """...
- my_intent: Description
"""

# Add permission
TIER_PERMISSIONS = {
    "free": [..., "my_intent"],
    # ...
}

# Add routing
def route_by_intent(state: AgentState) -> str:
    if state["intent"] == "my_intent":
        return "my_agent_node"
    # ...

# Add to graph
graph_builder.add_node("my_agent_node", my_agent)
graph_builder.add_edge("my_agent_node", END)
```

3. **Write tests**: `tests/agents/test_my_agent.py`

### Code Style

- **Formatting**: Follow PEP 8
- **Type hints**: Use for all functions
- **Docstrings**: Google style
- **Async**: Prefer async/await for I/O ops
- **Error handling**: Use custom exceptions from `app/core/errors.py`

### Git Workflow

```bash
# Create feature branch
git checkout -b feature/my-feature

# Make changes + tests
git add .
git commit -m "feat: add my feature"

# Push and create PR
git push origin feature/my-feature
```

---

---

## 💰 Subscription Tiers

| Gói             | Giá/tháng | Tính năng                                                                            |
| --------------- | --------- | ------------------------------------------------------------------------------------ |
| **Free**        | $0        | ✅ Tìm recipe cơ bản<br>✅ Chat với AI<br>✅ Web browsing                            |
| **Saving**      | $4.99     | + ✅ Quản lý inventory<br>+ ✅ Zero-waste matching<br>+ ✅ Expiry alerts             |
| **Energy**      | $9.99     | + ✅ Meal planner<br>+ ✅ Contextual tagging<br>+ ✅ Weather-based suggestions       |
| **Performance** | $14.99    | + ✅ Nutrition calculator (BMR/TDEE)<br>+ ✅ Macro tracking<br>+ ✅ Health analytics |

**Feature Matrix:**

| Feature                 | Free | Saving | Energy | Performance |
| ----------------------- | ---- | ------ | ------ | ----------- |
| Recipe search           | ✅   | ✅     | ✅     | ✅          |
| General chat            | ✅   | ✅     | ✅     | ✅          |
| Web browsing            | ✅   | ✅     | ✅     | ✅          |
| Inventory management    | ❌   | ✅     | ✅     | ✅          |
| Expiry tracking         | ❌   | ✅     | ✅     | ✅          |
| Zero-waste matching     | ❌   | ✅     | ✅     | ✅          |
| Meal planner            | ❌   | ❌     | ✅     | ✅          |
| Contextual tags         | ❌   | ❌     | ✅     | ✅          |
| Nutrition calculator    | ❌   | ❌     | ❌     | ✅          |
| BMR/TDEE/Macro tracking | ❌   | ❌     | ❌     | ✅          |

---

## 🔧 Troubleshooting

### Common Issues

**1. "Supabase connection failed"**

```bash
# Check .env file
cat .env | grep SUPABASE

# Test connection
python verify_supabase.py
```

**2. "Gemini API error: quota exceeded"**

- Giảm batch size trong ingestion
- Thêm rate limiting với `time.sleep()`
- Upgrade Gemini quota tại Google AI Studio

**3. "No recipes found"**

```bash
# Check if data was ingested
python check_data.py

# Re-ingest data
python -m app.data_pipeline.ingest --mode synthetic --count 20
```

**4. "Vector search returns no results"**

- Check embedding dimension (should be 768D for Gemini Embedding-001)
- Verify `match_recipes` function exists:
  ```sql
  SELECT routine_name FROM information_schema.routines WHERE routine_name = 'match_recipes';
  ```

**5. "Permission denied error"**

- Check RLS policies are applied
- For development, use `schema_rls_dev.sql`
- Verify user_id matches authenticated user

### Debug Mode

Enable detailed logging:

```python
# app/main.py
import logging
logging.basicConfig(level=logging.DEBUG)
```

---

## 📚 Additional Resources

**Documentation:**

- [LangGraph Docs](https://langchain-ai.github.io/langgraph/)
- [Google Gemini API](https://ai.google.dev/docs)
- [Supabase Docs](https://supabase.com/docs)
- [pgvector](https://github.com/pgvector/pgvector)

**Vietnamese NLP:**

- [underthesea](https://github.com/undertheseanlp/underthesea) - Vietnamese NLP toolkit
- [PhoBERT](https://github.com/VinAIResearch/PhoBERT) - Vietnamese BERT

**Nutrition Science:**

- [Mifflin-St Jeor Equation](https://en.wikipedia.org/wiki/Basal_metabolic_rate#BMR_estimation_formulas)
- [USDA FoodData Central](https://fdc.nal.usda.gov/)

---

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repo
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

**Guidelines:**

- Follow existing code style
- Add tests for new features
- Update README if needed
- Keep commits atomic and descriptive

---

## 📝 License

This project is licensed under the MIT License - see LICENSE file for details.

---

## 📞 Support

**Issues:** Report bugs via [GitHub Issues](https://github.com/yourusername/menu_green/issues)

**Contact:** your.email@example.com

**Slack/Discord:** [Join our community](#)

---

## 🗺️ Roadmap

### Phase 1: MVP (Completed ✅)

- [x] Multi-agent orchestration
- [x] Recipe vector search
- [x] Contextual tagging
- [x] Nutrition calculator
- [x] Inventory management
- [x] Subscription tiers

### Phase 2: Enhancements (In Progress 🚧)

- [ ] True streaming implementation
- [ ] Meal planner with optimization
- [ ] Fuzzy ingredient matching
- [ ] Vietnamese NLP tokenization
- [ ] Embedding caching (Redis)
- [ ] Comprehensive testing

### Phase 3: Production (Planned 📅)

- [ ] Rate limiting
- [ ] Monitoring & telemetry
- [ ] Data quality validation
- [ ] Mobile app (React Native)
- [ ] User authentication
- [ ] Payment integration

### Phase 4: Advanced (Future 🚀)

- [ ] Voice input (Vietnamese STT)
- [ ] Image recognition for food
- [ ] Social features (share recipes)
- [ ] Grocery integration
- [ ] Wearable sync (Fitbit, Apple Watch)
- [ ] Multi-language support

---

## 🙏 Acknowledgments

- **LangChain/LangGraph**: For agent orchestration framework
- **Google Gemini**: For powerful LLM and embeddings
- **Supabase**: For BaaS with pgvector support
- **Vietnamese community**: For cuisine inspiration

---

**Made with ❤️ and 🥗 by Menu Green Team**

_Last updated: February 11, 2026_
