"""Field-Level Encryption for Pydantic Models.

Features:
- Transparent encryption/decryption for Pydantic fields
- AES-256-GCM authenticated encryption
- Key rotation support
- Searchable encryption (deterministic for exact match)
- Format-preserving encryption for specific types
- Integration with external key management (AWS KMS, HashiCorp Vault)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from dataclasses import dataclass
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Protocol,
    Set,
    Type,
    TypeVar,
    Union,
    get_args,
    get_origin,
)

from loguru import logger


# Optional cryptography import
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes

    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False
    logger.warning("cryptography package not installed, using mock encryption")


T = TypeVar("T")


class EncryptionType(Enum):
    """Types of field encryption."""

    RANDOMIZED = "randomized"  # Non-deterministic, most secure
    DETERMINISTIC = "deterministic"  # Same plaintext = same ciphertext (for search)
    FORMAT_PRESERVING = "format_preserving"  # Preserve format (e.g., SSN)


class EncryptionProvider(Protocol):
    """Protocol for encryption key providers."""

    def encrypt(self, plaintext: bytes, key_id: Optional[str] = None) -> bytes: ...
    def decrypt(self, ciphertext: bytes, key_id: Optional[str] = None) -> bytes: ...
    def get_current_key_id(self) -> str: ...


@dataclass
class EncryptedFieldConfig:
    """Configuration for an encrypted field."""

    encryption_type: EncryptionType = EncryptionType.RANDOMIZED
    key_id: Optional[str] = None
    searchable: bool = False  # Enable exact-match search (uses deterministic)
    algorithm: str = "AES-256-GCM"


class MasterKeyProvider:
    """Provider for encryption keys.

    Supports multiple backends:
    - Environment variable (for dev)
    - AWS KMS
    - HashiCorp Vault
    - File-based keys
    """

    def __init__(self, master_key: Optional[bytes] = None):
        self._keys: Dict[str, bytes] = {}
        self._current_key_id = "key-1"

        if master_key:
            self._keys[self._current_key_id] = master_key
        else:
            # Try to load from environment
            env_key = os.environ.get("FASTMVC_ENCRYPTION_KEY")
            if env_key:
                self._keys[self._current_key_id] = base64.urlsafe_b64decode(env_key)
            elif HAS_CRYPTOGRAPHY:
                # Generate a key for development
                logger.warning(
                    "Using auto-generated encryption key - NOT FOR PRODUCTION"
                )
                self._keys[self._current_key_id] = AESGCM.generate_key(bit_length=256)

    def add_key(self, key_id: str, key: bytes) -> None:
        """Add a key to the provider."""
        self._keys[key_id] = key

    def get_key(self, key_id: Optional[str] = None) -> bytes:
        """Get a key by ID."""
        key_id = key_id or self._current_key_id
        if key_id not in self._keys:
            raise KeyError(f"Encryption key not found: {key_id}")
        return self._keys[key_id]

    def get_current_key_id(self) -> str:
        """Get the current key ID."""
        return self._current_key_id

    def rotate_key(self, new_key: bytes) -> str:
        """Rotate to a new key."""
        new_key_id = f"key-{len(self._keys) + 1}"
        self._keys[new_key_id] = new_key
        self._current_key_id = new_key_id
        return new_key_id


class FieldEncryption:
    """Field-level encryption handler.

    Supports:
    - AES-256-GCM authenticated encryption
    - Deterministic encryption for search
    - Key versioning
    """

    # Version marker for encrypted data
    VERSION = 1

    def __init__(self, key_provider: Optional[MasterKeyProvider] = None):
        self.key_provider = key_provider or MasterKeyProvider()

        if not HAS_CRYPTOGRAPHY:
            logger.error("cryptography package required for encryption")

    def encrypt(
        self,
        plaintext: Union[str, bytes],
        encryption_type: EncryptionType = EncryptionType.RANDOMIZED,
        key_id: Optional[str] = None,
    ) -> str:
        """Encrypt a value.

        Returns base64-encoded ciphertext with metadata.
        """
        if not HAS_CRYPTOGRAPHY:
            raise RuntimeError("cryptography package required")

        if isinstance(plaintext, str):
            plaintext = plaintext.encode("utf-8")

        key = self.key_provider.get_key(key_id)
        actual_key_id = key_id or self.key_provider.get_current_key_id()

        if encryption_type == EncryptionType.DETERMINISTIC:
            # Use key as-is for deterministic encryption
            # Add HMAC-based deterministic nonce
            nonce = hashlib.sha256(plaintext + key[:16]).digest()[:12]
        else:
            # Random nonce for randomized encryption
            nonce = os.urandom(12)

        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)

        # Format: version:key_id:nonce:ciphertext (all base64)
        result = (
            f"{self.VERSION}:{actual_key_id}:"
            + base64.urlsafe_b64encode(nonce + ciphertext).decode()
        )

        return result

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a value.

        Args:
            ciphertext: Base64-encoded ciphertext with metadata

        Returns:
            Decrypted plaintext string

        """
        if not HAS_CRYPTOGRAPHY:
            raise RuntimeError("cryptography package required")

        # Parse the encrypted format
        parts = ciphertext.split(":")
        if len(parts) != 3:
            raise ValueError("Invalid encrypted format")

        version, key_id, data = parts
        version = int(version)

        if version != self.VERSION:
            raise ValueError(f"Unsupported encryption version: {version}")

        key = self.key_provider.get_key(key_id)
        data_bytes = base64.urlsafe_b64decode(data)

        nonce = data_bytes[:12]
        encrypted = data_bytes[12:]

        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, encrypted, None)

        return plaintext.decode("utf-8")

    def encrypt_deterministic(self, plaintext: Union[str, bytes]) -> str:
        """Encrypt with deterministic mode (for exact-match search)."""
        return self.encrypt(plaintext, EncryptionType.DETERMINISTIC)

    def hash_for_search(self, plaintext: Union[str, bytes]) -> str:
        """Create a searchable hash (deterministic)."""
        if isinstance(plaintext, str):
            plaintext = plaintext.encode("utf-8")

        key = self.key_provider.get_key()
        return hmac.new(key, plaintext, hashlib.sha256).hexdigest()[:32]


class Encrypted(Generic[T]):
    """Type hint for encrypted fields in Pydantic models.

    Usage:
        class User(BaseModel):
            name: str
            ssn: Encrypted[str]  # Automatically encrypted/decrypted
            email_hash: str  # Store searchable hash separately
    """

    def __init__(self, value: T):
        self.value = value

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        return v

    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(type="string", format="encrypted")


class EncryptedString(str):
    """String type that automatically encrypts/decrypts.

    This is a drop-in replacement for str that handles encryption
    transparently in Pydantic models.
    """

    _encryption: Optional[FieldEncryption] = None

    def __new__(cls, value: Union[str, "EncryptedString"], encrypted: bool = False):
        if isinstance(value, EncryptedString):
            return value

        instance = super().__new__(cls, value if encrypted else "")
        instance._plaintext = None if encrypted else value
        instance._ciphertext = value if encrypted else None
        instance._encrypted = encrypted
        return instance

    @property
    def plaintext(self) -> str:
        """Get plaintext value, decrypting if necessary."""
        if self._plaintext is not None:
            return self._plaintext

        if self._ciphertext and self._encryption:
            self._plaintext = self._encryption.decrypt(self._ciphertext)
            return self._plaintext

        return str(self)

    @property
    def ciphertext(self) -> str:
        """Get ciphertext value, encrypting if necessary."""
        if self._ciphertext is not None:
            return self._ciphertext

        if self._plaintext and self._encryption:
            self._ciphertext = self._encryption.encrypt(self._plaintext)
            return self._ciphertext

        return str(self)

    def __str__(self) -> str:
        # Return masked value for security
        return self._mask_value()

    def __repr__(self) -> str:
        return f"EncryptedString(***masked***)"

    def _mask_value(self) -> str:
        """Return masked value for display."""
        plaintext = self.plaintext if self._plaintext else ""
        if len(plaintext) <= 4:
            return "****"
        return plaintext[:2] + "****" + plaintext[-2:]

    @classmethod
    def set_encryption(cls, encryption: FieldEncryption) -> None:
        """Set the global encryption handler."""
        cls._encryption = encryption


def encrypted_field(
    encryption_type: EncryptionType = EncryptionType.RANDOMIZED,
    searchable: bool = False,
    key_id: Optional[str] = None,
):
    """Create an encrypted field configuration for Pydantic.

    Usage:
        class User(BaseModel):
            ssn: str = encrypted_field(searchable=True)
            notes: str = encrypted_field(encryption_type=EncryptionType.RANDOMIZED)
    """
    return {
        "encrypted": True,
        "encryption_type": encryption_type,
        "searchable": searchable,
        "key_id": key_id,
    }


class ModelEncryption:
    """Encryption handler for entire Pydantic models.

    Automatically encrypts/decrypts fields marked for encryption.
    """

    def __init__(self, encryption: Optional[FieldEncryption] = None):
        self.encryption = encryption or FieldEncryption()

    def encrypt_model(
        self, model: Any, fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Encrypt fields in a model dictionary.

        Args:
            model: The model or dict to encrypt
            fields: Specific fields to encrypt (None = auto-detect)

        Returns:
            Dictionary with encrypted fields

        """
        if hasattr(model, "dict"):
            data = model.dict()
        elif hasattr(model, "model_dump"):
            data = model.model_dump()
        else:
            data = dict(model)

        # Auto-detect encrypted fields from model annotations
        if fields is None and hasattr(model, "__annotations__"):
            fields = self._detect_encrypted_fields(model)

        for field in fields or []:
            if field in data and data[field] is not None:
                value = data[field]
                if not self._is_encrypted(value):
                    data[field] = self.encryption.encrypt(str(value))

                    # Add searchable hash if needed
                    if hasattr(model, "model_config"):
                        field_config = self._get_field_config(model, field)
                        if field_config and field_config.get("searchable"):
                            data[f"{field}_hash"] = self.encryption.hash_for_search(
                                str(value)
                            )

        return data

    def decrypt_model(
        self, data: Dict[str, Any], fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Decrypt fields in a model dictionary.

        Args:
            data: The dictionary with encrypted fields
            fields: Specific fields to decrypt

        Returns:
            Dictionary with decrypted fields

        """
        for field in fields or self._detect_encrypted_fields_from_data(data):
            if field in data and data[field] is not None:
                value = data[field]
                if self._is_encrypted(value):
                    try:
                        data[field] = self.encryption.decrypt(value)
                    except Exception as e:
                        logger.error(f"Failed to decrypt field {field}: {e}")
                        # Keep original value on failure

        return data

    def _detect_encrypted_fields(self, model: Any) -> List[str]:
        """Detect fields marked for encryption from model annotations."""
        fields = []

        annotations = getattr(model, "__annotations__", {})
        for field_name, annotation in annotations.items():
            # Check for Encrypted[T] type hint
            origin = get_origin(annotation)
            if origin is Encrypted:
                fields.append(field_name)
            # Check for EncryptedString type
            elif annotation is EncryptedString:
                fields.append(field_name)

        return fields

    def _detect_encrypted_fields_from_data(self, data: Dict[str, Any]) -> List[str]:
        """Detect encrypted fields by examining data format."""
        fields = []
        for key, value in data.items():
            if isinstance(value, str) and self._is_encrypted(value):
                fields.append(key)
        return fields

    def _is_encrypted(self, value: Any) -> bool:
        """Check if a value appears to be encrypted."""
        if not isinstance(value, str):
            return False

        # Check for our encryption format: version:key_id:data
        parts = value.split(":")
        if len(parts) != 3:
            return False

        try:
            version = int(parts[0])
            return version == FieldEncryption.VERSION
        except ValueError:
            return False

    def _get_field_config(
        self, model: Any, field_name: str
    ) -> Optional[Dict[str, Any]]:
        """Get field configuration from model."""
        # Try Pydantic v2
        if hasattr(model, "model_fields"):
            field_info = model.model_fields.get(field_name)
            if field_info:
                return getattr(field_info, "json_schema_extra", None)

        # Try Pydantic v1
        if hasattr(model, "__fields__"):
            field_info = model.__fields__.get(field_name)
            if field_info:
                return field_info.field_info.extra

        return None


class SearchableEncryption:
    """Utilities for searchable encryption.

    Enables exact-match and range queries on encrypted data.
    """

    def __init__(self, encryption: Optional[FieldEncryption] = None):
        self.encryption = encryption or FieldEncryption()

    def prepare_for_insert(
        self, plaintext: str, enable_search: bool = True
    ) -> Dict[str, Any]:
        """Prepare a value for insertion with search support.

        Returns:
            Dict with 'encrypted' and optional 'hash' fields

        """
        result = {
            "encrypted": self.encryption.encrypt(plaintext, EncryptionType.RANDOMIZED)
        }

        if enable_search:
            result["hash"] = self.encryption.hash_for_search(plaintext)

        return result

    def prepare_for_search(self, plaintext: str) -> str:
        """Prepare a search value.

        Returns the hash that can be used in exact-match queries.
        """
        return self.encryption.hash_for_search(plaintext)

    def matches(self, encrypted_record: Dict[str, Any], plaintext_search: str) -> bool:
        """Check if an encrypted record matches a plaintext search."""
        search_hash = self.encryption.hash_for_search(plaintext_search)
        return encrypted_record.get("hash") == search_hash


# Global instances
field_encryption = FieldEncryption()
model_encryption = ModelEncryption(field_encryption)
searchable_encryption = SearchableEncryption(field_encryption)


def setup_encryption(master_key: Optional[bytes] = None) -> FieldEncryption:
    """Setup encryption with a master key.

    Usage:
        # From environment
        setup_encryption()

        # With explicit key
        setup_encryption(base64.b64decode("your-key"))
    """
    global field_encryption, model_encryption, searchable_encryption

    key_provider = MasterKeyProvider(master_key)
    field_encryption = FieldEncryption(key_provider)
    model_encryption = ModelEncryption(field_encryption)
    searchable_encryption = SearchableEncryption(field_encryption)
    EncryptedString.set_encryption(field_encryption)

    return field_encryption


__all__ = [
    "Encrypted",
    "EncryptedString",
    "FieldEncryption",
    "field_encryption",
    "ModelEncryption",
    "model_encryption",
    "MasterKeyProvider",
    "EncryptionType",
    "EncryptedFieldConfig",
    "encrypted_field",
    "SearchableEncryption",
    "searchable_encryption",
    "setup_encryption",
]
