"""Tests for time-limited embed URL signing."""

import time
from unittest.mock import patch

from fast_dashboards.core.embed_signing import sign_embed_url, verify_signed_embed_url


def test_sign_verify_roundtrip():
    """Execute test_sign_verify_roundtrip operation.

    Returns:
        The result of the operation.
    """
    secret = b"test-secret-32-bytes-long!!!!"
    url = "https://app.example.com/embed/view"
    signed = sign_embed_url(url, secret, ttl_seconds=3600, extra_params={"k": "v"})
    assert "exp=" in signed
    assert "sig=" in signed
    params = verify_signed_embed_url(signed, secret)
    assert params is not None
    assert params.get("k") == "v"
    assert "exp" in params


def test_verify_rejects_expired():
    """Execute test_verify_rejects_expired operation.

    Returns:
        The result of the operation.
    """
    secret = b"x" * 32
    url = "https://a.com/x"
    signed = sign_embed_url(url, secret, ttl_seconds=1)
    with patch(
        "fast_dashboards.core.embed_signing.time.time", return_value=time.time() + 99999
    ):
        assert verify_signed_embed_url(signed, secret) is None


def test_verify_rejects_bad_sig():
    """Execute test_verify_rejects_bad_sig operation.

    Returns:
        The result of the operation.
    """
    secret = b"x" * 32
    signed = sign_embed_url("https://a.com/x", secret, 60)
    tampered = signed.replace("sig=", "sig=00")
    assert verify_signed_embed_url(tampered, secret) is None


def test_verify_rejects_missing_params():
    """Execute test_verify_rejects_missing_params operation.

    Returns:
        The result of the operation.
    """
    assert verify_signed_embed_url("https://a.com/x", b"secret") is None


def test_sign_merges_existing_query():
    """Execute test_sign_merges_existing_query operation.

    Returns:
        The result of the operation.
    """
    secret = b"k" * 32
    signed = sign_embed_url("https://a.com/p?existing=1", secret, 60)
    params = verify_signed_embed_url(signed, secret)
    assert params is not None
    assert params.get("existing") == "1"


def test_verify_rejects_non_numeric_exp():
    """Execute test_verify_rejects_non_numeric_exp operation.

    Returns:
        The result of the operation.
    """
    secret = b"k" * 32
    assert (
        verify_signed_embed_url("https://a.com/x?exp=abc&sig=deadbeef", secret) is None
    )


def test_verify_rejects_missing_exp_with_sig():
    """Execute test_verify_rejects_missing_exp_with_sig operation.

    Returns:
        The result of the operation.
    """
    assert verify_signed_embed_url("https://a.com/x?sig=foo", b"k" * 32) is None
