"""Mock core.utils.optional_imports module."""

import importlib
from typing import Any, Tuple


class OptionalImports:
    """Mock OptionalImports - resolve optional third-party modules defensively."""

    @staticmethod
    def optional_import(
        module: str, attr: str | None = None
    ) -> Tuple[Any | None, Any | None]:
        """Import *module* and optionally retrieve *attr* from it.
        Returns (None, None) on failure, (module, None) if no attr,
        (module, getattr(module, attr)) if attr specified.
        """
        try:
            mod = importlib.import_module(module)
        except Exception:
            return None, None
        if attr is None:
            return mod, None
        try:
            return mod, getattr(mod, attr)
        except Exception:
            return mod, None
