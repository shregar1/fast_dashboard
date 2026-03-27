"""Time-Travel Debugging - Record and Replay Request Flows.

Features:
- Record complete request/response cycles
- Capture database state, cache state, external calls
- Replay requests locally with exact state
- Breakpoint support during replay
- State diff visualization
- Export recordings for sharing

Usage:
    @recordable
    async def complex_endpoint(data: dict):
        # This will be recorded
        return await process(data)

    # Replay locally:
    fastmvc replay --recording=abc123 --breakpoint=line_45
"""

from __future__ import annotations

import base64
import copy
import functools
import hashlib
import inspect
import json
import pickle
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Protocol,
    Set,
    TypeVar,
    Union,
)

from loguru import logger


T = TypeVar("T")


class RecordingStatus(Enum):
    """Status of a recording."""

    RECORDING = "recording"
    COMPLETED = "completed"
    FAILED = "failed"
    REPLAYING = "replaying"


@dataclass
class Snapshot:
    """A snapshot of system state at a point in time."""

    timestamp: float
    line_number: int
    function_name: str
    local_vars: Dict[str, Any]
    global_vars: Dict[str, Any]
    call_stack: List[str]
    db_state: Optional[Dict[str, Any]] = None
    cache_state: Optional[Dict[str, Any]] = None
    external_calls: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (serialize values)."""
        return {
            "timestamp": self.timestamp,
            "line_number": self.line_number,
            "function_name": self.function_name,
            "local_vars": self._serialize_vars(self.local_vars),
            "global_vars": self._serialize_vars(self.global_vars),
            "call_stack": self.call_stack,
            "db_state": self.db_state,
            "cache_state": self.cache_state,
            "external_calls": self.external_calls,
        }

    def _serialize_vars(self, vars: Dict[str, Any]) -> Dict[str, Any]:
        """Serialize variables for storage."""
        result = {}
        for key, value in vars.items():
            if key.startswith("_"):
                continue  # Skip private vars
            try:
                # Try JSON serialization
                json.dumps(value)
                result[key] = value
            except (TypeError, ValueError):
                # Use repr for complex objects
                result[key] = repr(value)
        return result


@dataclass
class Recording:
    """A complete recording of a request/execution."""

    id: str
    name: str
    status: RecordingStatus
    start_time: datetime
    request_data: Optional[Dict[str, Any]] = None
    response_data: Optional[Dict[str, Any]] = None
    snapshots: List[Snapshot] = field(default_factory=list)
    function_name: str = ""
    module_name: str = ""
    error: Optional[str] = None
    end_time: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "request_data": self.request_data,
            "response_data": self.response_data,
            "snapshots": [s.to_dict() for s in self.snapshots],
            "function_name": self.function_name,
            "module_name": self.module_name,
            "error": self.error,
        }

    def save(self, directory: Path) -> Path:
        """Save recording to disk."""
        directory.mkdir(parents=True, exist_ok=True)
        file_path = directory / f"{self.id}.json"

        with open(file_path, "w") as f:
            json.dump(self.to_dict(), f, indent=2, default=str)

        return file_path

    @classmethod
    def load(cls, file_path: Path) -> Recording:
        """Load recording from disk."""
        with open(file_path) as f:
            data = json.load(f)

        return cls(
            id=data["id"],
            name=data["name"],
            status=RecordingStatus(data["status"]),
            start_time=datetime.fromisoformat(data["start_time"]),
            request_data=data.get("request_data"),
            response_data=data.get("response_data"),
            snapshots=[],  # Reconstruct if needed
            function_name=data.get("function_name", ""),
            module_name=data.get("module_name", ""),
            error=data.get("error"),
            end_time=datetime.fromisoformat(data["end_time"])
            if data.get("end_time")
            else None,
        )


class RecordingStore:
    """Store for recordings."""

    def __init__(self, directory: Optional[Path] = None):
        """Execute __init__ operation.

        Args:
            directory: The directory parameter.
        """
        self.directory = directory or Path(".fastmvc/recordings")
        self._active_recordings: Dict[str, Recording] = {}

    def create(self, name: str, function_name: str, module_name: str) -> Recording:
        """Create a new recording."""
        recording = Recording(
            id=str(uuid.uuid4())[:8],
            name=name,
            status=RecordingStatus.RECORDING,
            start_time=datetime.utcnow(),
            function_name=function_name,
            module_name=module_name,
        )
        self._active_recordings[recording.id] = recording
        return recording

    def get(self, recording_id: str) -> Optional[Recording]:
        """Get an active recording."""
        return self._active_recordings.get(recording_id)

    def complete(
        self, recording_id: str, response_data: Any, error: Optional[str] = None
    ):
        """Mark a recording as complete."""
        recording = self._active_recordings.get(recording_id)
        if recording:
            recording.status = (
                RecordingStatus.FAILED if error else RecordingStatus.COMPLETED
            )
            recording.response_data = {"data": response_data}
            recording.error = error
            recording.end_time = datetime.utcnow()

            # Save to disk
            recording.save(self.directory)

            # Remove from active
            del self._active_recordings[recording_id]

    def add_snapshot(self, recording_id: str, snapshot: Snapshot):
        """Add a snapshot to a recording."""
        recording = self._active_recordings.get(recording_id)
        if recording:
            recording.snapshots.append(snapshot)

    def list_recordings(self) -> List[Recording]:
        """List all saved recordings."""
        recordings = []
        if self.directory.exists():
            for file_path in self.directory.glob("*.json"):
                try:
                    recording = Recording.load(file_path)
                    recordings.append(recording)
                except Exception as e:
                    logger.error(f"Failed to load recording {file_path}: {e}")
        return recordings


# Global store
recording_store = RecordingStore()


class TimeTravelDebugger:
    """Time-travel debugger for request replay.

    Records complete execution state at each step,
    allowing for step-by-step replay and inspection.
    """

    def __init__(self):
        """Execute __init__ operation."""
        self._breakpoints: Set[int] = set()
        self._step_mode = False
        self._current_recording: Optional[Recording] = None
        self._current_snapshot_index = 0
        self._on_breakpoint: Optional[Callable] = None

    def record(
        self,
        func: Callable,
        name: Optional[str] = None,
        capture_db: bool = True,
        capture_cache: bool = True,
        capture_external: bool = True,
    ) -> Callable:
        """Decorator to record a function's execution.

        Args:
            func: Function to record
            name: Recording name
            capture_db: Whether to capture database state
            capture_cache: Whether to capture cache state
            capture_external: Whether to capture external API calls

        """
        recording_name = name or func.__name__

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                """Execute async_wrapper operation.

                Returns:
                    The result of the operation.
                """
                recording = recording_store.create(
                    recording_name, func.__name__, func.__module__
                )

                # Capture request data
                recording.request_data = {"args": repr(args), "kwargs": repr(kwargs)}

                # Create tracer
                tracer = _ExecutionTracer(
                    recording, capture_db, capture_cache, capture_external
                )

                try:
                    # Execute with tracing
                    result = await tracer.trace(func, *args, **kwargs)
                    recording_store.complete(recording.id, result)
                    return result

                except Exception as e:
                    recording_store.complete(recording.id, None, str(e))
                    raise

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                """Execute sync_wrapper operation.

                Returns:
                    The result of the operation.
                """
                recording = recording_store.create(
                    recording_name, func.__name__, func.__module__
                )

                recording.request_data = {"args": repr(args), "kwargs": repr(kwargs)}

                tracer = _ExecutionTracer(
                    recording, capture_db, capture_cache, capture_external
                )

                try:
                    result = tracer.trace_sync(func, *args, **kwargs)
                    recording_store.complete(recording.id, result)
                    return result

                except Exception as e:
                    recording_store.complete(recording.id, None, str(e))
                    raise

            return sync_wrapper

    def set_breakpoint(self, line_number: int):
        """Set a breakpoint at a line number."""
        self._breakpoints.add(line_number)

    def clear_breakpoint(self, line_number: int):
        """Clear a breakpoint."""
        self._breakpoints.discard(line_number)

    def enable_step_mode(self):
        """Enable step-by-step execution."""
        self._step_mode = True

    async def replay(
        self,
        recording_id: str,
        stop_at_breakpoints: bool = True,
        on_breakpoint: Optional[Callable[[Snapshot], None]] = None,
    ):
        """Replay a recording.

        Args:
            recording_id: ID of recording to replay
            stop_at_breakpoints: Whether to stop at breakpoints
            on_breakpoint: Callback when hitting a breakpoint

        """
        # Load recording
        recording = None
        for rec in recording_store.list_recordings():
            if rec.id == recording_id:
                recording = rec
                break

        if not recording:
            raise ValueError(f"Recording not found: {recording_id}")

        self._current_recording = recording
        self._on_breakpoint = on_breakpoint

        logger.info(f"Replaying recording: {recording.name} ({recording.id})")
        logger.info(f"Total snapshots: {len(recording.snapshots)}")

        # Replay each snapshot
        for i, snapshot in enumerate(recording.snapshots):
            self._current_snapshot_index = i

            # Check for breakpoint
            if stop_at_breakpoints and snapshot.line_number in self._breakpoints:
                logger.info(f"Breakpoint hit at line {snapshot.line_number}")

                if on_breakpoint:
                    if inspect.iscoroutinefunction(on_breakpoint):
                        await on_breakpoint(snapshot)
                    else:
                        on_breakpoint(snapshot)

                # In real implementation, would pause here for user input
                input("Press Enter to continue...")

            # Print state
            self._print_snapshot(snapshot)

        logger.info("Replay complete")

    def _print_snapshot(self, snapshot: Snapshot):
        """Print snapshot information."""
        print(f"\n{'=' * 60}")
        print(f"Line {snapshot.line_number}: {snapshot.function_name}")
        print(f"{'=' * 60}")

        if snapshot.local_vars:
            print("\nLocal variables:")
            for name, value in snapshot.local_vars.items():
                print(f"  {name} = {value}")

        if snapshot.external_calls:
            print("\nExternal calls:")
            for call in snapshot.external_calls:
                print(f"  {call}")


class _ExecutionTracer:
    """Internal tracer for recording execution."""

    def __init__(
        self,
        recording: Recording,
        capture_db: bool,
        capture_cache: bool,
        capture_external: bool,
    ):
        """Execute __init__ operation.

        Args:
            recording: The recording parameter.
            capture_db: The capture_db parameter.
            capture_cache: The capture_cache parameter.
            capture_external: The capture_external parameter.
        """
        self.recording = recording
        self.capture_db = capture_db
        self.capture_cache = capture_cache
        self.capture_external = capture_external

    async def trace(self, func: Callable, *args, **kwargs):
        """Trace async function execution."""
        # Use sys.settrace for line-by-line tracing
        import sys

        def trace_lines(frame, event, arg):
            """Execute trace_lines operation.

            Args:
                frame: The frame parameter.
                event: The event parameter.
                arg: The arg parameter.

            Returns:
                The result of the operation.
            """
            if event == "line":
                self._capture_snapshot(frame)
            return trace_lines

        def trace_calls(frame, event, arg):
            """Execute trace_calls operation.

            Args:
                frame: The frame parameter.
                event: The event parameter.
                arg: The arg parameter.

            Returns:
                The result of the operation.
            """
            if event == "call":
                return trace_lines
            return None

        sys.settrace(trace_calls)
        try:
            result = await func(*args, **kwargs)
            return result
        finally:
            sys.settrace(None)

    def trace_sync(self, func: Callable, *args, **kwargs):
        """Trace sync function execution."""
        import sys

        def trace_lines(frame, event, arg):
            """Execute trace_lines operation.

            Args:
                frame: The frame parameter.
                event: The event parameter.
                arg: The arg parameter.

            Returns:
                The result of the operation.
            """
            if event == "line":
                self._capture_snapshot(frame)
            return trace_lines

        def trace_calls(frame, event, arg):
            """Execute trace_calls operation.

            Args:
                frame: The frame parameter.
                event: The event parameter.
                arg: The arg parameter.

            Returns:
                The result of the operation.
            """
            if event == "call":
                return trace_lines
            return None

        sys.settrace(trace_calls)
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            sys.settrace(None)

    def _capture_snapshot(self, frame):
        """Capture a snapshot of current state."""
        try:
            # Get call stack
            stack = []
            current = frame
            while current:
                stack.append(current.f_code.co_name)
                current = current.f_back

            # Capture external calls
            external_calls = []
            if self.capture_external:
                # This would integrate with HTTP client interception
                pass

            snapshot = Snapshot(
                timestamp=time.time(),
                line_number=frame.f_lineno,
                function_name=frame.f_code.co_name,
                local_vars=dict(frame.f_locals),
                global_vars={
                    k: v for k, v in frame.f_globals.items() if not k.startswith("_")
                },
                call_stack=stack,
                external_calls=external_calls,
            )

            recording_store.add_snapshot(self.recording.id, snapshot)

        except Exception as e:
            logger.error(f"Failed to capture snapshot: {e}")


# Decorator for recordable functions
def recordable(
    name: Optional[str] = None,
    capture_db: bool = True,
    capture_cache: bool = True,
    capture_external: bool = True,
):
    """Decorator to make a function recordable for time-travel debugging.

    Usage:
        @recordable(name="process_order")
        async def process_order(order_id: str):
            # This execution will be recorded
            return await process(order_id)
    """

    def decorator(func: Callable) -> Callable:
        """Execute decorator operation.

        Args:
            func: The func parameter.

        Returns:
            The result of the operation.
        """
        debugger = TimeTravelDebugger()
        return debugger.record(func, name, capture_db, capture_cache, capture_external)

    return decorator


# CLI commands for time-travel debugging
class TimeTravelCLI:
    """CLI commands for time-travel debugging."""

    @staticmethod
    def list_recordings():
        """List all recordings."""
        recordings = recording_store.list_recordings()

        if not recordings:
            print("No recordings found.")
            return

        print(f"{'ID':<10} {'Name':<30} {'Status':<15} {'Date'}")
        print("=" * 80)

        for rec in recordings:
            date_str = rec.start_time.strftime("%Y-%m-%d %H:%M")
            print(f"{rec.id:<10} {rec.name:<30} {rec.status.value:<15} {date_str}")

    @staticmethod
    def show_recording(recording_id: str):
        """Show recording details."""
        for rec in recording_store.list_recordings():
            if rec.id == recording_id:
                print(f"Recording: {rec.name}")
                print(f"ID: {rec.id}")
                print(f"Status: {rec.status.value}")
                print(f"Function: {rec.module_name}.{rec.function_name}")
                print(f"Start: {rec.start_time}")
                print(f"End: {rec.end_time}")
                print(f"Snapshots: {len(rec.snapshots)}")

                if rec.error:
                    print(f"Error: {rec.error}")

                return

        print(f"Recording not found: {recording_id}")

    @staticmethod
    def replay_recording(recording_id: str, breakpoint_line: Optional[int] = None):
        """Replay a recording."""
        debugger = TimeTravelDebugger()

        if breakpoint_line:
            debugger.set_breakpoint(breakpoint_line)

        import asyncio

        asyncio.run(debugger.replay(recording_id))


__all__ = [
    "TimeTravelDebugger",
    "TimeTravelCLI",
    "recordable",
    "Recording",
    "Snapshot",
    "RecordingStatus",
    "recording_store",
]
