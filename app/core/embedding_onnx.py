"""
app/core/embedding_onnx.py

ONNX-based Embedding thay thế Gemini Embedding API.
Sử dụng BAAI/bge-m3 — multilingual model, tốt cho tiếng Việt.
Không cần API key, không tốn token.

Sử dụng:
    from app.core.embedding_onnx import get_embedding, is_onnx_available
    vector = await get_embedding("Phở bò ngon")
"""

import logging
import numpy as np
import asyncio

logger = logging.getLogger(__name__)

# ONNX model path — download từ HuggingFace lần đầu, cache lại
ONNX_EMBEDDING_MODEL = "BAAI/bge-m3"
_model = None
_tokenizer = None
_use_onnx = None  # None = chưa kiểm tra, True/False sau khi check


def _load_model():
    """Load ONNX embedding model (lazy, load 1 lần)."""
    global _model, _tokenizer, _use_onnx

    if _use_onnx is not None:
        return _use_onnx

    try:
        from optimum.onnxruntime import ORTModelForFeatureExtraction
        from transformers import AutoTokenizer

        logger.info(f"🔄 Loading ONNX embedding model: {ONNX_EMBEDDING_MODEL}")
        _tokenizer = AutoTokenizer.from_pretrained(ONNX_EMBEDDING_MODEL)
        _model = ORTModelForFeatureExtraction.from_pretrained(
            ONNX_EMBEDDING_MODEL,
            export=True,  # Auto-export nếu chưa có .onnx cache
        )
        _use_onnx = True
        logger.info("✅ ONNX embedding model loaded")
        return True

    except ImportError:
        logger.warning("⚠️ optimum/onnxruntime not installed. Falling back to Gemini.")
        _use_onnx = False
        return False
    except Exception as e:
        logger.warning(f"⚠️ Could not load ONNX embedding: {e}. Falling back to Gemini.")
        _use_onnx = False
        return False


def is_onnx_available() -> bool:
    """Check xem ONNX embedding model có sẵn không."""
    return _load_model()


def _mean_pooling(model_output, attention_mask) -> np.ndarray:
    """Mean pooling để lấy sentence embedding từ token embeddings."""
    # model_output là numpy array [batch, seq_len, hidden_size]
    token_embeddings = model_output[0]  # First element = token embeddings

    # Expand attention mask
    mask = np.expand_dims(attention_mask, axis=-1).astype(np.float32)

    # Apply mask và tính mean
    sum_embeddings = np.sum(token_embeddings * mask, axis=1)
    sum_mask = np.clip(np.sum(mask, axis=1), a_min=1e-9, a_max=None)
    return sum_embeddings / sum_mask


def _normalize(v: np.ndarray) -> np.ndarray:
    """L2 normalize vector."""
    norm = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.clip(norm, a_min=1e-9, a_max=None)


def embed_text_onnx(text: str) -> list[float]:
    """
    Tạo embedding vector bằng ONNX (đồng bộ).

    Returns:
        List of floats (1024D cho BGE-M3)
    """
    if not _load_model() or _tokenizer is None or _model is None:
        raise RuntimeError("ONNX model not available")

    inputs = _tokenizer(
        text,
        max_length=512,
        padding=True,
        truncation=True,
        return_tensors="np",
    )

    outputs = _model(
        input_ids=inputs["input_ids"],
        attention_mask=inputs["attention_mask"],
    )

    embedding = _mean_pooling(outputs, inputs["attention_mask"])
    embedding = _normalize(embedding)
    return embedding[0].tolist()


async def get_embedding_onnx(text: str) -> list[float]:
    """Async wrapper cho ONNX embedding."""
    return await asyncio.to_thread(embed_text_onnx, text)


async def get_embedding(text: str) -> list[float]:
    """
    Smart embedding: dùng ONNX nếu có, fallback Gemini.
    Drop-in replacement cho SupabaseClient.create_embedding().
    """
    if is_onnx_available():
        try:
            return await get_embedding_onnx(text)
        except Exception as e:
            logger.warning(f"[ONNX Embedding] Failed: {e}. Falling back to Gemini.")

    # Fallback to Gemini
    from app.core.supabase_client import SupabaseClient

    return await SupabaseClient.create_embedding_gemini(text)
