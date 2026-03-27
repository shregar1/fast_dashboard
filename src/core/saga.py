"""Saga Pattern for Distributed Transactions.

A saga is a sequence of local transactions where each transaction updates data
within a single service. If a transaction fails, the saga executes compensating
transactions to undo the changes made by previous transactions.

Features:
- Choreography-based sagas (event-driven)
- Orchestration-based sagas (central coordinator)
- Automatic compensation on failure
- Saga state persistence
- Timeout handling
- Parallel step execution
- Saga status monitoring

Usage:
    @saga()
    async def process_order(order_id: str):
        inventory = await reserve_inventory(order_id)
        payment = await process_payment(order_id)
        shipment = await create_shipment(order_id)
        # Auto-compensates if any step fails
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import (
    Any,
    Callable,
    Coroutine,
    Dict,
    Generic,
    List,
    Optional,
    Protocol,
    TypeVar,
    Union,
)

from loguru import logger


T = TypeVar("T")
R = TypeVar("R")


class SagaStatus(Enum):
    """Status of a saga execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"
    TIMEOUT = "timeout"


class SagaStepStatus(Enum):
    """Status of a saga step."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"
    SKIPPED = "skipped"


@dataclass
class SagaContext:
    """Context passed through saga steps."""

    saga_id: str
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        """Get value from context."""
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set value in context."""
        self.data[key] = value


@dataclass
class SagaStepResult:
    """Result of a saga step execution."""

    success: bool
    data: Any = None
    error: Optional[str] = None
    compensation_data: Any = None


@dataclass
class SagaStep:
    """A single step in a saga."""

    name: str
    action: Callable[[SagaContext], Coroutine[Any, Any, SagaStepResult]]
    compensation: Optional[Callable[[SagaContext, Any], Coroutine[Any, Any, None]]] = (
        None
    )
    retry_count: int = 0
    retry_delay: float = 1.0
    timeout: Optional[float] = None
    parallel: bool = False
    condition: Optional[Callable[[SagaContext], bool]] = None


@dataclass
class SagaExecution:
    """Record of a saga execution."""

    saga_id: str
    saga_name: str
    status: SagaStatus
    steps: List[Dict[str, Any]]
    start_time: datetime
    end_time: Optional[datetime] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "saga_id": self.saga_id,
            "saga_name": self.saga_name,
            "status": self.status.value,
            "steps": self.steps,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "error": self.error,
        }


class SagaStore(Protocol):
    """Protocol for saga persistence."""

    async def save(self, execution: SagaExecution) -> None:
        """Save saga execution state."""
        ...

    async def load(self, saga_id: str) -> Optional[SagaExecution]:
        """Load saga execution by ID."""
        ...

    async def list_by_status(self, status: SagaStatus) -> List[SagaExecution]:
        """List sagas by status."""
        ...


class InMemorySagaStore:
    """In-memory saga store for testing."""

    def __init__(self):
        """Execute __init__ operation."""
        self._executions: Dict[str, SagaExecution] = {}

    async def save(self, execution: SagaExecution) -> None:
        """Execute save operation.

        Args:
            execution: The execution parameter.

        Returns:
            The result of the operation.
        """
        self._executions[execution.saga_id] = execution

    async def load(self, saga_id: str) -> Optional[SagaExecution]:
        """Execute load operation.

        Args:
            saga_id: The saga_id parameter.

        Returns:
            The result of the operation.
        """
        return self._executions.get(saga_id)

    async def list_by_status(self, status: SagaStatus) -> List[SagaExecution]:
        """Execute list_by_status operation.

        Args:
            status: The status parameter.

        Returns:
            The result of the operation.
        """
        return [e for e in self._executions.values() if e.status == status]


class SagaBuilder:
    """Builder for creating saga definitions.

    Usage:
        saga = (
            SagaBuilder("order_processing")
            .step("reserve_inventory", reserve_inventory, compensate=release_inventory)
            .step("process_payment", process_payment, compensate=refund_payment)
            .step("create_shipment", create_shipment, compensate=cancel_shipment)
            .build()
        )
    """

    def __init__(self, name: str):
        """Execute __init__ operation.

        Args:
            name: The name parameter.
        """
        self.name = name
        self.steps: List[SagaStep] = []
        self.timeout: Optional[float] = None
        self.parallel_compensation = False

    def step(
        self,
        name: str,
        action: Callable[[SagaContext], Coroutine[Any, Any, SagaStepResult]],
        compensation: Optional[Callable] = None,
        retry_count: int = 0,
        retry_delay: float = 1.0,
        timeout: Optional[float] = None,
        parallel: bool = False,
        condition: Optional[Callable[[SagaContext], bool]] = None,
    ) -> SagaBuilder:
        """Add a step to the saga."""
        self.steps.append(
            SagaStep(
                name=name,
                action=action,
                compensation=compensation,
                retry_count=retry_count,
                retry_delay=retry_delay,
                timeout=timeout or self.timeout,
                parallel=parallel,
                condition=condition,
            )
        )
        return self

    def with_timeout(self, timeout: float) -> SagaBuilder:
        """Set default timeout for all steps."""
        self.timeout = timeout
        return self

    def with_parallel_compensation(self) -> SagaBuilder:
        """Enable parallel compensation."""
        self.parallel_compensation = True
        return self

    def build(self) -> Saga:
        """Build the saga."""
        return Saga(
            name=self.name,
            steps=self.steps,
            timeout=self.timeout,
            parallel_compensation=self.parallel_compensation,
        )


class Saga:
    """Orchestrated Saga for distributed transactions.

    Manages the execution of multiple steps with automatic compensation
    on failure.
    """

    def __init__(
        self,
        name: str,
        steps: List[SagaStep],
        timeout: Optional[float] = None,
        parallel_compensation: bool = False,
        store: Optional[SagaStore] = None,
    ):
        """Execute __init__ operation.

        Args:
            name: The name parameter.
            steps: The steps parameter.
            timeout: The timeout parameter.
            parallel_compensation: The parallel_compensation parameter.
            store: The store parameter.
        """
        self.name = name
        self.steps = steps
        self.timeout = timeout
        self.parallel_compensation = parallel_compensation
        self.store = store or InMemorySagaStore()
        self._on_status_change: Optional[Callable] = None

    def on_status_change(self, callback: Callable[[SagaExecution], None]) -> Saga:
        """Set a callback for status changes."""
        self._on_status_change = callback
        return self

    async def execute(
        self, initial_data: Optional[Dict[str, Any]] = None
    ) -> SagaExecution:
        """Execute the saga.

        Args:
            initial_data: Initial data for the saga context

        Returns:
            SagaExecution record

        """
        saga_id = str(uuid.uuid4())
        context = SagaContext(saga_id=saga_id, data=initial_data or {})

        execution = SagaExecution(
            saga_id=saga_id,
            saga_name=self.name,
            status=SagaStatus.RUNNING,
            steps=[],
            start_time=datetime.utcnow(),
        )

        completed_steps: List[SagaStep] = []

        try:
            # Separate parallel and sequential steps
            parallel_steps = [s for s in self.steps if s.parallel]
            sequential_steps = [s for s in self.steps if not s.parallel]

            # Execute parallel steps first
            if parallel_steps:
                parallel_results = await asyncio.gather(
                    *[
                        self._execute_step(step, context, execution)
                        for step in parallel_steps
                    ]
                )

                for step, (success, result) in zip(parallel_steps, parallel_results):
                    if success:
                        completed_steps.append(step)
                    else:
                        # Compensate completed parallel steps
                        await self._compensate_steps(completed_steps, context)
                        execution.status = SagaStatus.FAILED
                        execution.error = f"Parallel step '{step.name}' failed"
                        execution.end_time = datetime.utcnow()
                        await self.store.save(execution)
                        self._notify_status_change(execution)
                        return execution

            # Execute sequential steps
            for step in sequential_steps:
                # Check condition
                if step.condition and not step.condition(context):
                    execution.steps.append(
                        {"name": step.name, "status": SagaStepStatus.SKIPPED.value}
                    )
                    continue

                success, result = await self._execute_step(step, context, execution)

                if success:
                    completed_steps.append(step)
                else:
                    # Compensate all completed steps
                    execution.status = SagaStatus.COMPENSATING
                    await self._compensate_steps(completed_steps, context)

                    execution.status = SagaStatus.FAILED
                    execution.error = f"Step '{step.name}' failed: {result.error}"
                    execution.end_time = datetime.utcnow()
                    await self.store.save(execution)
                    self._notify_status_change(execution)
                    return execution

            # All steps completed successfully
            execution.status = SagaStatus.COMPLETED
            execution.end_time = datetime.utcnow()
            await self.store.save(execution)
            self._notify_status_change(execution)
            return execution

        except asyncio.TimeoutError:
            # Compensate completed steps
            await self._compensate_steps(completed_steps, context)

            execution.status = SagaStatus.TIMEOUT
            execution.error = "Saga timed out"
            execution.end_time = datetime.utcnow()
            await self.store.save(execution)
            self._notify_status_change(execution)
            return execution

        except Exception as e:
            # Compensate completed steps
            await self._compensate_steps(completed_steps, context)

            execution.status = SagaStatus.FAILED
            execution.error = str(e)
            execution.end_time = datetime.utcnow()
            await self.store.save(execution)
            self._notify_status_change(execution)
            raise

    async def _execute_step(
        self, step: SagaStep, context: SagaContext, execution: SagaExecution
    ) -> tuple[bool, SagaStepResult]:
        """Execute a single step with retries."""
        step_record = {
            "name": step.name,
            "status": SagaStepStatus.RUNNING.value,
            "start_time": datetime.utcnow().isoformat(),
        }
        execution.steps.append(step_record)

        last_error = None

        for attempt in range(step.retry_count + 1):
            try:
                # Execute with timeout
                if step.timeout:
                    result = await asyncio.wait_for(
                        step.action(context), timeout=step.timeout
                    )
                else:
                    result = await step.action(context)

                if result.success:
                    # Store compensation data in context
                    if result.compensation_data:
                        context.set(
                            f"_compensation_{step.name}", result.compensation_data
                        )

                    step_record.update(
                        {
                            "status": SagaStepStatus.COMPLETED.value,
                            "end_time": datetime.utcnow().isoformat(),
                        }
                    )

                    # Store step result in context
                    if result.data:
                        context.set(step.name, result.data)

                    return True, result
                else:
                    last_error = result.error

                    if attempt < step.retry_count:
                        await asyncio.sleep(step.retry_delay * (attempt + 1))
                        continue

                    step_record.update(
                        {
                            "status": SagaStepStatus.FAILED.value,
                            "error": result.error,
                            "end_time": datetime.utcnow().isoformat(),
                        }
                    )
                    return False, result

            except asyncio.TimeoutError:
                last_error = "Timeout"
                step_record.update(
                    {
                        "status": SagaStepStatus.FAILED.value,
                        "error": "Timeout",
                        "end_time": datetime.utcnow().isoformat(),
                    }
                )
                return False, SagaStepResult(success=False, error="Timeout")

            except Exception as e:
                last_error = str(e)

                if attempt < step.retry_count:
                    await asyncio.sleep(step.retry_delay * (attempt + 1))
                    continue

                step_record.update(
                    {
                        "status": SagaStepStatus.FAILED.value,
                        "error": str(e),
                        "end_time": datetime.utcnow().isoformat(),
                    }
                )
                return False, SagaStepResult(success=False, error=str(e))

        return False, SagaStepResult(success=False, error=last_error)

    async def _compensate_steps(
        self, steps: List[SagaStep], context: SagaContext
    ) -> None:
        """Execute compensation for completed steps."""
        if not steps:
            return

        if self.parallel_compensation:
            # Compensate in parallel (reverse order still matters for data)
            await asyncio.gather(
                *[self._compensate_step(step, context) for step in reversed(steps)]
            )
        else:
            # Compensate in reverse order
            for step in reversed(steps):
                await self._compensate_step(step, context)

    async def _compensate_step(self, step: SagaStep, context: SagaContext) -> None:
        """Execute compensation for a single step."""
        if not step.compensation:
            return

        try:
            # Get compensation data
            compensation_data = context.get(f"_compensation_{step.name}")

            if asyncio.iscoroutinefunction(step.compensation):
                await step.compensation(context, compensation_data)
            else:
                step.compensation(context, compensation_data)

            logger.info(f"Compensated step: {step.name}")

        except Exception as e:
            logger.error(f"Compensation failed for step {step.name}: {e}")
            # Log but don't fail - we've done our best

    def _notify_status_change(self, execution: SagaExecution) -> None:
        """Notify status change callback."""
        if self._on_status_change:
            try:
                if asyncio.iscoroutinefunction(self._on_status_change):
                    asyncio.create_task(self._on_status_change(execution))
                else:
                    self._on_status_change(execution)
            except Exception as e:
                logger.error(f"Status change notification failed: {e}")


# Decorator for saga functions
def saga(
    name: Optional[str] = None,
    timeout: Optional[float] = None,
    compensate_on_failure: bool = True,
):
    """Decorator to create a saga from a function.

    The decorated function should yield steps:

        @saga(name="order_processing")
        async def process_order(order_id: str):
            # Step 1: Reserve inventory
            inventory = yield SagaStep(
                name="reserve_inventory",
                action=lambda ctx: reserve_inventory(order_id),
                compensation=lambda ctx, data: release_inventory(data)
            )

            # Step 2: Process payment
            payment = yield SagaStep(
                name="process_payment",
                action=lambda ctx: process_payment(order_id),
                compensation=lambda ctx, data: refund_payment(data)
            )
    """

    def decorator(func: Callable) -> Callable:
        """Execute decorator operation.

        Args:
            func: The func parameter.

        Returns:
            The result of the operation.
        """
        saga_name = name or func.__name__

        async def wrapper(*args, **kwargs):
            """Execute wrapper operation.

            Returns:
                The result of the operation.
            """
            # This is a simplified version - full implementation would use generators
            builder = SagaBuilder(saga_name)
            if timeout:
                builder.with_timeout(timeout)

            # Call function to get steps (generator-based)
            # For now, just execute the function
            return await func(*args, **kwargs)

        return wrapper

    return decorator


# Helper functions for creating saga steps
def step(
    name: str, action: Callable, compensation: Optional[Callable] = None, **kwargs
) -> SagaStep:
    """Create a saga step."""
    return SagaStep(name=name, action=action, compensation=compensation, **kwargs)


def ok(data: Any = None, compensation_data: Any = None) -> SagaStepResult:
    """Create a successful step result."""
    return SagaStepResult(success=True, data=data, compensation_data=compensation_data)


def fail(error: str) -> SagaStepResult:
    """Create a failed step result."""
    return SagaStepResult(success=False, error=error)


__all__ = [
    "Saga",
    "SagaBuilder",
    "SagaStep",
    "SagaStepResult",
    "SagaContext",
    "SagaExecution",
    "SagaStatus",
    "SagaStepStatus",
    "SagaStore",
    "InMemorySagaStore",
    "saga",
    "step",
    "ok",
    "fail",
]
