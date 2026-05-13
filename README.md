# Menu Green AI Worker

Menu Green is now organized primarily as an internal Python AI worker that a
C# gateway can call over HTTP. The bundled frontend is optional and disabled by
default.

## Architecture

- `C# gateway`: public API, auth, mobile/web integration
- `Python worker`: intent classification, RAG, nutrition logic, meal planning
- `Supabase`: data store
- `ONNX`: local intent classification to reduce Gemini usage

## Main endpoints

- `POST /worker/chat`
- `GET /worker/health`
- `POST /chat`
- `POST /chat/stream`
- `GET /health`
- `GET /health/db`

`/worker/chat` is the stable endpoint intended for the C# gateway.

## Quick start

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

## Environment

Create `.env` with at least:

```env
SUPABASE_URL=
SUPABASE_KEY=
POSTGRES_URL=
GOOGLE_API_KEY=
LLM_MODEL=gemini-2.5-flash
EMBEDDING_MODEL=models/gemini-embedding-001
APP_NAME=Menu Green
DEBUG=true
SERVE_FRONTEND=false
ENABLE_TRAINING_ENDPOINT=false
WORKER_TIMEOUT_SECONDS=120
```

Notes:

- `SERVE_FRONTEND=false` keeps the API in worker mode
- `POSTGRES_URL` is optional and only used for LangGraph persistence
- backend should use a Supabase server-side key, not a publishable key

## Database setup

Run the unified bootstrap SQL:

- [database_setup.sql](/D:/EXE/Model_RAG_MenuGreen/database_setup.sql)

Optional dev-only patch:

- [fix_rls.sql](/D:/EXE/Model_RAG_MenuGreen/fix_rls.sql)

## ONNX bundle

Train and export:

```powershell
python -X utf8 training\generate_dataset.py
python -X utf8 training\train_intent_classifier.py
python -X utf8 training\export_onnx.py
```

The export script creates:

- `models/intent_onnx/`
- `dist/intent_onnx_runtime.zip`

Model binaries are ignored from git because GitHub blocks files larger than
100 MB.

Bundle instructions:

- [MODEL_BUNDLE_SETUP.md](/D:/EXE/Model_RAG_MenuGreen/MODEL_BUNDLE_SETUP.md)

## C# gateway sample

Sample ASP.NET Core integration lives in:

- [samples/csharp-gateway/README.md](/D:/EXE/Model_RAG_MenuGreen/samples/csharp-gateway/README.md)
- [samples/csharp-gateway/Contracts/AiWorkerDtos.cs](/D:/EXE/Model_RAG_MenuGreen/samples/csharp-gateway/Contracts/AiWorkerDtos.cs)
- [samples/csharp-gateway/Services/AiWorkerClient.cs](/D:/EXE/Model_RAG_MenuGreen/samples/csharp-gateway/Services/AiWorkerClient.cs)
- [samples/csharp-gateway/Controllers/AssistantController.cs](/D:/EXE/Model_RAG_MenuGreen/samples/csharp-gateway/Controllers/AssistantController.cs)

## Tests

```powershell
D:\EXE\Model_RAG_MenuGreen\.venv\Scripts\python.exe -m pytest tests\test_nutrition.py tests\test_orchestrator.py -q
```
