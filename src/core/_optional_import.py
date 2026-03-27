"""Optional import helper for optional dependencies."""

from __future__ import annotations

from importlib import import_module
from typing import Any, Tuple


def optional_import(
    module: str, attr: str | None = None
) -> Tuple[Any | None, Any | None]:
    """Execute optional_import operation.

    Args:
        module: The module parameter.
        attr: The attr parameter.

    Returns:
        The result of the operation.
    """
    try:
        mod = import_module(module)
    except Exception:
        return None, None
    if not attr:
        return mod, None
    current: Any = mod
    for part in attr.split("."):
        try:
            current = getattr(current, part)
        except AttributeError:
            return mod, None
    return mod, current
