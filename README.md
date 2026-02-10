# Model_RAG_MenuGreen

# Menu Green - Hệ điều hành Dinh dưỡng Thông minh

Một hệ thống Multi-Agent AI giúp quản lý dinh dưỡng cá nhân, lập kế hoạch bữa ăn, và tối ưu hóa sức khỏe.

## 🚀 Hướng Dẫn Chạy Chương Trình

### 1. Cài đặt Môi trường

```bash
# Clone và cài dependencies
pip install -r requirements.txt
```

### 2. Cấu hình Database & API Key

- Copy file cấu hình mẫu:
  ```bash
  cp .env.example .env
  ```
- Mở file `.env` và điền:
  - `SUPABASE_URL`: URL dự án Supabase của bạn.
  - `SUPABASE_KEY`: Key `service_role` (để ghi dữ liệu) hoặc `anon` (nếu chỉ đọc).
  - `OPENAI_API_KEY`: Key OpenAI (để chạy LLM Agent).

- **Khởi tạo Database:**
  - Chạy script SQL trong `schema.sql` (Tạo bảng).
  - Chạy script SQL trong `match_recipes_function.sql` (Tạo hàm tìm kiếm vector).

### 3. Nạp Dữ liệu (Pipeline)

Dữ liệu là "trí não" của Menu Green. Bạn cần nạp công thức nấu ăn vào DB trước khi dùng.

**Cách 1: Tạo dữ liệu giả lập (Synthetic Data)**
Dùng GPT-4o để tạo công thức món ăn Việt Nam chuẩn.

```bash
python -m app.data_pipeline.ingest --mode synthetic --count 20
```

**Cách 2: Nạp từ Food.com/Recipe1M+ (CSV)**
Nạp dataset lớn, tự động map nutrition và tag ngữ cảnh.

```bash
python -m app.data_pipeline.ingest --mode csv --input "path/to/recipes.csv" --limit 100
```

**Cách 3: Nạp từ file JSON thô**

```bash
python -m app.data_pipeline.ingest --mode file --input "raw_data.json"
```

### 4. Kiểm thử & Đánh giá (Evaluation)

Chạy script kiểm tra các kịch bản thực tế (Vd: Nhân viên văn phòng, trời mưa...).

```bash
# Kiểm tra Logic Matching & Contextual Tagging
python evaluate_pipeline.py

# Kiểm tra Logic Agent (Mock test, không cần API Key)
python test_context_mock.py
```

### 5. Chạy Backend Server

Khởi động API để kết nối với Frontend hoặc Mobile App.

```bash
uvicorn app.main:app --reload
```

- API Docs: http://localhost:8000/docs

---

## Kiến trúc Hệ thống

```
┌─────────────────────────────────────────────────────────┐
│                    FastAPI Gateway                       │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│              LangGraph Orchestrator                      │
│  ┌─────────────────────────────────────────────────┐    │
│  │           Intent Classifier (GPT-4o-mini)        │    │
│  └─────────────────────────────────────────────────┘    │
│                         │                                │
│    ┌────────────────────┼────────────────────┐          │
│    ▼                    ▼                    ▼          │
│ ┌──────────┐      ┌──────────┐        ┌──────────┐      │
│ │ Nutrition│      │ Inventory│        │  Recipe  │      │
│ │  Agent   │      │  Agent   │        │   RAG    │      │
│ └──────────┘      └──────────┘        └──────────┘      │
└─────────────────────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                Supabase (PostgreSQL + pgvector)          │
└─────────────────────────────────────────────────────────┘
```

## Subscription Tiers

| Gói            | Tính năng                                         |
| -------------- | ------------------------------------------------- |
| **Miễn phí**   | Tìm công thức cơ bản                              |
| **Tiết kiệm**  | + Quản lý kho (Zero Waste), Matching theo tập hợp |
| **Năng lượng** | + Lập kế hoạch bữa ăn, Contextual Tagging         |
| **Hiệu suất**  | + Tính toán dinh dưỡng chính xác (BMR/TDEE/Macro) |
