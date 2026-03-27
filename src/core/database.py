"""Production-grade database utilities with transaction management.

Connection pooling, retry logic, circuit breaker pattern, and
automatic transaction handling.
"""

from __future__ import annotations

import functools
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum
from typing import Any, AsyncGenerator, Callable, Optional, TypeVar

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from fast_dashboards.core.registry import registry
from fast_dashboards.core.metrics import metrics


T = TypeVar("T")


class TransactionIsolationLevel(str, Enum):
    """SQL transaction isolation levels."""

    READ_UNCOMMITTED = "READ UNCOMMITTED"
    READ_COMMITTED = "READ COMMITTED"
    REPEATABLE_READ = "REPEATABLE READ"
    SERIALIZABLE = "SERIALIZABLE"


class CircuitBreakerState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, rejecting requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class RetryConfig:
    """Database retry configuration."""

    max_retries: int = 3
    base_delay: float = 0.1
    max_delay: float = 2.0
    exponential_base: float = 2.0
    retryable_exceptions: tuple = ()


class CircuitBreaker:
    """Circuit breaker pattern for database resilience."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
    ):
        """Execute __init__ operation.

        Args:
            failure_threshold: The failure_threshold parameter.
            recovery_timeout: The recovery_timeout parameter.
            half_open_max_calls: The half_open_max_calls parameter.
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.half_open_calls = 0

    def can_execute(self) -> bool:
        """Check if execution is allowed."""
        if self.state == CircuitBreakerState.CLOSED:
            return True

        if self.state == CircuitBreakerState.OPEN:
            if time.time() - (self.last_failure_time or 0) >= self.recovery_timeout:
                self.state = CircuitBreakerState.HALF_OPEN
                self.half_open_calls = 0
                return True
            return False

        if self.state == CircuitBreakerState.HALF_OPEN:
            return self.half_open_calls < self.half_open_max_calls

        return True

    def record_success(self):
        """Record a successful execution."""
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.half_open_max_calls:
                self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0
                self.success_count = 0
        else:
            self.failure_count = max(0, self.failure_count - 1)

    def record_failure(self):
        """Record a failed execution."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitBreakerState.HALF_OPEN:
            self.state = CircuitBreakerState.OPEN
        elif self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN

    async def execute(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute a function with circuit breaker protection."""
        if not self.can_execute():
            raise Exception("Circuit breaker is OPEN")

        if self.state == CircuitBreakerState.HALF_OPEN:
            self.half_open_calls += 1

        try:
            result = await func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            raise


# Global circuit breaker for database
db_circuit_breaker = CircuitBreaker()


async def retry_with_backoff(
    func: Callable[..., T], config: RetryConfig, *args, **kwargs
) -> T:
    """Execute a function with retry and exponential backoff."""
    last_exception = None

    for attempt in range(config.max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e

            # Check if exception is retryable
            if config.retryable_exceptions and not isinstance(
                e, config.retryable_exceptions
            ):
                raise

            if attempt < config.max_retries:
                delay = min(
                    config.base_delay * (config.exponential_base**attempt),
                    config.max_delay,
                )
                logger.warning(
                    f"Attempt {attempt + 1} failed, retrying in {delay:.2f}s: {e}"
                )
                await asyncio.sleep(delay)

    raise last_exception


@asynccontextmanager
async def transaction(
    isolation_level: Optional[TransactionIsolationLevel] = None,
    readonly: bool = False,
    retry_config: Optional[RetryConfig] = None,
) -> AsyncGenerator[AsyncSession, None]:
    """Database transaction context manager.

    Usage:
        async with transaction() as session:
            result = await session.execute(query)
            await session.commit()
    """
    db_session = registry.get_db_session()

    if db_session is None:
        raise Exception("Database session not available")

    # Check circuit breaker
    if not db_circuit_breaker.can_execute():
        raise Exception("Database circuit breaker is OPEN")

    start_time = time.time()

    try:
        # Set isolation level if specified
        if isolation_level:
            await db_session.execute(
                f"SET TRANSACTION ISOLATION LEVEL {isolation_level.value}"
            )

        # Set readonly if specified
        if readonly:
            await db_session.execute("SET TRANSACTION READ ONLY")

        yield db_session

        if not readonly:
            await db_session.commit()

        db_circuit_breaker.record_success()

    except Exception as e:
        db_circuit_breaker.record_failure()

        if not readonly:
            await db_session.rollback()

        raise

    finally:
        duration = time.time() - start_time
        metrics.track_db_query("transaction", "", duration)


@asynccontextmanager
async def read_only_transaction(
    isolation_level: TransactionIsolationLevel = TransactionIsolationLevel.READ_COMMITTED,
) -> AsyncGenerator[AsyncSession, None]:
    """Convenience context manager for read-only transactions."""
    async with transaction(isolation_level=isolation_level, readonly=True) as session:
        yield session


def transactional(
    isolation_level: Optional[TransactionIsolationLevel] = None,
    retry_config: Optional[RetryConfig] = None,
):
    """Decorator for transactional functions.

    Usage:
        @transactional()
        async def create_user(session: AsyncSession, user_data: dict) -> User:
            user = User(**user_data)
            session.add(user)
            return user
    """

    def decorator(func: Callable) -> Callable:
        """Execute decorator operation.

        Args:
            func: The func parameter.

        Returns:
            The result of the operation.
        """

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            """Execute wrapper operation.

            Returns:
                The result of the operation.
            """
            async with transaction(
                isolation_level, retry_config=retry_config
            ) as session:
                # Inject session as first argument if not provided
                if "session" not in kwargs and not any(
                    isinstance(arg, AsyncSession) for arg in args
                ):
                    return await func(session, *args, **kwargs)
                return await func(*args, **kwargs)

        return wrapper

    return decorator


def with_retry(config: Optional[RetryConfig] = None):
    """Decorator to add retry logic to database operations."""
    retry_cfg = config or RetryConfig()

    def decorator(func: Callable) -> Callable:
        """Execute decorator operation.

        Args:
            func: The func parameter.

        Returns:
            The result of the operation.
        """

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            """Execute wrapper operation.

            Returns:
                The result of the operation.
            """
            return await retry_with_backoff(func, retry_cfg, *args, **kwargs)

        return wrapper

    return decorator


class DatabaseManager:
    """High-level database management utilities."""

    def __init__(self):
        """Execute __init__ operation."""
        self.circuit_breaker = db_circuit_breaker

    async def health_check(self) -> bool:
        """Check database connectivity."""
        try:
            async with transaction(readonly=True) as session:
                await session.execute("SELECT 1")
            return True
        except Exception:
            return False

    async def get_stats(self) -> dict:
        """Get database statistics."""
        return {
            "circuit_breaker_state": self.circuit_breaker.state.value,
            "circuit_breaker_failures": self.circuit_breaker.failure_count,
        }

    def reset_circuit_breaker(self):
        """Manually reset the circuit breaker."""
        self.circuit_breaker.state = CircuitBreakerState.CLOSED
        self.circuit_breaker.failure_count = 0
        self.circuit_breaker.success_count = 0


# Global database manager
db_manager = DatabaseManager()


import asyncio

__all__ = [
    "transaction",
    "read_only_transaction",
    "transactional",
    "with_retry",
    "retry_with_backoff",
    "CircuitBreaker",
    "CircuitBreakerState",
    "RetryConfig",
    "TransactionIsolationLevel",
    "db_manager",
    "db_circuit_breaker",
]
