"""Utility functions for AgentProjectBox."""

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any

from uuid6 import uuid7


def generate_id() -> str:
    """Generate a UUID7 string."""
    return str(uuid7())


def timestamp_now() -> datetime:
    """Current UTC datetime."""
    return datetime.now(timezone.utc)


def ensure_timezone(dt: datetime | None) -> datetime | None:
    """Ensure datetime has UTC timezone."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def hash_dict(data: dict[str, Any]) -> str:
    """Create deterministic hash of a dictionary."""
    json_str = json.dumps(data, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(json_str.encode()).hexdigest()


def sanitize_filename(name: str) -> str:
    """Sanitize string for safe filename use."""
    return re.sub(r'[^\w\-_.]', '_', name).strip('_')


def days_between(start: datetime, end: datetime) -> int:
    """Calculate days between two datetimes."""
    return (end - start).days


def parse_duration(duration_str: str) -> int:
    """Parse duration string to hours. Supports: '2d', '4h', '1w', '30m'."""
    duration_str = duration_str.strip().lower()
    
    if duration_str.endswith('w'):
        return int(duration_str[:-1]) * 7 * 8  # weeks to hours (8h days)
    if duration_str.endswith('d'):
        return int(duration_str[:-1]) * 8  # days to hours
    if duration_str.endswith('h'):
        return int(duration_str[:-1])
    if duration_str.endswith('m'):
        return int(duration_str[:-1]) // 60
    
    # Try to parse as float hours
    try:
        return int(float(duration_str))
    except ValueError:
        return 8  # default


def calculate_confidence_interval(
    estimates: list[float], 
    confidence: float = 0.8
) -> tuple[float, float]:
    """Calculate confidence interval from estimates."""
    if not estimates:
        return (0.0, 0.0)
    
    sorted_estimates = sorted(estimates)
    lower_idx = int(len(sorted_estimates) * (1 - confidence) / 2)
    upper_idx = int(len(sorted_estimates) * (1 + confidence) / 2)
    
    return (sorted_estimates[lower_idx], sorted_estimates[upper_idx])


def merge_nested_dicts(base: dict, update: dict) -> dict:
    """Deep merge two dictionaries."""
    result = base.copy()
    for key, value in update.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_nested_dicts(result[key], value)
        else:
            result[key] = value
    return result


def truncate_string(s: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate string to max_length."""
    if len(s) <= max_length:
        return s
    return s[:max_length - len(suffix)] + suffix


def chunk_list(lst: list, chunk_size: int) -> list[list]:
    """Split list into chunks."""
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]
