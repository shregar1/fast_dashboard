"""Dashboard embed providers (Metabase, Grafana, …)."""

from __future__ import annotations

from .base import DashboardEmbedProvider
from .grafana import GrafanaEmbedProvider
from .looker import LookerEmbedProvider
from .metabase import MetabaseEmbedProvider
from .powerbi import PowerBIEmbedProvider

__all__ = [
    "DashboardEmbedProvider",
    "GrafanaEmbedProvider",
    "LookerEmbedProvider",
    "MetabaseEmbedProvider",
    "PowerBIEmbedProvider",
]
