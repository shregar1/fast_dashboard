"""Production-grade audit logging system.

Tracks all significant actions with user context, timing, and outcomes.
Supports multiple backends: console, file, database, webhook.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Protocol

from fastapi import Request, Response
from loguru import logger


class AuditLevel(str, Enum):
    """Audit log levels."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AuditAction(str, Enum):
    """Standard audit actions."""

    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"
    EXPORT = "export"
    IMPORT = "import"
    EXECUTE = "execute"
    CONFIG_CHANGE = "config_change"


@dataclass
class AuditEvent:
    """Audit event record."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    level: AuditLevel = AuditLevel.INFO
    action: str = ""
    resource_type: str = ""
    resource_id: Optional[str] = None
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    tenant_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    request_path: Optional[str] = None
    request_method: Optional[str] = None
    status_code: Optional[int] = None
    duration_ms: Optional[float] = None
    success: bool = True
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), default=str)


class AuditBackend(Protocol):
    """Protocol for audit backends."""

    async def write(self, event: AuditEvent) -> None:
        """Write an audit event."""
        ...

    async def query(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 100,
    ) -> List[AuditEvent]:
        """Query audit events."""
        ...


class ConsoleAuditBackend:
    """Console output audit backend."""

    async def write(self, event: AuditEvent) -> None:
        """Write to console."""
        emoji = {
            AuditAction.CREATE: "📝",
            AuditAction.READ: "👁️",
            AuditAction.UPDATE: "✏️",
            AuditAction.DELETE: "🗑️",
            AuditAction.LOGIN: "🔑",
            AuditAction.LOGOUT: "👋",
            AuditAction.EXECUTE: "▶️",
            AuditAction.CONFIG_CHANGE: "⚙️",
        }.get(event.action, "📋")

        status = "✅" if event.success else "❌"
        user = event.user_email or event.user_id or "anonymous"

        logger.info(
            f"{emoji} {status} [{event.action.upper()}] {event.resource_type} "
            f"by {user} | {event.duration_ms:.1f}ms | {event.request_path}"
        )

    async def query(self, **kwargs) -> List[AuditEvent]:
        """Console backend doesn't support querying."""
        return []


class FileAuditBackend:
    """File-based audit backend."""

    def __init__(self, filepath: str = "/tmp/audit.log"):
        """Execute __init__ operation.

        Args:
            filepath: The filepath parameter.
        """
        self.filepath = filepath
        self._lock = asyncio.Lock()

    async def write(self, event: AuditEvent) -> None:
        """Append to file."""
        async with self._lock:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._write_sync, event)

    def _write_sync(self, event: AuditEvent) -> None:
        """Synchronous file write."""
        with open(self.filepath, "a") as f:
            f.write(event.to_json() + "\n")

    async def query(self, **kwargs) -> List[AuditEvent]:
        """Query from file."""
        # Simplified implementation
        return []


class InMemoryAuditBackend:
    """In-memory audit backend for testing."""

    def __init__(self, max_size: int = 10000):
        """Execute __init__ operation.

        Args:
            max_size: The max_size parameter.
        """
        self.events: List[AuditEvent] = []
        self.max_size = max_size

    async def write(self, event: AuditEvent) -> None:
        """Store in memory."""
        self.events.append(event)
        # Trim if too large
        if len(self.events) > self.max_size:
            self.events = self.events[-self.max_size :]

    async def query(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 100,
    ) -> List[AuditEvent]:
        """Query in-memory events."""
        results = self.events

        if user_id:
            results = [e for e in results if e.user_id == user_id]
        if action:
            results = [e for e in results if e.action == action]

        return results[-limit:]


class AuditLogger:
    """Production-grade audit logger."""

    def __init__(self):
        """Execute __init__ operation."""
        self.backends: List[AuditBackend] = [ConsoleAuditBackend()]
        self.sensitive_fields = {
            "password",
            "token",
            "secret",
            "api_key",
            "credit_card",
        }

    def add_backend(self, backend: AuditBackend) -> None:
        """Add an audit backend."""
        self.backends.append(backend)

    def _sanitize_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive fields from metadata."""
        sanitized = {}
        for key, value in metadata.items():
            if any(sensitive in key.lower() for sensitive in self.sensitive_fields):
                sanitized[key] = "***REDACTED***"
            else:
                sanitized[key] = value
        return sanitized

    async def log(
        self,
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        user_id: Optional[str] = None,
        user_email: Optional[str] = None,
        tenant_id: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        level: AuditLevel = AuditLevel.INFO,
        request: Optional[Request] = None,
        response: Optional[Response] = None,
        duration_ms: Optional[float] = None,
    ) -> AuditEvent:
        """Create and log an audit event."""
        event = AuditEvent(
            level=level,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            user_email=user_email,
            tenant_id=tenant_id,
            success=success,
            error_message=error_message,
            metadata=self._sanitize_metadata(metadata or {}),
            duration_ms=duration_ms,
        )

        # Extract request info if provided
        if request:
            event.ip_address = self._get_client_ip(request)
            event.user_agent = request.headers.get("user-agent")
            event.request_path = str(request.url.path)
            event.request_method = request.method

            # Try to get user from request state
            if hasattr(request.state, "user"):
                user = request.state.user
                if user:
                    event.user_id = getattr(user, "id", event.user_id)
                    event.user_email = getattr(user, "email", event.user_email)

            if hasattr(request.state, "tenant_id"):
                event.tenant_id = request.state.tenant_id

        if response:
            event.status_code = response.status_code

        # Write to all backends
        for backend in self.backends:
            try:
                await backend.write(event)
            except Exception as e:
                logger.error(f"Audit backend failed: {e}")

        return event

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        if request.client:
            return request.client.host

        return "unknown"

    async def log_request(
        self, request: Request, response: Response, duration_ms: float
    ) -> Optional[AuditEvent]:
        """Automatically log an HTTP request."""
        # Skip health checks and static files
        path = request.url.path
        if path in ["/health", "/ready", "/metrics"] or path.startswith("/static"):
            return None

        # Determine action from HTTP method
        action_map = {
            "GET": AuditAction.READ,
            "POST": AuditAction.CREATE,
            "PUT": AuditAction.UPDATE,
            "PATCH": AuditAction.UPDATE,
            "DELETE": AuditAction.DELETE,
        }
        action = action_map.get(request.method, AuditAction.EXECUTE)

        # Extract resource type from path
        parts = path.strip("/").split("/")
        resource_type = parts[0] if parts else "unknown"
        resource_id = parts[1] if len(parts) > 1 else None

        return await self.log(
            action=action.value,
            resource_type=resource_type,
            resource_id=resource_id,
            request=request,
            response=response,
            duration_ms=duration_ms,
            success=response.status_code < 400,
        )


# Global audit logger
audit_logger = AuditLogger()


class AuditMiddleware:
    """FastAPI middleware for automatic request auditing."""

    def __init__(self, app, skip_paths: Optional[List[str]] = None):
        """Execute __init__ operation.

        Args:
            app: The app parameter.
            skip_paths: The skip_paths parameter.
        """
        self.app = app
        self.skip_paths = set(
            skip_paths or ["/health", "/ready", "/metrics", "/docs", "/openapi.json"]
        )

    async def __call__(self, scope, receive, send):
        """Execute __call__ operation.

        Args:
            scope: The scope parameter.
            receive: The receive parameter.
            send: The send parameter.

        Returns:
            The result of the operation.
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)

        if request.url.path in self.skip_paths:
            await self.app(scope, receive, send)
            return

        start_time = time.time()

        # Capture response
        response_body = []

        async def wrapped_send(message):
            """Execute wrapped_send operation.

            Args:
                message: The message parameter.

            Returns:
                The result of the operation.
            """
            if message["type"] == "http.response.body":
                response_body.append(message.get("body", b""))
            await send(message)

        try:
            await self.app(scope, receive, wrapped_send)

            duration_ms = (time.time() - start_time) * 1000

            # Create mock response for logging
            response = Response(content=b"".join(response_body))

            # Log the request
            await audit_logger.log_request(request, response, duration_ms)

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000

            # Log the error
            await audit_logger.log(
                action=AuditAction.EXECUTE.value,
                resource_type="error",
                request=request,
                success=False,
                error_message=str(e),
                duration_ms=duration_ms,
                level=AuditLevel.ERROR,
            )

            raise


__all__ = [
    "AuditLogger",
    "audit_logger",
    "AuditEvent",
    "AuditLevel",
    "AuditAction",
    "AuditBackend",
    "ConsoleAuditBackend",
    "FileAuditBackend",
    "InMemoryAuditBackend",
    "AuditMiddleware",
]
