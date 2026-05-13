"""
Local ONNX intent classifier used as a drop-in replacement for Gemini-based
intent classification.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_MODEL_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "models", "intent_onnx"
)


class ONNXIntentClassifier:
    """Run lightweight intent classification with ONNX Runtime."""

    def __init__(self, model_path: str = DEFAULT_MODEL_PATH):
        self.model_path = os.path.abspath(model_path)
        self._session = None
        self._tokenizer = None
        self._label_config = None
        self._input_names = set()
        self._load()

    def _load(self):
        try:
            import onnxruntime as ort
            from transformers import AutoTokenizer

            int8_path = os.path.join(self.model_path, "model.int8.onnx")
            fp32_path = os.path.join(self.model_path, "model.onnx")
            active_model_path = int8_path if os.path.exists(int8_path) else fp32_path
            label_path = os.path.join(self.model_path, "label_config.json")

            if not os.path.exists(active_model_path):
                raise FileNotFoundError(
                    f"ONNX model not found at {active_model_path}. "
                    "Run training/export_onnx.py first."
                )

            with open(label_path, "r", encoding="utf-8") as file:
                self._label_config = json.load(file)

            self._tokenizer = AutoTokenizer.from_pretrained(self.model_path)

            session_options = ort.SessionOptions()
            session_options.intra_op_num_threads = 4
            session_options.graph_optimization_level = (
                ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            )

            self._session = ort.InferenceSession(
                active_model_path,
                sess_options=session_options,
                providers=["CPUExecutionProvider"],
            )
            self._input_names = {node.name for node in self._session.get_inputs()}

            logger.info("ONNX intent classifier loaded successfully")
            logger.info("  path: %s", self.model_path)
            logger.info("  model: %s", os.path.basename(active_model_path))
            logger.info("  labels: %s", list(self._label_config["label_map"].keys()))

        except ImportError as exc:
            logger.error("Missing dependency for ONNX classifier: %s", exc)
            logger.error("Run: pip install onnxruntime transformers")
            raise
        except Exception as exc:
            logger.error("Failed to load ONNX classifier: %s", exc)
            raise

    @staticmethod
    def _softmax(values: np.ndarray) -> np.ndarray:
        exp_values = np.exp(values - np.max(values))
        return exp_values / exp_values.sum()

    def _build_feed_dict(self, inputs: dict) -> dict:
        feed = {
            "input_ids": inputs["input_ids"].astype(np.int64),
            "attention_mask": inputs["attention_mask"].astype(np.int64),
        }
        if "token_type_ids" in inputs and "token_type_ids" in self._input_names:
            feed["token_type_ids"] = inputs["token_type_ids"].astype(np.int64)
        return feed

    def predict(self, text: str, threshold: float = 0.5) -> str:
        result = self.predict_with_score(text)
        if result["score"] < threshold:
            return "general"
        return result["label"]

    def predict_with_score(self, text: str) -> dict:
        max_length = self._label_config.get("max_length", 96)
        inputs = self._tokenizer(
            text,
            max_length=max_length,
            padding="max_length",
            truncation=True,
            return_token_type_ids=True,
            return_tensors="np",
        )

        outputs = self._session.run(None, self._build_feed_dict(inputs))
        logits = outputs[0][0]
        probabilities = self._softmax(logits)
        prediction_id = int(np.argmax(probabilities))

        id2label = self._label_config["id2label"]
        label_names = [id2label[str(index)] for index in range(len(id2label))]

        return {
            "label": label_names[prediction_id],
            "label_id": prediction_id,
            "score": float(probabilities[prediction_id]),
            "all_scores": {
                label_name: float(probabilities[index])
                for index, label_name in enumerate(label_names)
            },
        }

    def is_available(self) -> bool:
        return self._session is not None


_classifier_instance: Optional[ONNXIntentClassifier] = None


def get_onnx_classifier() -> Optional[ONNXIntentClassifier]:
    global _classifier_instance
    if _classifier_instance is None:
        model_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "models", "intent_onnx"
        )
        if not os.path.exists(os.path.join(model_path, "model.onnx")) and not os.path.exists(
            os.path.join(model_path, "model.int8.onnx")
        ):
            logger.warning(
                "ONNX model not found. Falling back to Gemini API for intent classification. "
                "Run training/export_onnx.py to enable local inference."
            )
            return None
        try:
            _classifier_instance = ONNXIntentClassifier(model_path)
        except Exception as exc:
            logger.error("Could not load ONNX classifier: %s", exc)
            return None
    return _classifier_instance
