"""Mock start_utils module."""

from contextlib import asynccontextmanager, contextmanager
from typing import Any, AsyncGenerator, Generator


class MockDBSession:
    """Mock database session."""

    async def execute(self, *args, **kwargs):
        """Execute execute operation.

        Returns:
            The result of the operation.
        """
        return None

    async def __aenter__(self):
        """Execute __aenter__ operation.

        Returns:
            The result of the operation.
        """
        return self

    async def __aexit__(self, *args):
        """Execute __aexit__ operation.

        Returns:
            The result of the operation.
        """
        pass


class MockRedisSession:
    """Mock Redis session."""

    async def ping(self):
        """Execute ping operation.

        Returns:
            The result of the operation.
        """
        return False

    async def info(self):
        """Execute info operation.

        Returns:
            The result of the operation.
        """
        return {}

    async def __aenter__(self):
        """Execute __aenter__ operation.

        Returns:
            The result of the operation.
        """
        return self

    async def __aexit__(self, *args):
        """Execute __aexit__ operation.

        Returns:
            The result of the operation.
        """
        pass


@asynccontextmanager
async def db_session() -> AsyncGenerator[MockDBSession, None]:
    """Mock database session context manager."""
    yield MockDBSession()


@asynccontextmanager
async def redis_session() -> AsyncGenerator[MockRedisSession, None]:
    """Mock Redis session context manager."""
    yield MockRedisSession()
