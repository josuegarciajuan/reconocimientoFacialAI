"""Allowlisted runtime path components."""
import re

_SAFE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")

def safe_component(value: object) -> str:
    value = str(value)
    if not _SAFE.fullmatch(value):
        raise ValueError("invalid path component")
    return value
