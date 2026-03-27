"""Revocation list and theme/locale query params for signed embed URLs."""

from fast_dashboards.core.embed_revocation import InMemoryEmbedRevocationList
from fast_dashboards.core.embed_signing import sign_embed_url, verify_signed_embed_url
from fast_dashboards.core.embed_theme import EmbedThemeParams, theme_to_extra_params


def test_sign_embed_accepts_tid_theme_locale():
    """Execute test_sign_embed_accepts_tid_theme_locale operation.

    Returns:
        The result of the operation.
    """
    secret = b"k" * 32
    u = sign_embed_url(
        "https://x.com/d",
        secret,
        60,
        token_id="tok-1",
        theme="dark",
        locale="en-US",
    )
    p = verify_signed_embed_url(u, secret)
    assert p is not None
    assert p.get("tid") == "tok-1"
    assert p.get("theme") == "dark"
    assert p.get("locale") == "en-US"


def test_verify_revokes_tid():
    """Execute test_verify_revokes_tid operation.

    Returns:
        The result of the operation.
    """
    secret = b"k" * 32
    u = sign_embed_url("https://x.com/d", secret, 60, token_id="bad")
    block = InMemoryEmbedRevocationList()
    assert verify_signed_embed_url(u, secret) is not None
    assert verify_signed_embed_url(u, secret, revocation=block) is not None
    block.revoke("bad")
    assert verify_signed_embed_url(u, secret, revocation=block) is None


def test_theme_to_extra_params_merge():
    """Execute test_theme_to_extra_params_merge operation.

    Returns:
        The result of the operation.
    """
    t = EmbedThemeParams(appearance="light", locale="de")
    assert theme_to_extra_params(t) == {"theme": "light", "locale": "de"}


def test_sign_merges_theme_extra_params():
    """Execute test_sign_merges_theme_extra_params operation.

    Returns:
        The result of the operation.
    """
    secret = b"k" * 32
    u = sign_embed_url(
        "https://x.com/y",
        secret,
        120,
        extra_params=theme_to_extra_params(EmbedThemeParams(appearance="dark")),
    )
    p = verify_signed_embed_url(u, secret)
    assert p is not None
    assert p.get("theme") == "dark"
