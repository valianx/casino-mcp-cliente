"""
Utilities for MCP client tools including logging and timing functionality.
"""
import json
import time
from typing import Any, Dict
from contextlib import contextmanager

def json_log(level: str, message: str, **kwargs) -> None:
    """
    Log a message in JSON format with additional context.
    
    Args:
        level: Log level (info, warning, error, debug)
        message: Log message
        **kwargs: Additional context to include in the log
    """
    log_entry = {
        "timestamp": time.time(),
        "level": level.upper(),
        "message": message,
        **kwargs
    }
    print(json.dumps(log_entry))

@contextmanager
def timed(operation_name: str, **kwargs):
    """
    Context manager to time operations and log the duration.
    
    Args:
        operation_name: Name of the operation being timed
        **kwargs: Additional context to include in the log
    """
    start_time = time.time()
    try:
        yield
    finally:
        duration_ms = (time.time() - start_time) * 1000
        json_log("info", f"Operation completed", 
                operation=operation_name, 
                duration_ms=round(duration_ms, 2),
                **kwargs)
