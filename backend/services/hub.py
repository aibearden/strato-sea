from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from ais.models import (
    RemoveMessage,
    SnapshotMessage,
    StatusMessage,
    UpdateMessage,
    Vessel,
    Viewport,
)
from ais.subscription import SubscriptionManager
from services.vessel_store import VesselStore
from services.viewport import (
    STRATEGY_DEFER,
    ViewportPlan,
    merge_boxes,
    plan_viewport,
    point_in_viewport,
)

logger = logging.getLogger(__name__)


@dataclass
class ClientSession:
    websocket: WebSocket
    viewport: Viewport | None = None
    plan: ViewportPlan | None = None
    queue: asyncio.Queue[dict] = field(default_factory=lambda: asyncio.Queue(maxsize=200))


class ClientHub:
    """Fan-out vessel updates to browsers, filtered by each client's viewport."""

    def __init__(
        self,
        store: VesselStore,
        subscription: SubscriptionManager,
        *,
        buffer_ratio: float,
        min_zoom: float,
        max_span_deg: float,
        broadcast_interval: float,
    ) -> None:
        self._store = store
        self._subscription = subscription
        self._buffer_ratio = buffer_ratio
        self._min_zoom = min_zoom
        self._max_span_deg = max_span_deg
        self._broadcast_interval = broadcast_interval
        self._clients: dict[int, ClientSession] = {}
        self._ais_connected = False
        self._lock = asyncio.Lock()

    @property
    def ais_connected(self) -> bool:
        return self._ais_connected

    def set_ais_connected(self, connected: bool) -> None:
        self._ais_connected = connected
        asyncio.create_task(self.broadcast_status())

    async def connect(self, websocket: WebSocket) -> ClientSession:
        await websocket.accept()
        session = ClientSession(websocket=websocket)
        async with self._lock:
            self._clients[id(websocket)] = session
        logger.info("Client connected (%s total)", len(self._clients))
        await self._send(session, self._status_payload(session))
        return session

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._clients.pop(id(websocket), None)
        await self._refresh_subscription()
        logger.info("Client disconnected (%s total)", len(self._clients))

    async def set_viewport(self, session: ClientSession, viewport: Viewport) -> None:
        session.viewport = viewport
        session.plan = plan_viewport(
            viewport,
            buffer_ratio=self._buffer_ratio,
            min_zoom=self._min_zoom,
            max_span_deg=self._max_span_deg,
        )
        await self._refresh_subscription()
        vessels = await self._vessels_for_session(session)
        await self._send(
            session,
            SnapshotMessage(
                vessels=vessels,
                strategy=session.plan.strategy,
                subscription_active=session.plan.strategy != STRATEGY_DEFER,
            ).model_dump(mode="json"),
        )
        await self._send(session, self._status_payload(session))

    async def enqueue(self, session: ClientSession, payload: dict) -> None:
        try:
            session.queue.put_nowait(payload)
        except asyncio.QueueFull:
            logger.warning("Dropping message for slow client")

    async def sender_loop(self, session: ClientSession) -> None:
        try:
            while True:
                payload = await session.queue.get()
                await session.websocket.send_json(payload)
        except Exception:
            return

    async def flush_loop(self) -> None:
        while True:
            await asyncio.sleep(self._broadcast_interval)
            dirty, removed = await self._store.take_dirty()
            if not dirty and not removed:
                continue
            async with self._lock:
                clients = list(self._clients.values())
            for session in clients:
                if not session.viewport or not session.plan:
                    continue
                relevant = [
                    vessel
                    for vessel in dirty
                    if vessel.lat is not None
                    and vessel.lon is not None
                    and point_in_viewport(vessel.lat, vessel.lon, session.viewport, self._buffer_ratio)
                ]
                if relevant:
                    await self.enqueue(
                        session,
                        UpdateMessage(vessels=relevant).model_dump(mode="json"),
                    )
                if removed:
                    await self.enqueue(
                        session,
                        RemoveMessage(mmsis=removed).model_dump(mode="json"),
                    )

    async def broadcast_status(self) -> None:
        async with self._lock:
            clients = list(self._clients.values())
        for session in clients:
            await self.enqueue(session, self._status_payload(session))

    def _status_payload(self, session: ClientSession) -> dict:
        plan = session.plan
        strategy = plan.strategy if plan else STRATEGY_DEFER
        subscription_active = bool(plan and plan.strategy != STRATEGY_DEFER and self._ais_connected)
        message = None
        if not self._ais_connected:
            message = "Waiting for AISStream"
        if strategy == STRATEGY_DEFER:
            message = "Zoom in to stream live AIS for this area"
        return StatusMessage(
            ais_connected=self._ais_connected,
            subscription_active=subscription_active,
            strategy=strategy,
            vessel_count=0,
            tracked_total=len(self._clients),
            message=message,
        ).model_dump(mode="json")

    async def _vessels_for_session(self, session: ClientSession) -> list[Vessel]:
        if not session.viewport or not session.plan or session.plan.strategy == STRATEGY_DEFER:
            return []
        vessels = await self._store.all_vessels()
        return [
            vessel
            for vessel in vessels
            if vessel.lat is not None
            and vessel.lon is not None
            and point_in_viewport(vessel.lat, vessel.lon, session.viewport, self._buffer_ratio)
        ]

    async def _refresh_subscription(self) -> None:
        async with self._lock:
            plans = [session.plan for session in self._clients.values() if session.plan]
        boxes = []
        for plan in plans:
            boxes.extend(plan.boxes)
        self._subscription.request(merge_boxes(boxes))

    @staticmethod
    async def _send(session: ClientSession, payload: dict) -> None:
        if session.websocket.client_state != WebSocketState.CONNECTED:
            return
        try:
            await session.websocket.send_json(payload)
        except Exception:
            logger.debug("Failed to send to client", exc_info=True)
