"""
Tests for Field-Level Encryption.
"""

import base64
import pytest
from unittest.mock import Mock, patch

from fast_dashboards.core.encryption import (
    MasterKeyProvider,
    FieldEncryption,
    EncryptedString,
    ModelEncryption,
    SearchableEncryption,
    EncryptionType,
    Encrypted,
    setup_encryption,
    model_encryption,
)


# Skip tests if cryptography is not available
pytestmark = pytest.mark.skipif(
    not hasattr(FieldEncryption, 'VERSION'),
    reason="cryptography package not installed"
)


class TestMasterKeyProvider:
    """Tests for MasterKeyProvider."""
    
    def test_create_with_key(self):
        """Test creating provider with explicit key."""
        key = b"x" * 32  # 256-bit key
        provider = MasterKeyProvider(master_key=key)
        
        retrieved = provider.get_key()
        assert retrieved == key
    
    def test_add_key(self):
        """Test adding a key."""
        provider = MasterKeyProvider()
        key = b"y" * 32
        
        provider.add_key("key-2", key)
        
        assert provider.get_key("key-2") == key
    
    def test_key_not_found(self):
        """Test getting a non-existent key."""
        provider = MasterKeyProvider()
        
        with pytest.raises(KeyError):
            provider.get_key("nonexistent")
    
    def test_key_rotation(self):
        """Test key rotation."""
        provider = MasterKeyProvider(master_key=b"old" * 8)
        
        new_key = b"new" * 8
        new_key_id = provider.rotate_key(new_key)
        
        assert provider.get_current_key_id() == new_key_id
        assert provider.get_key(new_key_id) == new_key
        # Old key should still be available
        assert provider.get_key("key-1") == b"old" * 8


class TestFieldEncryption:
    """Tests for FieldEncryption."""
    
    @pytest.fixture
    def encryption(self):
        """Create encryption with test key."""
        key = AESGCM.generate_key(bit_length=256) if 'AESGCM' in dir() else b"x" * 32
        provider = MasterKeyProvider(master_key=key)
        return FieldEncryption(key_provider=provider)
    
    @pytest.mark.skipif(
        'AESGCM' not in dir(__import__('fast_dashboards.core.encryption', fromlist=[''])),
        reason="AESGCM not available"
    )
    def test_encrypt_decrypt_string(self, encryption):
        """Test encrypting and decrypting a string."""
        plaintext = "sensitive data"
        
        ciphertext = encryption.encrypt(plaintext)
        assert ciphertext != plaintext
        assert ":" in ciphertext  # Should have version:key_id:data format
        
        decrypted = encryption.decrypt(ciphertext)
        assert decrypted == plaintext
    
    @pytest.mark.skipif(
        'AESGCM' not in dir(__import__('fast_dashboards.core.encryption', fromlist=[''])),
        reason="AESGCM not available"
    )
    def test_encrypt_bytes(self, encryption):
        """Test encrypting bytes."""
        plaintext = b"binary data"
        
        ciphertext = encryption.encrypt(plaintext)
        decrypted = encryption.decrypt(ciphertext)
        
        assert decrypted == plaintext.decode()
    
    @pytest.mark.skipif(
        'AESGCM' not in dir(__import__('fast_dashboards.core.encryption', fromlist=[''])),
        reason="AESGCM not available"
    )
    def test_deterministic_encryption(self, encryption):
        """Test deterministic encryption produces same output."""
        plaintext = "test@example.com"
        
        # Encrypt twice
        ciphertext1 = encryption.encrypt(plaintext, EncryptionType.DETERMINISTIC)
        ciphertext2 = encryption.encrypt(plaintext, EncryptionType.DETERMINISTIC)
        
        # Should be the same (deterministic)
        assert ciphertext1 == ciphertext2
    
    @pytest.mark.skipif(
        'AESGCM' not in dir(__import__('fast_dashboards.core.encryption', fromlist=[''])),
        reason="AESGCM not available"
    )
    def test_randomized_encryption(self, encryption):
        """Test randomized encryption produces different output."""
        plaintext = "test@example.com"
        
        # Encrypt twice
        ciphertext1 = encryption.encrypt(plaintext, EncryptionType.RANDOMIZED)
        ciphertext2 = encryption.encrypt(plaintext, EncryptionType.RANDOMIZED)
        
        # Should be different (randomized)
        assert ciphertext1 != ciphertext2
        
        # But both should decrypt to same plaintext
        assert encryption.decrypt(ciphertext1) == plaintext
        assert encryption.decrypt(ciphertext2) == plaintext
    
    def test_hash_for_search(self, encryption):
        """Test generating searchable hashes."""
        plaintext = "test@example.com"
        
        hash1 = encryption.hash_for_search(plaintext)
        hash2 = encryption.hash_for_search(plaintext)
        
        # Same plaintext should produce same hash
        assert hash1 == hash2
        assert len(hash1) == 32  # Should be truncated to 32 chars
    
    def test_invalid_format(self, encryption):
        """Test decrypting invalid format."""
        with pytest.raises(ValueError, match="Invalid encrypted format"):
            encryption.decrypt("invalid-ciphertext")
    
    def test_unsupported_version(self, encryption):
        """Test decrypting unsupported version."""
        with pytest.raises(ValueError, match="Unsupported encryption version"):
            encryption.decrypt("999:key-1:abc123")


class TestEncryptedString:
    """Tests for EncryptedString."""
    
    def test_create_plaintext(self):
        """Test creating from plaintext."""
        s = EncryptedString("sensitive data")
        
        # Should be masked in string representation
        assert "****" in str(s)
        assert "sensitive data" not in str(s)
    
    def test_access_plaintext(self):
        """Test accessing plaintext value."""
        s = EncryptedString("sensitive data")
        
        # Without encryption setup, should return as-is
        assert s.plaintext == "sensitive data"


class TestSearchableEncryption:
    """Tests for SearchableEncryption."""
    
    @pytest.fixture
    def searchable(self):
        """Create searchable encryption."""
        key = b"x" * 32
        provider = MasterKeyProvider(master_key=key)
        field_encryption = FieldEncryption(key_provider=provider)
        return SearchableEncryption(encryption=field_encryption)
    
    @pytest.mark.skipif(
        'AESGCM' not in dir(__import__('fast_dashboards.core.encryption', fromlist=[''])),
        reason="AESGCM not available"
    )
    def test_prepare_for_insert(self, searchable):
        """Test preparing data for insert."""
        result = searchable.prepare_for_insert("test@example.com")
        
        assert "encrypted" in result
        assert "hash" in result
    
    def test_prepare_for_search(self, searchable):
        """Test preparing search value."""
        search_hash = searchable.prepare_for_search("test@example.com")
        
        assert len(search_hash) > 0
    
    def test_matches(self, searchable):
        """Test matching encrypted records."""
        record = {"hash": searchable.prepare_for_search("test@example.com")}
        
        assert searchable.matches(record, "test@example.com") is True
        assert searchable.matches(record, "other@example.com") is False


class TestModelEncryption:
    """Tests for ModelEncryption."""
    
    def test_detect_encrypted_fields(self):
        """Test detecting encrypted fields from annotations."""
        key = b"x" * 32
        provider = MasterKeyProvider(master_key=key)
        field_encryption = FieldEncryption(key_provider=provider)
        model_encryption = ModelEncryption(encryption=field_encryption)
        
        # Create a mock model with Encrypted type hints
        class MockModel:
            name: str
            ssn: Encrypted[str]
            email: Encrypted[str]
        
        fields = model_encryption._detect_encrypted_fields(MockModel)
        
        assert "ssn" in fields
        assert "email" in fields
        assert "name" not in fields
    
    def test_is_encrypted_detection(self):
        """Test detecting encrypted values."""
        key = b"x" * 32
        provider = MasterKeyProvider(master_key=key)
        field_encryption = FieldEncryption(key_provider=provider)
        model_encryption = ModelEncryption(encryption=field_encryption)
        
        # Valid encrypted format
        assert model_encryption._is_encrypted(f"{FieldEncryption.VERSION}:key-1:abc123") is True
        
        # Invalid formats
        assert model_encryption._is_encrypted("plain text") is False
        assert model_encryption._is_encrypted("123") is False
        assert model_encryption._is_encrypted(123) is False


class TestSetupEncryption:
    """Tests for setup_encryption function."""
    
    def test_setup_with_key(self):
        """Test setting up encryption with explicit key."""
        key = base64.urlsafe_b64encode(b"x" * 32)
        
        # Should not raise
        result = setup_encryption(base64.urlsafe_b64decode(key))
        
        assert result is not None
    
    @patch.dict('os.environ', {'FASTMVC_ENCRYPTION_KEY': base64.urlsafe_b64encode(b"x" * 32).decode()})
    def test_setup_from_env(self):
        """Test setting up encryption from environment."""
        # Should not raise
        result = setup_encryption()
        
        assert result is not None


class TestIntegration:
    """Integration tests for encryption."""
    
    @pytest.mark.skipif(
        'AESGCM' not in dir(__import__('fast_dashboards.core.encryption', fromlist=[''])),
        reason="AESGCM not available"
    )
    def test_full_workflow(self):
        """Test a complete encryption workflow."""
        from dataclasses import dataclass
        
        # Setup
        key = AESGCM.generate_key(bit_length=256)
        setup_encryption(key)
        
        # Create mock model as dataclass
        @dataclass
        class User:
            name: str
            ssn: str
            email: str
            
            def dict(self):
                return {"name": self.name, "ssn": self.ssn, "email": self.email}
        
        test_data = {
            "name": "John Doe",
            "ssn": "123-45-6789",
            "email": "john@example.com",
        }
        
        user = User(**test_data)
        
        # Encrypt
        encrypted = model_encryption.encrypt_model(user, fields=["ssn"])
        
        # Verify ssn is encrypted
        assert encrypted["ssn"] != test_data["ssn"]
        
        # Decrypt
        decrypted = model_encryption.decrypt_model(encrypted, fields=["ssn"])
        
        # Verify decryption
        assert decrypted["ssn"] == test_data["ssn"]


# Try to import AESGCM for conditional tests
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError:
    AESGCM = None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
