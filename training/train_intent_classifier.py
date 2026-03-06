# ============================================================
# train_intent_classifier.py
# Train Intent Classifier cho Menu Green
#
# Chạy trên: Kaggle / Google Colab (GPU T4 hoặc CPU đều được)
# Thời gian: ~10-15 phút với GPU, ~30 phút với CPU
#
# HƯỚNG DẪN:
# 1. Upload file này lên Kaggle/Colab
# 2. Upload intent_dataset.json vào cùng thư mục
# 3. Chạy từng cell (nếu .ipynb) hoặc python train_intent_classifier.py
# ============================================================

# ============================================================
# CELL 1: Install dependencies
# ============================================================
# !pip install transformers datasets scikit-learn optimum[exporters] onnxruntime -q

import json
import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    TrainingArguments,
    Trainer,
    EarlyStoppingCallback,
)
from sklearn.metrics import classification_report, accuracy_score
import os

print("✅ Imports done")
print(f"PyTorch version: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")


# ============================================================
# CELL 2: Config
# ============================================================

CONFIG = {
    # Model: XLM-RoBERTa base (tốt cho đa ngôn ngữ & tiếng Việt)
    # Thay thế: "vinai/phobert-base-v2" nếu chỉ cần tiếng Việt
    "model_name": "xlm-roberta-base",
    
    "num_labels": 7,
    "max_length": 128,
    "batch_size": 16,
    "num_epochs": 10,
    "learning_rate": 2e-5,
    "warmup_ratio": 0.1,
    "weight_decay": 0.01,
    
    "output_dir": "./menu_green_intent_model",
    "dataset_path": "./intent_dataset.json",
}

LABEL_NAMES = [
    "recipe_search",   # 0
    "nutrition_calc",  # 1
    "inventory_check", # 2
    "meal_plan",       # 3
    "web_browsing",    # 4
    "general",         # 5
    "unknown",         # 6
]

print(f"\n📋 Config:")
for k, v in CONFIG.items():
    print(f"  {k}: {v}")


# ============================================================
# CELL 3: Load Dataset
# ============================================================

with open(CONFIG["dataset_path"], "r", encoding="utf-8") as f:
    data = json.load(f)

train_data = data["train"]
val_data = data["val"]

print(f"\n📊 Dataset loaded:")
print(f"  Train: {len(train_data)} samples")
print(f"  Val:   {len(val_data)} samples")
print(f"  Labels: {LABEL_NAMES}")

# Per-class count
from collections import Counter
train_counts = Counter(s["label_name"] for s in train_data)
print("\nTrain class distribution:")
for cls in LABEL_NAMES:
    print(f"  {cls:<20} {train_counts.get(cls, 0)}")


# ============================================================
# CELL 4: Tokenizer & Dataset Class
# ============================================================

print(f"\n🔄 Loading tokenizer: {CONFIG['model_name']}")
tokenizer = AutoTokenizer.from_pretrained(CONFIG["model_name"])


class IntentDataset(Dataset):
    def __init__(self, samples, tokenizer, max_length=128):
        self.samples = samples
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        item = self.samples[idx]
        encoding = self.tokenizer(
            item["text"],
            max_length=self.max_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )
        return {
            "input_ids": encoding["input_ids"].squeeze(),
            "attention_mask": encoding["attention_mask"].squeeze(),
            "labels": torch.tensor(item["label"], dtype=torch.long),
        }


train_dataset = IntentDataset(train_data, tokenizer, CONFIG["max_length"])
val_dataset = IntentDataset(val_data, tokenizer, CONFIG["max_length"])

print(f"✅ Datasets created: {len(train_dataset)} train, {len(val_dataset)} val")


# ============================================================
# CELL 5: Load Model
# ============================================================

print(f"\n🤖 Loading model: {CONFIG['model_name']}")
model = AutoModelForSequenceClassification.from_pretrained(
    CONFIG["model_name"],
    num_labels=CONFIG["num_labels"],
    id2label={i: name for i, name in enumerate(LABEL_NAMES)},
    label2id={name: i for i, name in enumerate(LABEL_NAMES)},
)

total_params = sum(p.numel() for p in model.parameters())
print(f"✅ Model loaded: {total_params/1e6:.1f}M parameters")


# ============================================================
# CELL 6: Training Arguments
# ============================================================

training_args = TrainingArguments(
    output_dir=CONFIG["output_dir"],
    num_train_epochs=CONFIG["num_epochs"],
    per_device_train_batch_size=CONFIG["batch_size"],
    per_device_eval_batch_size=CONFIG["batch_size"],
    learning_rate=CONFIG["learning_rate"],
    warmup_ratio=CONFIG["warmup_ratio"],
    weight_decay=CONFIG["weight_decay"],
    
    evaluation_strategy="epoch",
    save_strategy="epoch",
    load_best_model_at_end=True,
    metric_for_best_model="accuracy",
    greater_is_better=True,
    
    logging_steps=10,
    fp16=torch.cuda.is_available(),  # Mixed precision nếu có GPU
    
    report_to="none",  # Tắt wandb
)


def compute_metrics(eval_pred):
    logits, labels = eval_pred
    predictions = np.argmax(logits, axis=-1)
    acc = accuracy_score(labels, predictions)
    return {"accuracy": acc}


# ============================================================
# CELL 7: Train!
# ============================================================

print("\n🚀 Starting training...")

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=train_dataset,
    eval_dataset=val_dataset,
    compute_metrics=compute_metrics,
    callbacks=[EarlyStoppingCallback(early_stopping_patience=3)],
)

trainer.train()

print("\n✅ Training complete!")


# ============================================================
# CELL 8: Evaluate & Report
# ============================================================

print("\n📊 Evaluation on validation set:")
predictions_output = trainer.predict(val_dataset)
preds = np.argmax(predictions_output.predictions, axis=-1)
labels = predictions_output.label_ids

print(classification_report(labels, preds, target_names=LABEL_NAMES))

acc = accuracy_score(labels, preds)
print(f"✅ Overall Accuracy: {acc:.4f} ({acc*100:.2f}%)")


# ============================================================
# CELL 9: Save Model
# ============================================================

save_path = CONFIG["output_dir"] + "/best"
trainer.save_model(save_path)
tokenizer.save_pretrained(save_path)

# Save label config for later use
label_config = {
    "label_map": {name: i for i, name in enumerate(LABEL_NAMES)},
    "id2label": {str(i): name for i, name in enumerate(LABEL_NAMES)},
    "num_labels": len(LABEL_NAMES),
}
with open(save_path + "/label_config.json", "w") as f:
    json.dump(label_config, f, indent=2)

print(f"\n💾 Model saved to: {save_path}")
print("Files:")
for f in os.listdir(save_path):
    size = os.path.getsize(os.path.join(save_path, f)) / (1024*1024)
    print(f"  {f:<40} {size:.1f} MB")


# ============================================================
# CELL 10: Quick Test
# ============================================================

print("\n🧪 Quick inference test:")

test_cases = [
    "Tìm món ăn với cà chua",
    "Tính BMR cho tôi",
    "Nguyên liệu nào sắp hết hạn?",
    "Lên thực đơn 7 ngày",
    "https://cookpad.com/vn/recipe/123",
    "Ăn gì tốt cho sức khỏe?",
    "Thời tiết hôm nay thế nào?",
]

from transformers import pipeline
classifier = pipeline(
    "text-classification",
    model=model,
    tokenizer=tokenizer,
    device=0 if torch.cuda.is_available() else -1,
)

print(f"\n{'Text':<45} {'Predicted':<20} {'Score'}")
print("-" * 80)
for text in test_cases:
    result = classifier(text)[0]
    print(f"{text:<45} {result['label']:<20} {result['score']:.3f}")


# ============================================================
# EXPORT TO ONNX → Chạy script export_onnx.py sau bước này
# ============================================================
print("\n✅ Done! Tiếp theo: chạy export_onnx.py để export sang ONNX")
