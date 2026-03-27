"""Mock identity configuration - registered with dependency registry."""

from dataclasses import dataclass, field
from typing import List, Optional

# Register with registry on module load
try:
    from fast_dashboards.core.registry import registry

    _REGISTRY_AVAILABLE = True
except ImportError:
    _REGISTRY_AVAILABLE = False


@dataclass
class OAuthProviderConfig:
    """Represents the OAuthProviderConfig class."""

    enabled: bool = False
    client_id: str = ""
    client_secret: str = ""
    redirect_uri: str = ""


@dataclass
class SAMLConfig:
    """Represents the SAMLConfig class."""

    enabled: bool = False
    idp_metadata_url: str = ""
    acs_url: str = ""


@dataclass
class IdentityProvidersConfig:
    """Represents the IdentityProvidersConfig class."""

    google: OAuthProviderConfig = field(default_factory=OAuthProviderConfig)
    github: OAuthProviderConfig = field(default_factory=OAuthProviderConfig)
    azure_ad: OAuthProviderConfig = field(default_factory=OAuthProviderConfig)
    okta: OAuthProviderConfig = field(default_factory=OAuthProviderConfig)
    auth0: OAuthProviderConfig = field(default_factory=OAuthProviderConfig)
    saml: SAMLConfig = field(default_factory=SAMLConfig)


class IdentityProvidersConfiguration:
    """Represents the IdentityProvidersConfiguration class."""

    _instance: Optional["IdentityProvidersConfiguration"] = None

    @classmethod
    def instance(cls) -> "IdentityProvidersConfiguration":
        """Execute instance operation.

        Returns:
            The result of the operation.
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_config(self) -> IdentityProvidersConfig:
        """Execute get_config operation.

        Returns:
            The result of the operation.
        """
        return IdentityProvidersConfig()


# Auto-register with dependency registry
if _REGISTRY_AVAILABLE:
    registry.register_config("identity", IdentityProvidersConfiguration)
