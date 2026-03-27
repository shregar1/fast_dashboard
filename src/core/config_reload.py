"""Hot Config Reload - Watch configuration files and auto-apply changes.

Features:
- Watch .env, JSON, YAML config files for changes
- Auto-reload without server restart
- Callback support for custom reload handlers
- Graceful degradation on config errors
- Config validation before applying
- WebSocket/SSE notifications for config changes

Usage:
    from fast_dashboards.core.config_reload import ConfigReloader

    reloader = ConfigReloader()

    @reloader.watch("database.pool_size")
    async def on_pool_size_change(old, new):
        await db_connection_pool.resize(new)

    reloader.start_watching()
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol, Set, Union

from loguru import logger


class ConfigFormat(Enum):
    """Supported configuration formats."""

    ENV = "env"
    JSON = "json"
    YAML = "yaml"
    TOML = "toml"


@dataclass
class ConfigChange:
    """Represents a configuration change."""

    key: str
    old_value: Any
    new_value: Any
    source_file: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class WatchConfig:
    """Configuration for a file watcher."""

    path: Path
    format: ConfigFormat
    reload_delay: float = 0.5  # Debounce delay
    validate_before_apply: bool = True
    auto_reload: bool = True


class ConfigValidator(Protocol):
    """Protocol for config validators."""

    async def validate(self, key: str, value: Any) -> tuple[bool, Optional[str]]:
        """Validate a config value.

        Returns:
            Tuple of (is_valid, error_message)

        """
        ...


class ConfigReloader:
    """Hot configuration reloader with file watching and callbacks.

    Features:
    - Multi-format support (.env, JSON, YAML, TOML)
    - Debounced reloads
    - Validation before apply
    - Webhook notifications
    - Change callbacks
    """

    def __init__(self):
        """Execute __init__ operation."""
        self._watchers: Dict[Path, WatchConfig] = {}
        self._callbacks: Dict[str, List[Callable]] = {}
        self._global_callbacks: List[Callable[[ConfigChange], None]] = []
        self._validators: Dict[str, List[ConfigValidator]] = {}
        self._current_values: Dict[str, Any] = {}
        self._watcher_tasks: Set[asyncio.Task] = set()
        self._running = False
        self._lock = asyncio.Lock()

    def watch_file(
        self,
        path: Union[str, Path],
        format: Optional[ConfigFormat] = None,
        auto_reload: bool = True,
        reload_delay: float = 0.5,
    ) -> WatchConfig:
        """Add a file to watch for changes.

        Args:
            path: Path to config file
            format: Config format (auto-detected if None)
            auto_reload: Whether to auto-reload on changes
            reload_delay: Debounce delay in seconds

        Returns:
            WatchConfig instance

        """
        path = Path(path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        # Auto-detect format
        if format is None:
            format = self._detect_format(path)

        config = WatchConfig(
            path=path, format=format, reload_delay=reload_delay, auto_reload=auto_reload
        )

        self._watchers[path] = config

        # Load initial values
        self._load_config_file(path)

        logger.info(f"Watching config file: {path} ({format.value})")

        return config

    def _detect_format(self, path: Path) -> ConfigFormat:
        """Detect config format from file extension."""
        suffix = path.suffix.lower()

        if suffix == ".env" or ".env" in path.name:
            return ConfigFormat.ENV
        elif suffix == ".json":
            return ConfigFormat.JSON
        elif suffix in (".yaml", ".yml"):
            return ConfigFormat.YAML
        elif suffix == ".toml":
            return ConfigFormat.TOML
        else:
            # Default to env format
            return ConfigFormat.ENV

    def _load_config_file(self, path: Path) -> Dict[str, Any]:
        """Load a config file and return its contents."""
        config = self._watchers[path]

        if config.format == ConfigFormat.ENV:
            return self._parse_env_file(path)
        elif config.format == ConfigFormat.JSON:
            with open(path) as f:
                return json.load(f)
        elif config.format == ConfigFormat.YAML:
            try:
                import yaml

                with open(path) as f:
                    return yaml.safe_load(f)
            except ImportError:
                logger.error("PyYAML not installed, cannot load YAML config")
                return {}
        elif config.format == ConfigFormat.TOML:
            try:
                import tomllib

                with open(path, "rb") as f:
                    return tomllib.load(f)
            except ImportError:
                logger.error(
                    "tomllib not available (Python 3.11+), cannot load TOML config"
                )
                return {}

        return {}

    def _parse_env_file(self, path: Path) -> Dict[str, str]:
        """Parse a .env file."""
        values = {}
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    values[key.strip()] = value.strip().strip('"').strip("'")
        return values

    def watch(
        self, key: str, callback: Optional[Callable[[Any, Any], None]] = None
    ) -> Callable:
        """Watch a specific config key for changes.

        Can be used as a decorator:
            @reloader.watch("database.host")
            async def on_db_host_change(old, new):
                await reconnect_db(new)

        Args:
            key: Config key to watch
            callback: Optional callback function(old_value, new_value)

        Returns:
            Decorator function if callback not provided

        """
        if callback:
            if key not in self._callbacks:
                self._callbacks[key] = []
            self._callbacks[key].append(callback)
            return callback

        # Return decorator
        def decorator(func: Callable):
            """Execute decorator operation.

            Args:
                func: The func parameter.

            Returns:
                The result of the operation.
            """
            if key not in self._callbacks:
                self._callbacks[key] = []
            self._callbacks[key].append(func)
            return func

        return decorator

    def on_any_change(self, callback: Callable[[ConfigChange], None]):
        """Register a callback for any config change.

        Args:
            callback: Function called with ConfigChange on any change

        """
        self._global_callbacks.append(callback)

    def add_validator(self, key: str, validator: ConfigValidator):
        """Add a validator for a config key.

        Validators are called before applying changes.
        """
        if key not in self._validators:
            self._validators[key] = []
        self._validators[key].append(validator)

    async def start_watching(self):
        """Start watching all registered files."""
        if self._running:
            return

        self._running = True

        for path, config in self._watchers.items():
            task = asyncio.create_task(self._watch_file_task(path, config))
            self._watcher_tasks.add(task)
            task.add_done_callback(self._watcher_tasks.discard)

        logger.info(f"Started watching {len(self._watchers)} config files")

    async def stop_watching(self):
        """Stop all file watchers."""
        self._running = False

        for task in self._watcher_tasks:
            task.cancel()

        if self._watcher_tasks:
            await asyncio.gather(*self._watcher_tasks, return_exceptions=True)

        self._watcher_tasks.clear()
        logger.info("Stopped config file watching")

    async def _watch_file_task(self, path: Path, config: WatchConfig):
        """Watch a single file for changes."""
        last_mtime = path.stat().st_mtime
        last_size = path.stat().st_size

        while self._running:
            try:
                await asyncio.sleep(0.5)  # Check every 500ms

                if not path.exists():
                    logger.warning(f"Config file deleted: {path}")
                    continue

                stat = path.stat()

                if stat.st_mtime != last_mtime or stat.st_size != last_size:
                    # Debounce
                    await asyncio.sleep(config.reload_delay)

                    # Check again
                    stat = path.stat()
                    if stat.st_mtime == last_mtime and stat.st_size == last_size:
                        continue

                    last_mtime = stat.st_mtime
                    last_size = stat.st_size

                    if config.auto_reload:
                        await self._handle_file_change(path)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error watching {path}: {e}")

    async def _handle_file_change(self, path: Path):
        """Handle a config file change."""
        logger.info(f"Config file changed: {path}")

        try:
            new_values = self._load_config_file(path)

            async with self._lock:
                # Find changes
                for key, new_value in new_values.items():
                    old_value = self._current_values.get(key)

                    if old_value != new_value:
                        change = ConfigChange(
                            key=key,
                            old_value=old_value,
                            new_value=new_value,
                            source_file=str(path),
                        )

                        # Validate
                        is_valid, error = await self._validate_change(change)

                        if is_valid:
                            # Apply change
                            self._current_values[key] = new_value

                            # Notify
                            await self._notify_change(change)

                            logger.info(f"Config updated: {key} = {new_value}")
                        else:
                            logger.error(f"Config validation failed for {key}: {error}")

                # Handle removed keys
                for key in list(self._current_values.keys()):
                    if key not in new_values:
                        change = ConfigChange(
                            key=key,
                            old_value=self._current_values[key],
                            new_value=None,
                            source_file=str(path),
                        )
                        await self._notify_change(change)
                        del self._current_values[key]

        except Exception as e:
            logger.error(f"Failed to reload config from {path}: {e}")

    async def _validate_change(
        self, change: ConfigChange
    ) -> tuple[bool, Optional[str]]:
        """Validate a config change."""
        validators = self._validators.get(change.key, [])

        for validator in validators:
            is_valid, error = await validator.validate(change.key, change.new_value)
            if not is_valid:
                return False, error

        return True, None

    async def _notify_change(self, change: ConfigChange):
        """Notify all callbacks of a change."""
        # Key-specific callbacks
        callbacks = self._callbacks.get(change.key, [])

        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(change.old_value, change.new_value)
                else:
                    callback(change.old_value, change.new_value)
            except Exception as e:
                logger.error(f"Config change callback failed: {e}")

        # Global callbacks
        for callback in self._global_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(change)
                else:
                    callback(change)
            except Exception as e:
                logger.error(f"Global config callback failed: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """Get current config value."""
        return self._current_values.get(key, default)

    def get_all(self) -> Dict[str, Any]:
        """Get all current config values."""
        return self._current_values.copy()

    async def reload_now(self, path: Optional[Path] = None):
        """Force reload config immediately."""
        if path:
            await self._handle_file_change(path)
        else:
            for p in self._watchers:
                await self._handle_file_change(p)


class ConfigReloadMiddleware:
    """FastAPI middleware for config reload notifications.

    Adds headers to responses when config has changed.
    """

    def __init__(self, app, reloader: ConfigReloader):
        """Execute __init__ operation.

        Args:
            app: The app parameter.
            reloader: The reloader parameter.
        """
        self.app = app
        self.reloader = reloader
        self._last_change_time = 0

        # Track changes
        reloader.on_any_change(self._on_change)

    def _on_change(self, change: ConfigChange):
        """Track config changes."""
        self._last_change_time = change.timestamp

    async def __call__(self, scope, receive, send):
        """Add config headers to responses."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def wrapped_send(message):
            """Execute wrapped_send operation.

            Args:
                message: The message parameter.

            Returns:
                The result of the operation.
            """
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append(
                    (b"X-Config-Version", str(int(self._last_change_time)).encode())
                )
                message["headers"] = headers

            await send(message)

        await self.app(scope, receive, wrapped_send)


class ConfigChangeSSE:
    """Server-Sent Events endpoint for config changes.

    Clients can subscribe to config changes in real-time.
    """

    def __init__(self, reloader: ConfigReloader):
        """Execute __init__ operation.

        Args:
            reloader: The reloader parameter.
        """
        self.reloader = reloader
        self._subscribers: Set[asyncio.Queue] = set()

        reloader.on_any_change(self._broadcast_change)

    async def _broadcast_change(self, change: ConfigChange):
        """Broadcast change to all subscribers."""
        message = json.dumps(
            {
                "event": "config_change",
                "data": {
                    "key": change.key,
                    "new_value": str(change.new_value),
                    "timestamp": change.timestamp,
                },
            }
        )

        for queue in list(self._subscribers):
            try:
                await queue.put(message)
            except Exception:
                self._subscribers.discard(queue)

    async def subscribe(self):
        """Subscribe to config changes.

        Yields SSE events.
        """
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.add(queue)

        try:
            while True:
                message = await queue.get()
                yield f"data: {message}\n\n"
        finally:
            self._subscribers.discard(queue)


# Global reloader instance
config_reloader = ConfigReloader()


__all__ = [
    "ConfigReloader",
    "config_reloader",
    "ConfigChange",
    "WatchConfig",
    "ConfigFormat",
    "ConfigValidator",
    "ConfigReloadMiddleware",
    "ConfigChangeSSE",
]
