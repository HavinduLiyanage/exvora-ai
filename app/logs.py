"""Structured JSON logging for Exvora AI."""

import json
import time
from typing import Any, Dict
from datetime import datetime

def log_json(req_id: str, stage: str, **kwargs) -> None:
    """Log structured JSON with request ID and stage."""
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "req_id": req_id,
        "stage": stage,
        **kwargs
    }
    
    # Print as JSON line (one line per log entry)
    print(json.dumps(log_entry), flush=True)

def log_summary(req_id: str, total_ms: float, **kwargs) -> None:
    """Log request summary."""
    log_json(req_id, "summary", total_ms=total_ms, **kwargs)
