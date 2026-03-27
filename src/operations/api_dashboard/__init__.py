"""API Dashboard package.

Exports helpers used to register API samples that will be displayed
and exercised by the built-in API dashboard UI.
"""

from .registry import EndpointSample, register_endpoint_sample
from .router import router as ApiDashboardRouter

__all__ = ["EndpointSample", "register_endpoint_sample", "ApiDashboardRouter"]
