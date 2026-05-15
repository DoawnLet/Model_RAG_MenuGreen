"""
Review queue logging for continual-learning style retraining.

The queue stores difficult requests as JSONL records that can later be reviewed
and promoted into the training dataset.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from app.core.config import get_settings


def append_review_case(record: dict[str, Any]) -> bool:
    settings = get_settings()
    if not settings.enable_review_queue:
        return False

    output_path = settings.review_queue_path
    parent = os.path.dirname(output_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    payload = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        **record,
    }

    with open(output_path, "a", encoding="utf-8") as file:
        file.write(json.dumps(payload, ensure_ascii=False) + "\n")

    return True
