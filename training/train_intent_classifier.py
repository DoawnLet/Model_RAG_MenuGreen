"""
Train the Menu Green intent classifier.

Run:
    python -X utf8 training/train_intent_classifier.py
"""

from __future__ import annotations

import json
import os
from collections import Counter

import numpy as np
import torch
from sklearn.metrics import accuracy_score, classification_report, f1_score
from torch.utils.data import Dataset
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    EarlyStoppingCallback,
    Trainer,
    TrainingArguments,
    pipeline,
)

print("Imports done")
print(f"PyTorch version: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")


CONFIG = {
    # Smaller multilingual backbone than xlm-roberta-base.
    # Better fit for server CPU inference and later mobile-friendly export.
    "model_name": "microsoft/Multilingual-MiniLM-L12-H384",
    "max_length": 96,
    "batch_size": 16,
    "num_epochs": 12,
    "learning_rate": 3e-5,
    "warmup_ratio": 0.1,
    "weight_decay": 0.01,
    "seed": 42,
    "output_dir": "./menu_green_intent_model",
    "dataset_path": "training/intent_dataset.json",
}

print("\nConfig:")
for key, value in CONFIG.items():
    print(f"  {key}: {value}")


with open(CONFIG["dataset_path"], "r", encoding="utf-8") as file:
    data = json.load(file)

train_data = data["train"]
val_data = data["val"]
label_map = data["label_map"]
label_names = [label for label, _ in sorted(label_map.items(), key=lambda item: item[1])]

CONFIG["num_labels"] = len(label_names)

print("\nDataset loaded:")
print(f"  Train: {len(train_data)} samples")
print(f"  Val:   {len(val_data)} samples")
print(f"  Labels: {label_names}")

train_counts = Counter(sample["label_name"] for sample in train_data)
val_counts = Counter(sample["label_name"] for sample in val_data)
print("\nClass distribution:")
for label_name in label_names:
    print(
        f"  {label_name:<20} train={train_counts.get(label_name, 0):<3} "
        f"val={val_counts.get(label_name, 0):<3}"
    )


print(f"\nLoading tokenizer: {CONFIG['model_name']}")
tokenizer = AutoTokenizer.from_pretrained(CONFIG["model_name"])


class IntentDataset(Dataset):
    def __init__(self, samples, model_tokenizer, max_length=96):
        self.samples = samples
        self.tokenizer = model_tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, index):
        item = self.samples[index]
        encoding = self.tokenizer(
            item["text"],
            max_length=self.max_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )
        return {
            "input_ids": encoding["input_ids"].squeeze(0),
            "attention_mask": encoding["attention_mask"].squeeze(0),
            "labels": torch.tensor(item["label"], dtype=torch.long),
        }


train_dataset = IntentDataset(train_data, tokenizer, CONFIG["max_length"])
val_dataset = IntentDataset(val_data, tokenizer, CONFIG["max_length"])

print(f"Datasets created: {len(train_dataset)} train, {len(val_dataset)} val")


print(f"\nLoading model: {CONFIG['model_name']}")
model = AutoModelForSequenceClassification.from_pretrained(
    CONFIG["model_name"],
    num_labels=CONFIG["num_labels"],
    id2label={index: name for index, name in enumerate(label_names)},
    label2id={name: index for index, name in enumerate(label_names)},
)

total_params = sum(parameter.numel() for parameter in model.parameters())
print(f"Model loaded: {total_params / 1e6:.1f}M parameters")


training_args = TrainingArguments(
    output_dir=CONFIG["output_dir"],
    num_train_epochs=CONFIG["num_epochs"],
    per_device_train_batch_size=CONFIG["batch_size"],
    per_device_eval_batch_size=CONFIG["batch_size"],
    warmup_ratio=CONFIG["warmup_ratio"],
    weight_decay=CONFIG["weight_decay"],
    learning_rate=CONFIG["learning_rate"],
    logging_steps=25,
    eval_strategy="epoch",
    save_strategy="epoch",
    save_total_limit=2,
    load_best_model_at_end=True,
    metric_for_best_model="macro_f1",
    greater_is_better=True,
    report_to="none",
    fp16=torch.cuda.is_available(),
    push_to_hub=False,
    seed=CONFIG["seed"],
)


def compute_metrics(eval_pred):
    logits, labels = eval_pred
    predictions = np.argmax(logits, axis=-1)
    return {
        "accuracy": accuracy_score(labels, predictions),
        "macro_f1": f1_score(labels, predictions, average="macro"),
        "weighted_f1": f1_score(labels, predictions, average="weighted"),
    }


print("\nStarting training...")
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=train_dataset,
    eval_dataset=val_dataset,
    compute_metrics=compute_metrics,
    callbacks=[EarlyStoppingCallback(early_stopping_patience=3)],
)
trainer.train()
print("\nTraining complete")


print("\nEvaluation on validation set:")
predictions_output = trainer.predict(val_dataset)
predictions = np.argmax(predictions_output.predictions, axis=-1)
labels = predictions_output.label_ids

print(classification_report(labels, predictions, target_names=label_names, digits=4))
accuracy = accuracy_score(labels, predictions)
macro_f1 = f1_score(labels, predictions, average="macro")
weighted_f1 = f1_score(labels, predictions, average="weighted")
print(f"Overall Accuracy: {accuracy:.4f} ({accuracy * 100:.2f}%)")
print(f"Macro F1:         {macro_f1:.4f}")
print(f"Weighted F1:      {weighted_f1:.4f}")


save_path = os.path.join(CONFIG["output_dir"], "best")
trainer.save_model(save_path)
tokenizer.save_pretrained(save_path)

label_config = {
    "label_map": {name: index for index, name in enumerate(label_names)},
    "id2label": {str(index): name for index, name in enumerate(label_names)},
    "num_labels": len(label_names),
    "model_name": CONFIG["model_name"],
    "max_length": CONFIG["max_length"],
}
with open(os.path.join(save_path, "label_config.json"), "w", encoding="utf-8") as file:
    json.dump(label_config, file, ensure_ascii=False, indent=2)

print(f"\nModel saved to: {save_path}")
print("Files:")
for file_name in sorted(os.listdir(save_path)):
    size_mb = os.path.getsize(os.path.join(save_path, file_name)) / (1024 * 1024)
    print(f"  {file_name:<40} {size_mb:.1f} MB")


print("\nQuick inference test:")
test_cases = [
    "Tìm món ăn với cà chua",
    "Tính BMR cho tôi",
    "Nguyên liệu nào sắp hết hạn?",
    "Lên thực đơn 7 ngày",
    "https://cookpad.com/vn/recipe/123",
    "Phở bò bao nhiêu calo?",
    "Ăn gì tốt cho sức khỏe?",
    "Thời tiết hôm nay thế nào?",
]

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

print("\nDone. Next: run export_onnx.py to export to ONNX.")
