"""Module order_lifecycle.py."""

from __future__ import annotations

from typing import Any, Dict, Optional

from loguru import logger

from .engine import IWorkflowEngine, build_workflow_engine


class OrderWorkflowService:
    """Facade for starting and inspecting order lifecycle workflows."""

    def __init__(self, engine: Optional[IWorkflowEngine] = None) -> None:
        """Execute __init__ operation.

        Args:
            engine: The engine parameter.
        """
        self._engine = engine or build_workflow_engine()

    async def start_order_lifecycle(
        self, order_id: str, tenant_id: str, payload: Dict[str, Any]
    ) -> Optional[str]:
        """Execute start_order_lifecycle operation.

        Args:
            order_id: The order_id parameter.
            tenant_id: The tenant_id parameter.
            payload: The payload parameter.

        Returns:
            The result of the operation.
        """
        if self._engine is None:
            logger.info(
                "Workflow engine is not configured; skipping order workflow for %s",
                order_id,
            )
            return None
        return await self._engine.start_order_workflow(order_id, tenant_id, payload)

    async def get_order_status(self, workflow_id: str) -> Dict[str, Any]:
        """Execute get_order_status operation.

        Args:
            workflow_id: The workflow_id parameter.

        Returns:
            The result of the operation.
        """
        if self._engine is None or workflow_id is None:
            return {"workflowId": workflow_id or "", "status": "unknown"}
        return await self._engine.get_order_status(workflow_id)
