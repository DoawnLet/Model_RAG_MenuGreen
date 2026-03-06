"""
app/core/intent_classifier_onnx.py

ONNX-based Intent Classifier thay thế Gemini API call.
Drop-in replacement cho phần classify_intent trong orchestrator.py

Sử dụng:
    from app.core.intent_classifier_onnx import ONNXIntentClassifier
    classifier = ONNXIntentClassifier()
    intent = classifier.predict("Tìm món ăn với cà chua")  # → "recipe_search"
"""

import json
import os
import logging
import numpy as np
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)

# Path tới ONNX model (đặt trong thư mục models/)
DEFAULT_MODEL_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "models", "intent_onnx"
)


class ONNXIntentClassifier:
    """
    Intent Classifier chạy locally với ONNX Runtime.
    Không cần API key, không cần internet, latency ~20ms.
    """

    def __init__(self, model_path: str = DEFAULT_MODEL_PATH):
        self.model_path = os.path.abspath(model_path)
        self._session = None
        self._tokenizer = None
        self._label_config = None
        self._load()

    def _load(self):
        """Load ONNX Session và Tokenizer."""
        try:
            import onnxruntime as ort
            from transformers import AutoTokenizer

            onnx_path = os.path.join(self.model_path, "model.onnx")
            label_path = os.path.join(self.model_path, "label_config.json")

            if not os.path.exists(onnx_path):
                raise FileNotFoundError(
                    f"ONNX model not found at {onnx_path}. "
                    "Chạy training/export_onnx.py trước!"
                )

            # Load label config
            with open(label_path, "r") as f:
                self._label_config = json.load(f)

            # Load tokenizer
            self._tokenizer = AutoTokenizer.from_pretrained(self.model_path)

            # Load ONNX session (CPU)
            sess_options = ort.SessionOptions()
            sess_options.intra_op_num_threads = 4  # Tối ưu CPU
            sess_options.graph_optimization_level = (
                ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            )

            self._session = ort.InferenceSession(
                onnx_path,
                sess_options=sess_options,
                providers=["CPUExecutionProvider"],
            )

            logger.info(f"✅ ONNX Intent Classifier loaded from {self.model_path}")
            logger.info(f"   Labels: {list(self._label_config['label_map'].keys())}")

        except ImportError as e:
            logger.error(f"❌ Missing dependency: {e}")
            logger.error("Run: pip install onnxruntime transformers")
            raise
        except Exception as e:
            logger.error(f"❌ Failed to load ONNX model: {e}")
            raise

    def _softmax(self, x: np.ndarray) -> np.ndarray:
        e = np.exp(x - np.max(x))
        return e / e.sum()

    def predict(self, text: str, threshold: float = 0.5) -> str:
        """
        Predict intent từ text.

        Args:
            text: Input text của user
            threshold: Nếu max confidence < threshold → trả "general"

        Returns:
            Intent string (vd: "recipe_search", "nutrition_calc", ...)
        """
        result = self.predict_with_score(text)
        if result["score"] < threshold:
            return "general"
        return result["label"]

    def predict_with_score(self, text: str) -> dict:
        """
        Predict với đầy đủ thông tin confidence.

        Returns dict:
            {
                "label": "recipe_search",
                "label_id": 0,
                "score": 0.97,
                "all_scores": {"recipe_search": 0.97, "general": 0.02, ...}
            }
        """
        max_length = self._label_config.get("max_length", 128)

        # Tokenize
        inputs = self._tokenizer(
            text,
            max_length=max_length,
            padding="max_length",
            truncation=True,
            return_tensors="np",
        )

        # ONNX inference
        outputs = self._session.run(
            None,
            {
                "input_ids": inputs["input_ids"].astype(np.int64),
                "attention_mask": inputs["attention_mask"].astype(np.int64),
            },
        )

        logits = outputs[0][0]
        probs = self._softmax(logits)
        pred_id = int(np.argmax(probs))

        id2label = self._label_config["id2label"]
        label_names = [id2label[str(i)] for i in range(len(id2label))]

        return {
            "label": label_names[pred_id],
            "label_id": pred_id,
            "score": float(probs[pred_id]),
            "all_scores": {
                name: float(probs[i]) for i, name in enumerate(label_names)
            },
        }

    def is_available(self) -> bool:
        """Check nếu model đã load thành công."""
        return self._session is not None


# ======================================================
# Singleton (load 1 lần duy nhất)
# ======================================================

_classifier_instance: Optional[ONNXIntentClassifier] = None


def get_onnx_classifier() -> Optional[ONNXIntentClassifier]:
    """
    Return singleton ONNX classifier.
    Return None nếu model chưa được export.
    """
    global _classifier_instance
    if _classifier_instance is None:
        model_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "models", "intent_onnx"
        )
        if not os.path.exists(os.path.join(model_path, "model.onnx")):
            logger.warning(
                "⚠️  ONNX model not found. "
                "Falling back to Gemini API for intent classification. "
                "Run training/export_onnx.py to enable local inference."
            )
            return None
        try:
            _classifier_instance = ONNXIntentClassifier(model_path)
        except Exception as e:
            logger.error(f"❌ Could not load ONNX classifier: {e}")
            return None
    return _classifier_instance
