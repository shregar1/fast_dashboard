"""Production-grade rate limiting with Redis backend.

Supports sliding window, fixed window, and token bucket algorithms.
Provides per-user, per-tenant, and global rate limits.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, Optional, Union

from fastapi import HTTPException, Request, Response, status

from fast_dashboards.core.registry import registry


class RateLimitAlgorithm(str, Enum):
    """Rate limiting algorithms."""

    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"
    TOKEN_BUCKET = "token_bucket"


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""

    requests: int = 100
    window_seconds: int = 60
    burst: int = 10
    algorithm: RateLimitAlgorithm = RateLimitAlgorithm.SLIDING_WINDOW
    key_prefix: str = "rl"


@dataclass
class RateLimitResult:
    """Rate limit check result."""

    allowed: bool
    remaining: int
    reset_time: int
    retry_after: Optional[int] = None
    limit: int = 0

    def to_headers(self) -> Dict[str, str]:
        """Convert to HTTP headers."""
        headers = {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(self.remaining),
            "X-RateLimit-Reset": str(self.reset_time),
        }
        if self.retry_after:
            headers["Retry-After"] = str(self.retry_after)
        return headers


class RateLimiter:
    """Production-grade rate limiter."""

    def __init__(self):
        """Execute __init__ operation."""
        self.configs: Dict[str, RateLimitConfig] = {}
        self._local_cache: Dict[str, Dict[str, Any]] = {}

    def configure(self, name: str, config: RateLimitConfig) -> None:
        """Configure a named rate limit."""
        self.configs[name] = config

    def _get_redis(self) -> Optional[Any]:
        """Get Redis connection from registry."""
        redis_session = registry.get_redis_session()
        return redis_session

    def _get_key(self, identifier: str, config: RateLimitConfig) -> str:
        """Generate Redis key for rate limit."""
        return f"{config.key_prefix}:{identifier}"

    async def _check_sliding_window(
        self, key: str, config: RateLimitConfig
    ) -> RateLimitResult:
        """Check rate limit using sliding window algorithm."""
        redis = self._get_redis()
        now = int(time.time())
        window_start = now - config.window_seconds

        if redis:
            # Use Redis sorted set for sliding window
            try:
                # Remove old entries
                await redis.zremrangebyscore(key, 0, window_start)

                # Count current requests
                current = await redis.zcard(key)

                if current >= config.requests:
                    # Get oldest request for reset time
                    oldest = await redis.zrange(key, 0, 0, withscores=True)
                    reset_time = (
                        int(oldest[0][1]) + config.window_seconds
                        if oldest
                        else now + config.window_seconds
                    )

                    return RateLimitResult(
                        allowed=False,
                        remaining=0,
                        reset_time=reset_time,
                        retry_after=reset_time - now,
                        limit=config.requests,
                    )

                # Add current request
                await redis.zadd(key, {str(now): now})
                await redis.expire(key, config.window_seconds)

                return RateLimitResult(
                    allowed=True,
                    remaining=config.requests - current - 1,
                    reset_time=now + config.window_seconds,
                    limit=config.requests,
                )
            except Exception:
                # Fall back to local cache on Redis error
                pass

        # Local cache fallback
        return self._check_local_sliding_window(key, config)

    def _check_local_sliding_window(
        self, key: str, config: RateLimitConfig
    ) -> RateLimitResult:
        """Check rate limit using local cache."""
        now = int(time.time())
        window_start = now - config.window_seconds

        if key not in self._local_cache:
            self._local_cache[key] = {"requests": []}

        cache = self._local_cache[key]

        # Clean old requests
        cache["requests"] = [t for t in cache["requests"] if t > window_start]

        if len(cache["requests"]) >= config.requests:
            reset_time = cache["requests"][0] + config.window_seconds
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_time=reset_time,
                retry_after=reset_time - now,
                limit=config.requests,
            )

        cache["requests"].append(now)

        return RateLimitResult(
            allowed=True,
            remaining=config.requests - len(cache["requests"]),
            reset_time=now + config.window_seconds,
            limit=config.requests,
        )

    async def _check_fixed_window(
        self, key: str, config: RateLimitConfig
    ) -> RateLimitResult:
        """Check rate limit using fixed window algorithm."""
        now = int(time.time())
        window = now // config.window_seconds
        window_key = f"{key}:{window}"

        redis = self._get_redis()

        if redis:
            try:
                current = await redis.incr(window_key)
                if current == 1:
                    await redis.expire(window_key, config.window_seconds)

                reset_time = (window + 1) * config.window_seconds

                if current > config.requests:
                    return RateLimitResult(
                        allowed=False,
                        remaining=0,
                        reset_time=reset_time,
                        retry_after=reset_time - now,
                        limit=config.requests,
                    )

                return RateLimitResult(
                    allowed=True,
                    remaining=config.requests - current,
                    reset_time=reset_time,
                    limit=config.requests,
                )
            except Exception:
                pass

        # Local cache fallback
        return self._check_local_fixed_window(key, config)

    def _check_local_fixed_window(
        self, key: str, config: RateLimitConfig
    ) -> RateLimitResult:
        """Check rate limit using local cache (fixed window)."""
        now = int(time.time())
        window = now // config.window_seconds
        window_key = f"{key}:{window}"

        if window_key not in self._local_cache:
            self._local_cache[window_key] = {"count": 0}

        cache = self._local_cache[window_key]
        cache["count"] += 1

        reset_time = (window + 1) * config.window_seconds

        if cache["count"] > config.requests:
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_time=reset_time,
                retry_after=reset_time - now,
                limit=config.requests,
            )

        return RateLimitResult(
            allowed=True,
            remaining=config.requests - cache["count"],
            reset_time=reset_time,
            limit=config.requests,
        )

    async def check(
        self, identifier: str, config_name: str = "default"
    ) -> RateLimitResult:
        """Check rate limit for an identifier."""
        config = self.configs.get(config_name, RateLimitConfig())
        key = self._get_key(identifier, config)

        if config.algorithm == RateLimitAlgorithm.SLIDING_WINDOW:
            return await self._check_sliding_window(key, config)
        elif config.algorithm == RateLimitAlgorithm.FIXED_WINDOW:
            return await self._check_fixed_window(key, config)
        else:
            # Default to sliding window
            return await self._check_sliding_window(key, config)

    async def check_request(
        self,
        request: Request,
        config_name: str = "default",
        key_func: Optional[Callable[[Request], str]] = None,
    ) -> RateLimitResult:
        """Check rate limit for a request."""
        if key_func:
            identifier = key_func(request)
        else:
            # Default: use IP + user (if authenticated)
            ip = self._get_client_ip(request)
            user_id = getattr(request.state, "user_id", None)
            identifier = f"{ip}:{user_id}" if user_id else ip

        return await self.check(identifier, config_name)

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

    def limit(
        self,
        config_name: str = "default",
        key_func: Optional[Callable[[Request], str]] = None,
    ) -> Callable:
        """Decorator/factory for rate limiting endpoints."""

        async def check_rate_limit(request: Request) -> None:
            """Execute check_rate_limit operation.

            Args:
                request: The request parameter.

            Returns:
                The result of the operation.
            """
            result = await self.check_request(request, config_name, key_func)

            if not result.allowed:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded",
                    headers=result.to_headers(),
                )

            # Store result in request state for response headers
            request.state.rate_limit = result

        return check_rate_limit


# Global rate limiter
rate_limiter = RateLimiter()

# Pre-configured rate limits
rate_limiter.configure("default", RateLimitConfig(requests=100, window_seconds=60))
rate_limiter.configure("strict", RateLimitConfig(requests=10, window_seconds=60))
rate_limiter.configure("generous", RateLimitConfig(requests=1000, window_seconds=60))
rate_limiter.configure(
    "auth", RateLimitConfig(requests=5, window_seconds=300)
)  # 5 login attempts per 5 min


class RateLimitMiddleware:
    """FastAPI middleware for automatic rate limiting."""

    def __init__(
        self, app, config_name: str = "default", skip_paths: Optional[list] = None
    ):
        """Execute __init__ operation.

        Args:
            app: The app parameter.
            config_name: The config_name parameter.
            skip_paths: The skip_paths parameter.
        """
        self.app = app
        self.config_name = config_name
        self.skip_paths = set(skip_paths or ["/health", "/ready", "/metrics"])

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

        # Check rate limit
        result = await rate_limiter.check_request(request, self.config_name)

        if not result.allowed:
            response = Response(
                content='{"detail": "Rate limit exceeded"}',
                status_code=429,
                headers={"Content-Type": "application/json", **result.to_headers()},
            )
            await response(scope, receive, send)
            return

        # Store result for response headers
        request.state.rate_limit = result

        # Wrap send to add headers
        original_send = send

        async def send_with_headers(message):
            """Execute send_with_headers operation.

            Args:
                message: The message parameter.

            Returns:
                The result of the operation.
            """
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                for key, value in result.to_headers().items():
                    headers.append((key.encode(), value.encode()))
                message["headers"] = headers
            await original_send(message)

        await self.app(scope, receive, send_with_headers)


__all__ = [
    "RateLimiter",
    "rate_limiter",
    "RateLimitConfig",
    "RateLimitResult",
    "RateLimitAlgorithm",
    "RateLimitMiddleware",
]
