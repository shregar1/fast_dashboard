"""Production-grade webhook system for event-driven architecture.

Supports webhook registration, event delivery with retries,
signature verification, and delivery logging.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol

import httpx
from pydantic import BaseModel, HttpUrl, validator

from fast_dashboards.core.registry import registry


class WebhookEventType(str, Enum):
    """Standard webhook event types."""

    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_DELETED = "user.deleted"

    TENANT_CREATED = "tenant.created"
    TENANT_UPDATED = "tenant.updated"
    TENANT_DELETED = "tenant.deleted"

    JOB_STARTED = "job.started"
    JOB_COMPLETED = "job.completed"
    JOB_FAILED = "job.failed"

    CONFIG_CHANGED = "config.changed"

    CUSTOM = "custom"


class WebhookStatus(str, Enum):
    """Webhook delivery status."""

    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"


class WebhookAuthType(str, Enum):
    """Webhook authentication types."""

    NONE = "none"
    HMAC = "hmac"
    BEARER = "bearer"
    API_KEY = "api_key"


class WebhookSubscription(BaseModel):
    """Webhook subscription model."""

    id: str
    url: HttpUrl
    events: List[str]
    secret: str  # For HMAC signature
    auth_type: WebhookAuthType = WebhookAuthType.HMAC
    auth_token: Optional[str] = None  # For bearer or API key auth
    active: bool = True
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    max_retries: int = 3
    retry_delay_seconds: int = 60

    @validator("events")
    def validate_events(cls, v):
        """Execute validate_events operation.

        Args:
            v: The v parameter.

        Returns:
            The result of the operation.
        """
        if not v:
            raise ValueError("At least one event type is required")
        return v


@dataclass
class WebhookDelivery:
    """Webhook delivery record."""

    id: str
    subscription_id: str
    event_type: str
    payload: Dict[str, Any]
    status: WebhookStatus
    attempts: int = 0
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    delivered_at: Optional[str] = None
    response_status: Optional[int] = None
    response_body: Optional[str] = None
    error_message: Optional[str] = None


class WebhookStore(Protocol):
    """Protocol for webhook storage backend."""

    async def save_subscription(self, subscription: WebhookSubscription) -> None:
        """Save a webhook subscription."""
        ...

    async def get_subscription(
        self, subscription_id: str
    ) -> Optional[WebhookSubscription]:
        """Get a subscription by ID."""
        ...

    async def list_subscriptions(
        self, event_type: Optional[str] = None, active_only: bool = True
    ) -> List[WebhookSubscription]:
        """List subscriptions."""
        ...

    async def delete_subscription(self, subscription_id: str) -> bool:
        """Delete a subscription."""
        ...

    async def save_delivery(self, delivery: WebhookDelivery) -> None:
        """Save a delivery record."""
        ...

    async def get_pending_deliveries(self) -> List[WebhookDelivery]:
        """Get pending deliveries for retry."""
        ...


class InMemoryWebhookStore:
    """In-memory webhook store for development."""

    def __init__(self):
        """Execute __init__ operation."""
        self.subscriptions: Dict[str, WebhookSubscription] = {}
        self.deliveries: Dict[str, WebhookDelivery] = {}

    async def save_subscription(self, subscription: WebhookSubscription) -> None:
        """Execute save_subscription operation.

        Args:
            subscription: The subscription parameter.

        Returns:
            The result of the operation.
        """
        self.subscriptions[subscription.id] = subscription

    async def get_subscription(
        self, subscription_id: str
    ) -> Optional[WebhookSubscription]:
        """Execute get_subscription operation.

        Args:
            subscription_id: The subscription_id parameter.

        Returns:
            The result of the operation.
        """
        return self.subscriptions.get(subscription_id)

    async def list_subscriptions(
        self, event_type: Optional[str] = None, active_only: bool = True
    ) -> List[WebhookSubscription]:
        """Execute list_subscriptions operation.

        Args:
            event_type: The event_type parameter.
            active_only: The active_only parameter.

        Returns:
            The result of the operation.
        """
        subs = list(self.subscriptions.values())
        if active_only:
            subs = [s for s in subs if s.active]
        if event_type:
            subs = [s for s in subs if event_type in s.events or "*" in s.events]
        return subs

    async def delete_subscription(self, subscription_id: str) -> bool:
        """Execute delete_subscription operation.

        Args:
            subscription_id: The subscription_id parameter.

        Returns:
            The result of the operation.
        """
        if subscription_id in self.subscriptions:
            del self.subscriptions[subscription_id]
            return True
        return False

    async def save_delivery(self, delivery: WebhookDelivery) -> None:
        """Execute save_delivery operation.

        Args:
            delivery: The delivery parameter.

        Returns:
            The result of the operation.
        """
        self.deliveries[delivery.id] = delivery

    async def get_pending_deliveries(self) -> List[WebhookDelivery]:
        """Execute get_pending_deliveries operation.

        Returns:
            The result of the operation.
        """
        return [
            d
            for d in self.deliveries.values()
            if d.status in [WebhookStatus.PENDING, WebhookStatus.RETRYING]
            and d.attempts < 3
        ]


class WebhookManager:
    """Production-grade webhook manager."""

    def __init__(self, store: Optional[WebhookStore] = None):
        """Execute __init__ operation.

        Args:
            store: The store parameter.
        """
        self.store = store or InMemoryWebhookStore()
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=False,
                limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
            )
        return self._http_client

    def _generate_signature(self, payload: str, secret: str) -> str:
        """Generate HMAC signature for webhook payload."""
        return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()

    def _verify_signature(self, payload: str, signature: str, secret: str) -> bool:
        """Verify webhook signature."""
        expected = self._generate_signature(payload, secret)
        return hmac.compare_digest(expected, signature)

    async def register(
        self,
        url: str,
        events: List[str],
        secret: Optional[str] = None,
        auth_type: WebhookAuthType = WebhookAuthType.HMAC,
        auth_token: Optional[str] = None,
    ) -> WebhookSubscription:
        """Register a new webhook subscription."""
        subscription = WebhookSubscription(
            id=f"wh_{secrets.token_hex(8)}",
            url=url,
            events=events,
            secret=secret or secrets.token_urlsafe(32),
            auth_type=auth_type,
            auth_token=auth_token,
        )

        await self.store.save_subscription(subscription)
        return subscription

    async def unregister(self, subscription_id: str) -> bool:
        """Unregister a webhook subscription."""
        return await self.store.delete_subscription(subscription_id)

    async def trigger(
        self, event_type: str, payload: Dict[str, Any], tenant_id: Optional[str] = None
    ) -> List[WebhookDelivery]:
        """Trigger a webhook event to all matching subscriptions."""
        subscriptions = await self.store.list_subscriptions(event_type=event_type)

        deliveries = []
        for sub in subscriptions:
            # Filter by tenant if specified
            if tenant_id and sub.events != ["*"]:
                # Skip tenant-specific filtering for now
                pass

            delivery = WebhookDelivery(
                id=f"d_{secrets.token_hex(8)}",
                subscription_id=sub.id,
                event_type=event_type,
                payload=payload,
                status=WebhookStatus.PENDING,
            )

            await self.store.save_delivery(delivery)
            deliveries.append(delivery)

            # Schedule delivery (in production, use a task queue)
            # For now, we'll deliver asynchronously
            asyncio.create_task(self._deliver(sub, delivery))

        return deliveries

    async def _deliver(
        self, subscription: WebhookSubscription, delivery: WebhookDelivery
    ) -> None:
        """Deliver a webhook."""
        client = await self._get_client()

        # Prepare payload
        event_data = {
            "id": delivery.id,
            "type": delivery.event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": delivery.payload,
        }
        payload_json = json.dumps(event_data, default=str)

        # Prepare headers
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "FastMVC-Webhook/1.0",
            "X-Webhook-ID": delivery.id,
            "X-Event-Type": delivery.event_type,
            "X-Attempt": str(delivery.attempts + 1),
        }

        # Add authentication
        if subscription.auth_type == WebhookAuthType.HMAC:
            signature = self._generate_signature(payload_json, subscription.secret)
            headers["X-Webhook-Signature"] = f"sha256={signature}"
        elif (
            subscription.auth_type == WebhookAuthType.BEARER and subscription.auth_token
        ):
            headers["Authorization"] = f"Bearer {subscription.auth_token}"
        elif (
            subscription.auth_type == WebhookAuthType.API_KEY
            and subscription.auth_token
        ):
            headers["X-API-Key"] = subscription.auth_token

        # Attempt delivery
        delivery.attempts += 1

        try:
            response = await client.post(
                str(subscription.url), content=payload_json, headers=headers
            )

            delivery.response_status = response.status_code
            delivery.response_body = response.text[:1000]  # Limit stored response

            if response.status_code >= 200 and response.status_code < 300:
                delivery.status = WebhookStatus.DELIVERED
                delivery.delivered_at = datetime.utcnow().isoformat()
            else:
                delivery.status = WebhookStatus.FAILED
                delivery.error_message = f"HTTP {response.status_code}"

                # Schedule retry if needed
                if delivery.attempts < subscription.max_retries:
                    delivery.status = WebhookStatus.RETRYING
                    await asyncio.sleep(
                        subscription.retry_delay_seconds * delivery.attempts
                    )
                    await self._deliver(subscription, delivery)

        except Exception as e:
            delivery.status = WebhookStatus.FAILED
            delivery.error_message = str(e)[:500]

            # Schedule retry if needed
            if delivery.attempts < subscription.max_retries:
                delivery.status = WebhookStatus.RETRYING
                await asyncio.sleep(
                    subscription.retry_delay_seconds * delivery.attempts
                )
                await self._deliver(subscription, delivery)

        finally:
            await self.store.save_delivery(delivery)

    async def process_retries(self) -> int:
        """Process pending webhook retries. Returns number processed."""
        pending = await self.store.get_pending_deliveries()

        for delivery in pending:
            sub = await self.store.get_subscription(delivery.subscription_id)
            if sub and sub.active:
                asyncio.create_task(self._deliver(sub, delivery))

        return len(pending)

    async def verify_incoming(self, payload: str, signature: str, secret: str) -> bool:
        """Verify an incoming webhook signature."""
        return self._verify_signature(payload, signature, secret)

    async def close(self):
        """Close the webhook manager."""
        if self._http_client:
            await self._http_client.aclose()


# Global webhook manager
webhook_manager = WebhookManager()


# Convenience functions
async def register_webhook(
    url: str, events: List[str], secret: Optional[str] = None
) -> WebhookSubscription:
    """Register a webhook subscription."""
    return await webhook_manager.register(url, events, secret)


async def trigger_event(
    event_type: str, payload: Dict[str, Any], tenant_id: Optional[str] = None
) -> List[WebhookDelivery]:
    """Trigger a webhook event."""
    return await webhook_manager.trigger(event_type, payload, tenant_id)


import asyncio

__all__ = [
    "WebhookManager",
    "webhook_manager",
    "WebhookSubscription",
    "WebhookDelivery",
    "WebhookEventType",
    "WebhookStatus",
    "WebhookAuthType",
    "WebhookStore",
    "InMemoryWebhookStore",
    "register_webhook",
    "trigger_event",
]
