"""Tests for Saga Pattern."""

import asyncio
import pytest
from unittest.mock import AsyncMock, Mock, patch

from fast_dashboards.core.saga import (
    Saga,
    SagaBuilder,
    SagaStep,
    SagaStepResult,
    SagaContext,
    SagaExecution,
    SagaStatus,
    SagaStepStatus,
    InMemorySagaStore,
    step,
    ok,
    fail,
)


class TestSagaContext:
    """Tests for SagaContext."""

    def test_context_creation(self):
        """Test creating a context."""
        ctx = SagaContext(saga_id="test-123")

        assert ctx.saga_id == "test-123"
        assert ctx.data == {}

    def test_context_get_set(self):
        """Test getting and setting values."""
        ctx = SagaContext(saga_id="test-123")

        ctx.set("key", "value")
        assert ctx.get("key") == "value"
        assert ctx.get("missing", "default") == "default"


class TestSagaStepResult:
    """Tests for SagaStepResult."""

    def test_success_result(self):
        """Test creating a success result."""
        result = SagaStepResult(
            success=True, data={"id": 123}, compensation_data={"ref": "abc"}
        )

        assert result.success is True
        assert result.data == {"id": 123}
        assert result.compensation_data == {"ref": "abc"}

    def test_failure_result(self):
        """Test creating a failure result."""
        result = SagaStepResult(success=False, error="Something went wrong")

        assert result.success is False
        assert result.error == "Something went wrong"


class TestSagaBuilder:
    """Tests for SagaBuilder."""

    def test_builder_creation(self):
        """Test creating a builder."""
        builder = SagaBuilder("test_saga")

        assert builder.name == "test_saga"
        assert builder.steps == []

    def test_add_step(self):
        """Test adding a step."""
        builder = SagaBuilder("test_saga")

        async def action(ctx):
            """Execute action operation.

            Args:
                ctx: The ctx parameter.

            Returns:
                The result of the operation.
            """
            return ok()

        builder.step("step1", action)

        assert len(builder.steps) == 1
        assert builder.steps[0].name == "step1"

    def test_add_step_with_compensation(self):
        """Test adding a step with compensation."""
        builder = SagaBuilder("test_saga")

        async def action(ctx):
            """Execute action operation.

            Args:
                ctx: The ctx parameter.

            Returns:
                The result of the operation.
            """
            return ok()

        async def compensate(ctx, data):
            """Execute compensate operation.

            Args:
                ctx: The ctx parameter.
                data: The data parameter.

            Returns:
                The result of the operation.
            """
            pass

        builder.step("step1", action, compensation=compensate)

        assert builder.steps[0].compensation is not None

    def test_with_timeout(self):
        """Test setting timeout."""
        builder = SagaBuilder("test_saga")
        builder.with_timeout(30.0)

        assert builder.timeout == 30.0

    def test_with_parallel_compensation(self):
        """Test enabling parallel compensation."""
        builder = SagaBuilder("test_saga")
        builder.with_parallel_compensation()

        assert builder.parallel_compensation is True

    def test_build(self):
        """Test building a saga."""
        builder = SagaBuilder("test_saga")

        async def action(ctx):
            """Execute action operation.

            Args:
                ctx: The ctx parameter.

            Returns:
                The result of the operation.
            """
            return ok()

        saga = builder.step("step1", action).build()

        assert isinstance(saga, Saga)
        assert saga.name == "test_saga"
        assert len(saga.steps) == 1


class TestSaga:
    """Tests for Saga execution."""

    @pytest.mark.asyncio
    async def test_successful_execution(self):
        """Test successful saga execution."""

        async def action1(ctx):
            """Execute action1 operation.

            Args:
                ctx: The ctx parameter.

            Returns:
                The result of the operation.
            """
            return ok(data={"step": 1})

        async def action2(ctx):
            """Execute action2 operation.

            Args:
                ctx: The ctx parameter.

            Returns:
                The result of the operation.
            """
            return ok(data={"step": 2})

        saga = SagaBuilder("test").step("step1", action1).step("step2", action2).build()

        execution = await saga.execute()

        assert execution.status == SagaStatus.COMPLETED
        assert execution.error is None

    @pytest.mark.asyncio
    async def test_failed_execution_with_compensation(self):
        """Test failed execution triggers compensation."""
        compensate_called = []

        async def action1(ctx):
            """Execute action1 operation.

            Args:
                ctx: The ctx parameter.

            Returns:
                The result of the operation.
            """
            return ok(compensation_data={"id": 1})

        async def compensate1(ctx, data):
            """Execute compensate1 operation.

            Args:
                ctx: The ctx parameter.
                data: The data parameter.

            Returns:
                The result of the operation.
            """
            compensate_called.append(data)

        async def action2(ctx):
            """Execute action2 operation.

            Args:
                ctx: The ctx parameter.

            Returns:
                The result of the operation.
            """
            return fail("Something failed")

        saga = (
            SagaBuilder("test")
            .step("step1", action1, compensation=compensate1)
            .step("step2", action2)
            .build()
        )

        execution = await saga.execute()

        assert execution.status == SagaStatus.FAILED
        assert "Something failed" in execution.error
        assert len(compensate_called) == 1

    @pytest.mark.asyncio
    async def test_step_retries(self):
        """Test step retry mechanism."""
        attempt_count = 0

        async def flaky_action(ctx):
            """Execute flaky_action operation.

            Args:
                ctx: The ctx parameter.

            Returns:
                The result of the operation.
            """
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                return fail("Temporary error")
            return ok()

        saga = (
            SagaBuilder("test")
            .step("step1", flaky_action, retry_count=3, retry_delay=0.01)
            .build()
        )

        execution = await saga.execute()

        assert execution.status == SagaStatus.COMPLETED
        assert attempt_count == 3

    @pytest.mark.asyncio
    async def test_step_condition(self):
        """Test conditional step execution."""
        action_called = False

        async def conditional_action(ctx):
            """Execute conditional_action operation.

            Args:
                ctx: The ctx parameter.

            Returns:
                The result of the operation.
            """
            nonlocal action_called
            action_called = True
            return ok()

        def should_run(ctx):
            """Execute should_run operation.

            Args:
                ctx: The ctx parameter.

            Returns:
                The result of the operation.
            """
            return ctx.get("run_step") is True

        saga = (
            SagaBuilder("test")
            .step("step1", conditional_action, condition=should_run)
            .build()
        )

        # Execute with condition=False
        execution = await saga.execute({"run_step": False})

        assert execution.status == SagaStatus.COMPLETED
        assert action_called is False

        # Execute with condition=True
        action_called = False
        execution = await saga.execute({"run_step": True})

        assert action_called is True

    @pytest.mark.asyncio
    async def test_parallel_steps(self):
        """Test parallel step execution."""
        execution_order = []

        async def action1(ctx):
            """Execute action1 operation.

            Args:
                ctx: The ctx parameter.

            Returns:
                The result of the operation.
            """
            await asyncio.sleep(0.05)
            execution_order.append(1)
            return ok()

        async def action2(ctx):
            """Execute action2 operation.

            Args:
                ctx: The ctx parameter.

            Returns:
                The result of the operation.
            """
            execution_order.append(2)
            return ok()

        saga = (
            SagaBuilder("test")
            .step("step1", action1, parallel=True)
            .step("step2", action2, parallel=True)
            .build()
        )

        execution = await saga.execute()

        assert execution.status == SagaStatus.COMPLETED
        # step2 should finish before step1 due to sleep
        assert execution_order == [2, 1]

    @pytest.mark.asyncio
    async def test_step_timeout(self):
        """Test step timeout handling."""

        async def slow_action(ctx):
            """Execute slow_action operation.

            Args:
                ctx: The ctx parameter.

            Returns:
                The result of the operation.
            """
            await asyncio.sleep(10)
            return ok()

        saga = SagaBuilder("test").step("step1", slow_action, timeout=0.01).build()

        execution = await saga.execute()

        assert execution.status == SagaStatus.FAILED
        # Should have timed out

    @pytest.mark.asyncio
    async def test_status_change_callback(self):
        """Test status change notification."""
        status_changes = []

        def on_status_change(execution):
            """Execute on_status_change operation.

            Args:
                execution: The execution parameter.

            Returns:
                The result of the operation.
            """
            status_changes.append(execution.status)

        async def action(ctx):
            """Execute action operation.

            Args:
                ctx: The ctx parameter.

            Returns:
                The result of the operation.
            """
            return ok()

        saga = SagaBuilder("test").step("step1", action).build()
        saga.on_status_change(on_status_change)

        execution = await saga.execute()

        assert SagaStatus.COMPLETED in status_changes


class TestInMemorySagaStore:
    """Tests for InMemorySagaStore."""

    @pytest.fixture
    def store(self):
        """Execute store operation.

        Returns:
            The result of the operation.
        """
        return InMemorySagaStore()

    @pytest.mark.asyncio
    async def test_save_and_load(self, store):
        """Test saving and loading executions."""
        execution = SagaExecution(
            saga_id="test-123",
            saga_name="test",
            status=SagaStatus.COMPLETED,
            steps=[],
            start_time=__import__("datetime").datetime.utcnow(),
        )

        await store.save(execution)
        loaded = await store.load("test-123")

        assert loaded is not None
        assert loaded.saga_id == "test-123"
        assert loaded.status == SagaStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_list_by_status(self, store):
        """Test listing by status."""
        from datetime import datetime

        completed = SagaExecution(
            saga_id="completed-1",
            saga_name="test",
            status=SagaStatus.COMPLETED,
            steps=[],
            start_time=datetime.utcnow(),
        )

        failed = SagaExecution(
            saga_id="failed-1",
            saga_name="test",
            status=SagaStatus.FAILED,
            steps=[],
            start_time=datetime.utcnow(),
        )

        await store.save(completed)
        await store.save(failed)

        completed_list = await store.list_by_status(SagaStatus.COMPLETED)

        assert len(completed_list) == 1
        assert completed_list[0].saga_id == "completed-1"


class TestHelpers:
    """Tests for helper functions."""

    def test_ok_helper(self):
        """Test ok() helper."""
        result = ok(data={"id": 1}, compensation_data={"ref": "abc"})

        assert result.success is True
        assert result.data == {"id": 1}
        assert result.compensation_data == {"ref": "abc"}

    def test_fail_helper(self):
        """Test fail() helper."""
        result = fail("Error message")

        assert result.success is False
        assert result.error == "Error message"

    def test_step_helper(self):
        """Test step() helper."""

        async def action(ctx):
            """Execute action operation.

            Args:
                ctx: The ctx parameter.

            Returns:
                The result of the operation.
            """
            return ok()

        async def compensate(ctx, data):
            """Execute compensate operation.

            Args:
                ctx: The ctx parameter.
                data: The data parameter.

            Returns:
                The result of the operation.
            """
            pass

        s = step("test_step", action, compensation=compensate, retry_count=3)

        assert s.name == "test_step"
        assert s.compensation is not None
        assert s.retry_count == 3


class TestIntegration:
    """Integration tests for saga pattern."""

    @pytest.mark.asyncio
    async def test_ecommerce_order_saga(self):
        """Test a complete e-commerce order saga."""
        inventory_reserved = []
        payment_processed = []
        shipment_created = []

        compensations = []

        async def reserve_inventory(ctx):
            """Execute reserve_inventory operation.

            Args:
                ctx: The ctx parameter.

            Returns:
                The result of the operation.
            """
            inventory_reserved.append(ctx.get("order_id"))
            return ok(
                data={"reservation_id": "inv-123"},
                compensation_data={"reservation_id": "inv-123"},
            )

        async def release_inventory(ctx, data):
            """Execute release_inventory operation.

            Args:
                ctx: The ctx parameter.
                data: The data parameter.

            Returns:
                The result of the operation.
            """
            compensations.append("inventory")

        async def process_payment(ctx):
            """Execute process_payment operation.

            Args:
                ctx: The ctx parameter.

            Returns:
                The result of the operation.
            """
            payment_processed.append(ctx.get("order_id"))
            return ok(
                data={"payment_id": "pay-456"},
                compensation_data={"payment_id": "pay-456"},
            )

        async def refund_payment(ctx, data):
            """Execute refund_payment operation.

            Args:
                ctx: The ctx parameter.
                data: The data parameter.

            Returns:
                The result of the operation.
            """
            compensations.append("payment")

        async def create_shipment(ctx):
            """Execute create_shipment operation.

            Args:
                ctx: The ctx parameter.

            Returns:
                The result of the operation.
            """
            shipment_created.append(ctx.get("order_id"))
            return ok(data={"shipment_id": "ship-789"})

        saga = (
            SagaBuilder("order_processing")
            .step(
                "reserve_inventory", reserve_inventory, compensation=release_inventory
            )
            .step("process_payment", process_payment, compensation=refund_payment)
            .step("create_shipment", create_shipment)
            .build()
        )

        execution = await saga.execute({"order_id": "order-123"})

        assert execution.status == SagaStatus.COMPLETED
        assert len(inventory_reserved) == 1
        assert len(payment_processed) == 1
        assert len(shipment_created) == 1
        assert len(compensations) == 0

    @pytest.mark.asyncio
    async def test_failed_order_with_full_compensation(self):
        """Test failed order with full compensation."""
        compensations = []

        async def reserve_inventory(ctx):
            """Execute reserve_inventory operation.

            Args:
                ctx: The ctx parameter.

            Returns:
                The result of the operation.
            """
            return ok(compensation_data={"id": 1})

        async def release_inventory(ctx, data):
            """Execute release_inventory operation.

            Args:
                ctx: The ctx parameter.
                data: The data parameter.

            Returns:
                The result of the operation.
            """
            compensations.append("inventory")

        async def process_payment(ctx):
            """Execute process_payment operation.

            Args:
                ctx: The ctx parameter.

            Returns:
                The result of the operation.
            """
            return ok(compensation_data={"id": 2})

        async def refund_payment(ctx, data):
            """Execute refund_payment operation.

            Args:
                ctx: The ctx parameter.
                data: The data parameter.

            Returns:
                The result of the operation.
            """
            compensations.append("payment")

        async def create_shipment(ctx):
            """Execute create_shipment operation.

            Args:
                ctx: The ctx parameter.

            Returns:
                The result of the operation.
            """
            return fail("Shipping service unavailable")

        saga = (
            SagaBuilder("order_processing")
            .step(
                "reserve_inventory", reserve_inventory, compensation=release_inventory
            )
            .step("process_payment", process_payment, compensation=refund_payment)
            .step("create_shipment", create_shipment)
            .build()
        )

        execution = await saga.execute()

        assert execution.status == SagaStatus.FAILED
        # Both previous steps should be compensated
        assert "payment" in compensations
        assert "inventory" in compensations


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
