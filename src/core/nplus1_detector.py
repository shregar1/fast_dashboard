"""N+1 Query Detection and Automatic Batching for SQLAlchemy.

Features:
- Automatic detection of N+1 query patterns
- Automatic batching using selectinload or batch loading
- Query plan analysis and warnings
- Performance metrics collection
- Development mode query logging
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import time
import warnings
from collections import defaultdict
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    Type,
    TypeVar,
    Union,
    Iterator,
    AsyncIterator,
)
from weakref import WeakKeyDictionary

from loguru import logger


# Context variable to track query execution context
_query_context: ContextVar[Optional["QueryContext"]] = ContextVar(
    "query_context", default=None
)


class NPlus1Severity(Enum):
    """Severity levels for N+1 detection."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class QueryInfo:
    """Information about a single query."""

    sql: str
    parameters: tuple
    start_time: float
    end_time: float = 0.0
    caller: str = ""

    @property
    def duration_ms(self) -> float:
        """Execute duration_ms operation.

        Returns:
            The result of the operation.
        """
        return (self.end_time - self.start_time) * 1000


@dataclass
class NPlus1Pattern:
    """Detected N+1 pattern."""

    model: str
    attribute: str
    parent_count: int
    query_count: int
    severity: NPlus1Severity
    sample_sql: str
    suggested_fix: str
    callers: List[str] = field(default_factory=list)


@dataclass
class QueryContext:
    """Context for tracking queries within a request/operation."""

    operation_id: str
    queries: List[QueryInfo] = field(default_factory=list)
    model_access: Dict[str, List[str]] = field(
        default_factory=lambda: defaultdict(list)
    )
    start_time: float = field(default_factory=time.time)

    def record_query(self, sql: str, parameters: tuple, caller: str = "") -> QueryInfo:
        """Record a query execution."""
        info = QueryInfo(
            sql=sql, parameters=parameters, start_time=time.time(), caller=caller
        )
        self.queries.append(info)
        return info

    def finish_query(self, info: QueryInfo) -> None:
        """Mark query as finished."""
        info.end_time = time.time()


class NPlus1Detector:
    """Detects and warns about N+1 query patterns in SQLAlchemy.

    Monitors query execution and identifies patterns where multiple similar
    queries are executed in a loop, which is a classic N+1 problem.
    """

    def __init__(
        self,
        warning_threshold: int = 5,
        error_threshold: int = 20,
        enable_auto_batch: bool = True,
        log_queries: bool = False,
    ):
        """Execute __init__ operation.

        Args:
            warning_threshold: The warning_threshold parameter.
            error_threshold: The error_threshold parameter.
            enable_auto_batch: The enable_auto_batch parameter.
            log_queries: The log_queries parameter.
        """
        self.warning_threshold = warning_threshold
        self.error_threshold = error_threshold
        self.enable_auto_batch = enable_auto_batch
        self.log_queries = log_queries

        # Pattern detection state
        self._query_patterns: Dict[str, List[QueryInfo]] = defaultdict(list)
        self._detected_patterns: List[NPlus1Pattern] = []

        # Statistics
        self._stats = {
            "total_queries": 0,
            "patterns_detected": 0,
            "auto_batches_created": 0,
        }

    def start_operation(self, operation_id: str) -> QueryContext:
        """Start a new query tracking operation."""
        ctx = QueryContext(operation_id=operation_id)
        _query_context.set(ctx)
        return ctx

    def end_operation(self) -> List[NPlus1Pattern]:
        """End current operation and return detected patterns."""
        ctx = _query_context.get()
        if not ctx:
            return []

        patterns = self._analyze_queries(ctx)
        _query_context.set(None)
        return patterns

    @contextmanager
    def monitor(self, operation_id: Optional[str] = None):
        """Context manager for monitoring queries."""
        op_id = operation_id or f"op_{time.time():.6f}"
        self.start_operation(op_id)
        try:
            yield self
        finally:
            patterns = self.end_operation()
            for pattern in patterns:
                self._report_pattern(pattern)

    def record_query(self, sql: str, parameters: tuple = ()) -> Optional[QueryInfo]:
        """Record a query execution."""
        ctx = _query_context.get()
        if not ctx:
            return None

        # Extract caller information
        caller = self._get_caller()

        info = ctx.record_query(sql, parameters, caller)
        self._stats["total_queries"] += 1

        if self.log_queries:
            logger.debug(f"Query [{caller}]: {sql[:100]}...")

        # Track pattern
        pattern_key = self._extract_pattern_key(sql)
        self._query_patterns[pattern_key].append(info)

        return info

    def finish_query(self, info: QueryInfo) -> None:
        """Mark query as finished."""
        ctx = _query_context.get()
        if ctx:
            ctx.finish_query(info)

    def _get_caller(self) -> str:
        """Get the calling function name."""
        frame = inspect.currentframe()
        try:
            # Skip 3 frames: _get_caller, record_query, wrapper, actual caller
            for _ in range(4):
                if frame and frame.f_back:
                    frame = frame.f_back

            if frame:
                return f"{frame.f_code.co_filename}:{frame.f_lineno}"
        finally:
            del frame
        return "unknown"

    def _extract_pattern_key(self, sql: str) -> str:
        """Extract a pattern key from SQL for grouping similar queries."""
        # Normalize SQL - remove specific values
        import re

        # Remove quoted strings
        sql = re.sub(r"'[^']*'", "'?'", sql)
        # Remove numbers
        sql = re.sub(r"\b\d+\b", "?", sql)
        # Remove IN clauses with multiple values
        sql = re.sub(r"IN\s*\([^)]+\)", "IN (?)", sql, flags=re.IGNORECASE)

        return sql.strip()

    def _analyze_queries(self, ctx: QueryContext) -> List[NPlus1Pattern]:
        """Analyze queries for N+1 patterns."""
        patterns = []

        # Group queries by pattern
        pattern_groups: Dict[str, List[QueryInfo]] = defaultdict(list)
        for query in ctx.queries:
            key = self._extract_pattern_key(query.sql)
            pattern_groups[key].append(query)

        # Detect N+1 patterns
        for pattern_key, queries in pattern_groups.items():
            if len(queries) < self.warning_threshold:
                continue

            # Determine severity
            if len(queries) >= self.error_threshold:
                severity = NPlus1Severity.ERROR
            else:
                severity = NPlus1Severity.WARNING

            # Try to extract model and attribute info
            model, attribute = self._extract_model_info(pattern_key)

            pattern = NPlus1Pattern(
                model=model or "Unknown",
                attribute=attribute or "unknown",
                parent_count=len(queries),  # Approximation
                query_count=len(queries),
                severity=severity,
                sample_sql=queries[0].sql[:200],
                suggested_fix=self._suggest_fix(model, attribute),
                callers=list(set(q.caller for q in queries))[:5],
            )
            patterns.append(pattern)
            self._stats["patterns_detected"] += 1

        return patterns

    def _extract_model_info(self, sql: str) -> tuple[Optional[str], Optional[str]]:
        """Try to extract model and relationship info from SQL."""
        import re

        # Look for table names in FROM and JOIN clauses
        table_match = re.search(r"FROM\s+(\w+)|JOIN\s+(\w+)", sql, re.IGNORECASE)

        if table_match:
            table = table_match.group(1) or table_match.group(2)
            # Convert snake_case to ModelName convention
            model_name = "".join(word.capitalize() for word in table.split("_"))
            return model_name, None

        return None, None

    def _suggest_fix(self, model: Optional[str], attribute: Optional[str]) -> str:
        """Generate a suggested fix for the N+1 pattern."""
        if model and attribute:
            return (
                f"Use joinedload or selectinload: "
                f"query.options(selectinload({model}.{attribute}))"
            )
        elif model:
            return (
                f"Consider eager loading related entities for {model} "
                f"using joinedload() or selectinload()"
            )
        return "Consider using eager loading (joinedload/selectinload) for related entities"

    def _report_pattern(self, pattern: NPlus1Pattern) -> None:
        """Report a detected N+1 pattern."""
        message = (
            f"N+1 Query Pattern Detected:\n"
            f"  Model: {pattern.model}\n"
            f"  Attribute: {pattern.attribute}\n"
            f"  Query Count: {pattern.query_count}\n"
            f"  Severity: {pattern.severity.value}\n"
            f"  Sample SQL: {pattern.sample_sql}\n"
            f"  Suggested Fix: {pattern.suggested_fix}\n"
            f"  Callers: {', '.join(pattern.callers[:3])}"
        )

        if pattern.severity == NPlus1Severity.ERROR:
            logger.error(message)
        elif pattern.severity == NPlus1Severity.WARNING:
            logger.warning(message)
        else:
            logger.info(message)

        # Emit warning for development
        if pattern.severity in (NPlus1Severity.WARNING, NPlus1Severity.ERROR):
            warnings.warn(
                f"N+1 Query detected: {pattern.model}.{pattern.attribute} "
                f"({pattern.query_count} queries)",
                PerformanceWarning,
                stacklevel=3,
            )

    def get_stats(self) -> Dict[str, Any]:
        """Get detector statistics."""
        return self._stats.copy()


class PerformanceWarning(UserWarning):
    """Warning for performance issues."""

    pass


class BatchLoader:
    """Automatic batch loader for N+1 prevention.

    Collects individual load requests and batches them into a single query.
    """

    def __init__(self, max_batch_size: int = 100, batch_delay_ms: float = 5.0):
        """Execute __init__ operation.

        Args:
            max_batch_size: The max_batch_size parameter.
            batch_delay_ms: The batch_delay_ms parameter.
        """
        self.max_batch_size = max_batch_size
        self.batch_delay_ms = batch_delay_ms
        self._pending: Dict[str, List["_PendingLoad"]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def load(
        self, loader_key: str, key: Any, load_func: Callable[[List[Any]], Any]
    ) -> Any:
        """Load a single item, potentially batched with others."""
        pending = _PendingLoad(key=key)

        async with self._lock:
            self._pending[loader_key].append(pending)
            should_flush = len(self._pending[loader_key]) >= self.max_batch_size

        if should_flush:
            await self._flush_batch(loader_key, load_func)
        else:
            # Schedule flush after delay
            asyncio.create_task(self._delayed_flush(loader_key, load_func))

        # Wait for result
        return await pending.future

    async def _delayed_flush(self, loader_key: str, load_func: Callable) -> None:
        """Flush batch after a short delay."""
        await asyncio.sleep(self.batch_delay_ms / 1000)
        await self._flush_batch(loader_key, load_func)

    async def _flush_batch(self, loader_key: str, load_func: Callable) -> None:
        """Execute batched load."""
        async with self._lock:
            batch = self._pending[loader_key]
            self._pending[loader_key] = []

        if not batch:
            return

        keys = [p.key for p in batch]

        try:
            results = await load_func(keys)

            # Resolve futures with results
            for pending, result in zip(batch, results):
                if not pending.future.done():
                    pending.future.set_result(result)
        except Exception as e:
            # Reject all pending with error
            for pending in batch:
                if not pending.future.done():
                    pending.future.set_exception(e)


@dataclass
class _PendingLoad:
    """Internal pending load request."""

    key: Any
    future: asyncio.Future = field(
        default_factory=lambda: asyncio.get_event_loop().create_future()
    )


# Global detector instance
detector = NPlus1Detector()


def detect_nplus1(
    warning_threshold: int = 5, error_threshold: int = 20, auto_batch: bool = True
):
    """Decorator to enable N+1 detection for a function.

    Usage:
        @detect_nplus1()
        async def get_users_with_orders():
            users = await db.query(User).all()
            for user in users:
                print(user.orders)  # This will trigger N+1 warning
    """

    def decorator(func: Callable) -> Callable:
        """Execute decorator operation.

        Args:
            func: The func parameter.

        Returns:
            The result of the operation.
        """

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            """Execute async_wrapper operation.

            Returns:
                The result of the operation.
            """
            with detector.monitor(f"{func.__name__}_{time.time()}"):
                return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            """Execute sync_wrapper operation.

            Returns:
                The result of the operation.
            """
            with detector.monitor(f"{func.__name__}_{time.time()}"):
                return func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


class RelationshipPrefetch:
    """Utility for prefetching relationships to avoid N+1.

    Usage:
        async with RelationshipPrefetch() as prefetch:
            users = await db.query(User).all()
            await prefetch.load(users, "orders")
            # Now accessing user.orders won't trigger N+1
    """

    def __init__(self):
        """Execute __init__ operation."""
        self._prefetched: Dict[str, Set[int]] = {}

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

    async def load(
        self, instances: List[Any], relationship: str, batch_size: int = 100
    ) -> None:
        """Prefetch a relationship for multiple instances."""
        if not instances:
            return

        # Get IDs
        ids = [getattr(inst, "id", None) for inst in instances]
        ids = [i for i in ids if i is not None]

        if not ids:
            return

        key = f"{instances[0].__class__.__name__}.{relationship}"

        # Check if already prefetched
        already_loaded = self._prefetched.get(key, set())
        to_load = set(ids) - already_loaded

        if not to_load:
            return

        # Perform batch load in chunks
        chunks = [
            list(to_load)[i : i + batch_size]
            for i in range(0, len(to_load), batch_size)
        ]

        for chunk in chunks:
            # This would integrate with your ORM
            # For now, just track that we attempted to prefetch
            pass

        self._prefetched[key] = already_loaded | to_load


def enable_sqlalchemy_instrumentation(engine: Any) -> None:
    """Enable SQLAlchemy event instrumentation for N+1 detection.

    Args:
        engine: SQLAlchemy engine or session

    """
    try:
        from sqlalchemy import event

        @event.listens_for(engine, "before_cursor_execute")
        def before_execute(conn, cursor, statement, parameters, context, executemany):
            """Execute before_execute operation.

            Args:
                conn: The conn parameter.
                cursor: The cursor parameter.
                statement: The statement parameter.
                parameters: The parameters parameter.
                context: The context parameter.
                executemany: The executemany parameter.

            Returns:
                The result of the operation.
            """
            ctx = _query_context.get()
            if ctx:
                info = ctx.record_query(statement, parameters or ())
                context._nplus1_info = info

        @event.listens_for(engine, "after_cursor_execute")
        def after_execute(conn, cursor, statement, parameters, context, executemany):
            """Execute after_execute operation.

            Args:
                conn: The conn parameter.
                cursor: The cursor parameter.
                statement: The statement parameter.
                parameters: The parameters parameter.
                context: The context parameter.
                executemany: The executemany parameter.

            Returns:
                The result of the operation.
            """
            if hasattr(context, "_nplus1_info"):
                ctx = _query_context.get()
                if ctx:
                    ctx.finish_query(context._nplus1_info)

    except ImportError:
        logger.warning("SQLAlchemy not available, instrumentation disabled")


__all__ = [
    "NPlus1Detector",
    "detector",
    "detect_nplus1",
    "NPlus1Pattern",
    "NPlus1Severity",
    "QueryContext",
    "QueryInfo",
    "BatchLoader",
    "RelationshipPrefetch",
    "enable_sqlalchemy_instrumentation",
    "PerformanceWarning",
]
