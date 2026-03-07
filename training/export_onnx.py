"""
export_onnx.py
Export trained model sang ONNX format
Chạy SAU khi train xong: python training/export_onnx.py

Output:
  models/intent_onnx/          ← folder chứa ONNX model
    model.onnx                 ← model weights
    tokenizer_config.json      ← tokenizer config
    vocab.json / sentencepiece
    label_config.json          ← mapping label id → tên
"""

import json
import os
import numpy as np

print("🔄 Loading dependencies...")
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from optimum.exporters.onnx import main_export
import onnxruntime as ort

# ============================================================
# Config
# ============================================================

TRAINED_MODEL_PATH = "./menu_green_intent_model/best"  # Output từ bước train
ONNX_OUTPUT_PATH   = "./models/intent_onnx"

LABEL_NAMES = [
    "recipe_search",
    "nutrition_calc",
    "inventory_check",
    "meal_plan",
    "web_browsing",
    "general",
    "unknown",
]

# ============================================================
# Step 1: Export sang ONNX
# ============================================================

print(f"\n📦 Exporting to ONNX...")
print(f"  Source: {TRAINED_MODEL_PATH}")
print(f"  Output: {ONNX_OUTPUT_PATH}")

os.makedirs(ONNX_OUTPUT_PATH, exist_ok=True)

# Optimum auto-export với optimization
main_export(
    model_name_or_path=TRAINED_MODEL_PATH,
    output=ONNX_OUTPUT_PATH,
    task="text-classification",
    optimize="O2",           # O1=basic, O2=extended, O3=aggressive (float16)
    monolith=True,           # Gộp thành 1 file model.onnx
)

print(f"\n✅ ONNX export done!")
print(f"Files in {ONNX_OUTPUT_PATH}:")
for f in sorted(os.listdir(ONNX_OUTPUT_PATH)):
    size_mb = os.path.getsize(os.path.join(ONNX_OUTPUT_PATH, f)) / (1024 * 1024)
    print(f"  {f:<40} {size_mb:.1f} MB")


# ============================================================
# Step 2: Verify ONNX model output
# ============================================================

print("\n🧪 Verifying ONNX model...")

tokenizer = AutoTokenizer.from_pretrained(ONNX_OUTPUT_PATH)
session = ort.InferenceSession(
    os.path.join(ONNX_OUTPUT_PATH, "model.onnx"),
    providers=["CPUExecutionProvider"],
)

def predict(text: str) -> dict:
    """Inference với ONNX Runtime."""
    inputs = tokenizer(
        text,
        max_length=128,
        padding="max_length",
        truncation=True,
        return_tensors="np",
    )
    outputs = session.run(
        None,
        {
            "input_ids": inputs["input_ids"].astype(np.int64),
            "attention_mask": inputs["attention_mask"].astype(np.int64),
        },
    )
    logits = outputs[0][0]
    probs = softmax(logits)
    pred_id = int(np.argmax(probs))
    return {
        "label": LABEL_NAMES[pred_id],
        "label_id": pred_id,
        "score": float(probs[pred_id]),
        "all_probs": {name: float(p) for name, p in zip(LABEL_NAMES, probs)},
    }

def softmax(x):
    e = np.exp(x - np.max(x))
    return e / e.sum()


# Test cases
test_cases = [
    ("Tìm món ăn với cà chua",          "recipe_search"),
    ("Tính BMR cho tôi",                 "nutrition_calc"),
    ("Nguyên liệu nào sắp hết hạn?",    "inventory_check"),
    ("Lên thực đơn 7 ngày giảm cân",    "meal_plan"),
    ("https://cookpad.com/vn/recipe/1", "web_browsing"),
    ("Ăn gì tốt cho tim mạch?",         "general"),
    ("Thời tiết hôm nay thế nào?",      "unknown"),
]

print(f"\n{'Text':<45} {'Expected':<20} {'Predicted':<20} {'Score':<8} {'OK?'}")
print("-" * 100)

correct = 0
for text, expected in test_cases:
    result = predict(text)
    ok = "✅" if result["label"] == expected else "❌"
    if result["label"] == expected:
        correct += 1
    print(f"{text:<45} {expected:<20} {result['label']:<20} {result['score']:.3f}   {ok}")

print(f"\n🎯 Accuracy: {correct}/{len(test_cases)} ({correct/len(test_cases)*100:.0f}%)")


# ============================================================
# Step 3: Benchmark latency
# ============================================================

import time

print("\n⏱️ Latency benchmark (100 calls):")
test_text = "Tìm công thức nấu phở bò ngon"
times = []

for _ in range(100):
    start = time.perf_counter()
    predict(test_text)
    times.append((time.perf_counter() - start) * 1000)

avg = np.mean(times)
p95 = np.percentile(times, 95)
print(f"  Average:  {avg:.1f} ms")
print(f"  P95:      {p95:.1f} ms")
print(f"  (Compare: Gemini API ~500-2000ms)")


# ============================================================
# Step 4: Save label config
# ============================================================

label_config = {
    "label_map": {name: i for i, name in enumerate(LABEL_NAMES)},
    "id2label": {str(i): name for i, name in enumerate(LABEL_NAMES)},
    "num_labels": len(LABEL_NAMES),
    "model_name": "xlm-roberta-base",
    "max_length": 128,
}

with open(os.path.join(ONNX_OUTPUT_PATH, "label_config.json"), "w") as f:
    json.dump(label_config, f, indent=2)

print(f"\n💾 Label config saved to {ONNX_OUTPUT_PATH}/label_config.json")

print("\n" + "="*60)
print("✅ ONNX Export Complete!")
print("="*60)
print(f"\nModel location: {ONNX_OUTPUT_PATH}/")
print("\nTiếp theo: Copy folder models/intent_onnx/ vào project")
print("và chạy: python training/test_onnx_integration.py")
