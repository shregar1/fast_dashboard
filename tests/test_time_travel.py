"""Tests for Time-Travel Debugging."""

import json
import pytest
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import Mock, patch

from fast_dashboards.core.time_travel import (
    TimeTravelDebugger,
    TimeTravelCLI,
    Recording,
    Snapshot,
    RecordingStatus,
    recording_store,
    recordable,
)


class TestSnapshot:
    """Tests for Snapshot."""

    def test_snapshot_creation(self):
        """Test creating a snapshot."""
        snapshot = Snapshot(
            timestamp=1234567890.0,
            line_number=42,
            function_name="test_func",
            local_vars={"x": 10, "y": 20},
            global_vars={"GLOBAL": "value"},
            call_stack=["test_func", "caller"],
        )

        assert snapshot.timestamp == 1234567890.0
        assert snapshot.line_number == 42
        assert snapshot.function_name == "test_func"

    def test_snapshot_to_dict(self):
        """Test converting snapshot to dict."""
        snapshot = Snapshot(
            timestamp=1234567890.0,
            line_number=42,
            function_name="test_func",
            local_vars={"x": 10},
            global_vars={},
            call_stack=["test_func"],
        )

        data = snapshot.to_dict()

        assert data["line_number"] == 42
        assert data["function_name"] == "test_func"
        assert "local_vars" in data


class TestRecording:
    """Tests for Recording."""

    @pytest.fixture
    def sample_recording(self):
        """Execute sample_recording operation.

        Returns:
            The result of the operation.
        """
        return Recording(
            id="abc123",
            name="test_recording",
            status=RecordingStatus.COMPLETED,
            start_time=__import__("datetime").datetime.utcnow(),
            function_name="test_func",
            module_name="test_module",
        )

    def test_recording_creation(self, sample_recording):
        """Test creating a recording."""
        assert sample_recording.id == "abc123"
        assert sample_recording.name == "test_recording"
        assert sample_recording.status == RecordingStatus.COMPLETED

    def test_recording_to_dict(self, sample_recording):
        """Test converting recording to dict."""
        data = sample_recording.to_dict()

        assert data["id"] == "abc123"
        assert data["name"] == "test_recording"
        assert data["status"] == "completed"

    def test_save_and_load(self, sample_recording, tmp_path):
        """Test saving and loading a recording."""
        file_path = sample_recording.save(tmp_path)

        assert file_path.exists()

        loaded = Recording.load(file_path)

        assert loaded.id == "abc123"
        assert loaded.name == "test_recording"


class TestRecordingStore:
    """Tests for RecordingStore."""

    @pytest.fixture
    def store(self, tmp_path):
        """Execute store operation.

        Args:
            tmp_path: The tmp_path parameter.

        Returns:
            The result of the operation.
        """
        return recording_store.__class__(directory=tmp_path)

    def test_create_recording(self, store):
        """Test creating a recording."""
        recording = store.create(
            name="test", function_name="test_func", module_name="test_module"
        )

        assert recording.name == "test"
        assert recording.status == RecordingStatus.RECORDING
        assert len(recording.id) > 0

    def test_get_recording(self, store):
        """Test getting a recording."""
        recording = store.create("test", "func", "module")

        retrieved = store.get(recording.id)

        assert retrieved is not None
        assert retrieved.id == recording.id

    def test_complete_recording(self, store):
        """Test completing a recording."""
        recording = store.create("test", "func", "module")

        store.complete(recording.id, {"result": "success"})

        assert recording.status == RecordingStatus.COMPLETED
        assert recording.response_data is not None

    def test_complete_with_error(self, store):
        """Test completing a recording with error."""
        recording = store.create("test", "func", "module")

        store.complete(recording.id, None, "Something failed")

        assert recording.status == RecordingStatus.FAILED
        assert recording.error == "Something failed"

    def test_add_snapshot(self, store):
        """Test adding a snapshot."""
        recording = store.create("test", "func", "module")

        snapshot = Snapshot(
            timestamp=1234567890.0,
            line_number=42,
            function_name="test_func",
            local_vars={},
            global_vars={},
            call_stack=[],
        )

        store.add_snapshot(recording.id, snapshot)

        assert len(recording.snapshots) == 1
        assert recording.snapshots[0].line_number == 42


class TestTimeTravelDebugger:
    """Tests for TimeTravelDebugger."""

    def test_set_breakpoint(self):
        """Test setting a breakpoint."""
        debugger = TimeTravelDebugger()

        debugger.set_breakpoint(42)

        assert 42 in debugger._breakpoints

    def test_clear_breakpoint(self):
        """Test clearing a breakpoint."""
        debugger = TimeTravelDebugger()
        debugger.set_breakpoint(42)

        debugger.clear_breakpoint(42)

        assert 42 not in debugger._breakpoints

    def test_enable_step_mode(self):
        """Test enabling step mode."""
        debugger = TimeTravelDebugger()

        debugger.enable_step_mode()

        assert debugger._step_mode is True


class TestRecordableDecorator:
    """Tests for @recordable decorator."""

    def test_sync_function_recording(self):
        """Test recording a sync function."""

        @recordable(name="test_sync")
        def test_func(x, y):
            """Execute test_func operation.

            Args:
                x: The x parameter.
                y: The y parameter.

            Returns:
                The result of the operation.
            """
            return x + y

        result = test_func(10, 20)

        assert result == 30

    @pytest.mark.asyncio
    async def test_async_function_recording(self):
        """Test recording an async function."""
        import asyncio

        @recordable(name="test_async")
        async def test_async_func(x):
            """Execute test_async_func operation.

            Args:
                x: The x parameter.

            Returns:
                The result of the operation.
            """
            await asyncio.sleep(0.01)
            return x * 2

        result = await test_async_func(5)

        assert result == 10


class TestTimeTravelCLI:
    """Tests for TimeTravelCLI."""

    def test_list_recordings_empty(self, capsys, tmp_path):
        """Test listing recordings when none exist."""
        # Create a fresh store with no recordings
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create empty directory
            store = recording_store.__class__(directory=Path(tmp_dir))

            # List should not error even with no recordings
            TimeTravelCLI.list_recordings()

            captured = capsys.readouterr()
            # Output may contain table headers but no data rows
            assert "ID" in captured.out or "No recordings" in captured.out


class TestIntegration:
    """Integration tests for time-travel debugging."""

    def test_full_recording_workflow(self, tmp_path):
        """Test complete recording workflow."""
        # Create a new store pointing to temp path
        from fast_dashboards.core.time_travel import RecordingStore

        store = RecordingStore(directory=tmp_path)

        # Create a recording manually
        recording = store.create(
            name="order_processing", function_name="process_order", module_name="orders"
        )

        # Add request data
        recording.request_data = {"order_id": "order-123", "amount": 99.99}

        # Add snapshots
        snapshot1 = Snapshot(
            timestamp=time.time(),
            line_number=10,
            function_name="process_order",
            local_vars={"order_id": "order-123"},
            global_vars={},
            call_stack=["process_order"],
        )

        snapshot2 = Snapshot(
            timestamp=time.time(),
            line_number=25,
            function_name="validate_order",
            local_vars={"is_valid": True},
            global_vars={},
            call_stack=["validate_order", "process_order"],
        )

        store.add_snapshot(recording.id, snapshot1)
        store.add_snapshot(recording.id, snapshot2)

        # Complete recording
        store.complete(recording.id, {"status": "success"})

        # Verify
        assert recording.status == RecordingStatus.COMPLETED
        assert len(recording.snapshots) == 2

        # Save and reload
        file_path = recording.save(tmp_path)
        loaded = Recording.load(file_path)

        assert loaded.id == recording.id
        assert loaded.name == "order_processing"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
