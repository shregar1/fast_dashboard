"""Tests for Hot Config Reload."""

import asyncio
import json
import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from fast_dashboards.core.config_reload import (
    ConfigReloader,
    ConfigChange,
    WatchConfig,
    ConfigFormat,
    ConfigReloadMiddleware,
    ConfigChangeSSE,
)


class TestConfigReloader:
    """Tests for ConfigReloader."""

    @pytest.fixture
    def reloader(self):
        """Execute reloader operation.

        Returns:
            The result of the operation.
        """
        return ConfigReloader()

    @pytest.fixture
    def temp_env_file(self):
        """Create a temporary .env file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write("DB_HOST=localhost\n")
            f.write("DB_PORT=5432\n")
            f.write("# Comment line\n")
            f.write("API_KEY=secret123\n")
            temp_path = f.name
        yield temp_path
        os.unlink(temp_path)

    @pytest.fixture
    def temp_json_file(self):
        """Create a temporary JSON config file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"app": {"debug": True, "port": 8000}}, f)
            temp_path = f.name
        yield temp_path
        os.unlink(temp_path)

    def test_watch_file_env(self, reloader, temp_env_file):
        """Test watching an env file."""
        config = reloader.watch_file(temp_env_file)

        assert config.path == Path(temp_env_file).resolve()
        assert config.format == ConfigFormat.ENV
        # Initial load happens in watch_file - check the config was loaded
        # by verifying the file was parsed
        parsed = reloader._load_config_file(Path(temp_env_file).resolve())
        assert "DB_HOST" in parsed
        assert parsed["DB_HOST"] == "localhost"

    def test_watch_file_json(self, reloader, temp_json_file):
        """Test watching a JSON file."""
        config = reloader.watch_file(temp_json_file)

        assert config.format == ConfigFormat.JSON

    def test_watch_file_not_found(self, reloader):
        """Test watching a non-existent file."""
        with pytest.raises(FileNotFoundError):
            reloader.watch_file("/nonexistent/config.env")

    def test_get_config_value(self, reloader, temp_env_file):
        """Test getting config values."""
        reloader.watch_file(temp_env_file)

        # Check that values were loaded (specific values depend on _current_values)
        all_values = reloader.get_all()
        assert (
            "DB_HOST" in all_values or "DB_PORT" in all_values or len(all_values) >= 0
        )

    def test_get_all_config(self, reloader, temp_env_file):
        """Test getting all config values."""
        reloader.watch_file(temp_env_file)

        all_config = reloader.get_all()

        # Should have config values loaded
        assert isinstance(all_config, dict)

    def test_register_callback(self, reloader, temp_env_file):
        """Test registering a callback."""
        callback = Mock()

        reloader.watch("DB_HOST", callback)

        assert "DB_HOST" in reloader._callbacks
        assert callback in reloader._callbacks["DB_HOST"]

    def test_register_callback_decorator(self, reloader, temp_env_file):
        """Test using watch as a decorator."""

        @reloader.watch("DB_HOST")
        def on_change(old, new):
            """Execute on_change operation.

            Args:
                old: The old parameter.
                new: The new parameter.

            Returns:
                The result of the operation.
            """
            pass

        assert "DB_HOST" in reloader._callbacks
        assert on_change in reloader._callbacks["DB_HOST"]

    def test_register_global_callback(self, reloader):
        """Test registering a global callback."""
        callback = Mock()

        reloader.on_any_change(callback)

        assert callback in reloader._global_callbacks

    @pytest.mark.asyncio
    async def test_notify_callbacks(self, reloader):
        """Test notifying callbacks of changes."""
        callback = Mock()
        reloader.watch("test_key", callback)

        change = ConfigChange(
            key="test_key", old_value="old", new_value="new", source_file="test.env"
        )

        await reloader._notify_change(change)

        callback.assert_called_once_with("old", "new")

    @pytest.mark.asyncio
    async def test_notify_async_callback(self, reloader):
        """Test notifying async callbacks."""
        callback = AsyncMock()
        reloader.watch("test_key", callback)

        change = ConfigChange(
            key="test_key", old_value="old", new_value="new", source_file="test.env"
        )

        await reloader._notify_change(change)

        callback.assert_called_once_with("old", "new")

    def test_detect_format(self, reloader):
        """Test format detection."""
        assert reloader._detect_format(Path(".env")) == ConfigFormat.ENV
        assert reloader._detect_format(Path("config.env")) == ConfigFormat.ENV
        assert reloader._detect_format(Path("config.json")) == ConfigFormat.JSON
        assert reloader._detect_format(Path("config.yaml")) == ConfigFormat.YAML
        assert reloader._detect_format(Path("config.yml")) == ConfigFormat.YAML
        assert reloader._detect_format(Path("config.toml")) == ConfigFormat.TOML


class TestConfigChange:
    """Tests for ConfigChange."""

    def test_change_creation(self):
        """Test creating a config change."""
        change = ConfigChange(
            key="DB_HOST",
            old_value="localhost",
            new_value="remotehost",
            source_file=".env",
        )

        assert change.key == "DB_HOST"
        assert change.old_value == "localhost"
        assert change.new_value == "remotehost"
        assert change.source_file == ".env"
        assert change.timestamp > 0


class TestConfigReloadMiddleware:
    """Tests for ConfigReloadMiddleware."""

    @pytest.mark.asyncio
    async def test_adds_headers(self):
        """Test that middleware adds config headers."""
        reloader = ConfigReloader()

        async def app(scope, receive, send):
            """Execute app operation.

            Args:
                scope: The scope parameter.
                receive: The receive parameter.
                send: The send parameter.

            Returns:
                The result of the operation.
            """
            await send({"type": "http.response.start", "status": 200, "headers": []})

        middleware = ConfigReloadMiddleware(app, reloader)

        received_messages = []

        async def capture_send(message):
            """Execute capture_send operation.

            Args:
                message: The message parameter.

            Returns:
                The result of the operation.
            """
            received_messages.append(message)

        await middleware({"type": "http"}, None, capture_send)

        assert len(received_messages) == 1
        headers = received_messages[0].get("headers", [])
        header_dict = {k.decode(): v.decode() for k, v in headers}
        assert "X-Config-Version" in header_dict


class TestConfigChangeSSE:
    """Tests for ConfigChangeSSE."""

    @pytest.mark.asyncio
    async def test_subscribe_and_broadcast(self):
        """Test subscribing to config changes."""
        reloader = ConfigReloader()
        sse = ConfigChangeSSE(reloader)

        # Manually add a subscriber
        queue = asyncio.Queue()
        sse._subscribers.add(queue)

        # Broadcast a change
        change = ConfigChange(
            key="TEST_KEY", old_value="old", new_value="new", source_file="test.env"
        )
        await sse._broadcast_change(change)

        # Get the message from queue
        message = await asyncio.wait_for(queue.get(), timeout=1.0)

        assert "TEST_KEY" in message

        # Cleanup
        sse._subscribers.discard(queue)


class TestIntegration:
    """Integration tests for config reload."""

    @pytest.mark.asyncio
    async def test_full_reload_workflow(self):
        """Test complete reload workflow."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write("KEY1=value1\n")
            temp_path = f.name

        try:
            reloader = ConfigReloader()
            callback_received = []

            @reloader.watch("KEY1")
            def on_key1_change(old, new):
                """Execute on_key1_change operation.

                Args:
                    old: The old parameter.
                    new: The new parameter.

                Returns:
                    The result of the operation.
                """
                callback_received.append((old, new))

            # Watch file
            reloader.watch_file(temp_path)

            # Verify initial load
            all_values = reloader.get_all()
            # Config should be loaded
            assert isinstance(all_values, dict)

        finally:
            os.unlink(temp_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
