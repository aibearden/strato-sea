from __future__ import annotations

import asyncio
import json
import logging
import random
from collections.abc import Awaitable, Callable
from typing import Any

import websockets
from websockets.exceptions import ConnectionClosedError

from ais.subscription import AISBoxes

logger = logging.getLogger(__name__)

OnMessage = Callable[[dict[str, Any]], Awaitable[None]]
OnState = Callable[[bool], Awaitable[None] | None]


class AISStreamClient:
    """Persistent AISStream.io WebSocket client with reconnect and bbox updates.

    The API key stays on the server. Subscriptions are replaced (not merged)
    and must be sent within 3 seconds of connecting.
    """

    def __init__(
        self,
        *,
        url: str,
        api_key: str,
        on_message: OnMessage,
        on_state: OnState | None = None,
    ) -> None:
        self._url = url
        self._api_key = api_key
        self._on_message = on_message
        self._on_state = on_state
        self._stop = asyncio.Event()
        self._ws: Any = None
        self._boxes: AISBoxes | None = None
        self._boxes_event = asyncio.Event()
        self._connected = False
        self._last_error: str | None = None

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def last_error(self) -> str | None:
        return self._last_error

    @property
    def configured(self) -> bool:
        return bool(self._api_key.strip())

    def set_state_handler(self, on_state: OnState) -> None:
        self._on_state = on_state

    async def set_bounding_boxes(self, boxes: AISBoxes | None) -> None:
        self._boxes = boxes
        self._boxes_event.set()
        ws = self._ws
        if ws is None:
            return
        if boxes:
            await self._send_subscription(ws, boxes)
        else:
            await ws.close()

    async def stop(self) -> None:
        self._stop.set()
        self._boxes_event.set()
        ws = self._ws
        if ws is not None:
            await ws.close()

    async def run(self) -> None:
        if not self.configured:
            self._last_error = "AISSTREAM_API_KEY is not set"
            logger.warning(self._last_error)
            await self._set_connected(False)
            await self._stop.wait()
            return

        backoff = 1.0
        while not self._stop.is_set():
            if not self._boxes:
                await self._set_connected(False)
                self._boxes_event.clear()
                await self._wait_for_boxes()
                if self._stop.is_set():
                    return
                continue
            try:
                await self._session()
                backoff = 1.0
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._last_error = str(exc)
                logger.warning("AISStream session ended: %s", exc)
            await self._set_connected(False)
            if self._stop.is_set() or not self._boxes:
                continue
            delay = backoff + random.uniform(0, 0.4 * backoff)
            logger.info("Reconnecting to AISStream in %.1fs", delay)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=delay)
                return
            except TimeoutError:
                backoff = min(backoff * 2, 60.0)

    async def _wait_for_boxes(self) -> None:
        while not self._stop.is_set() and not self._boxes:
            await self._boxes_event.wait()
            self._boxes_event.clear()

    async def _session(self) -> None:
        boxes = self._boxes
        if not boxes:
            return
        logger.info("Connecting to AISStream")
        async with websockets.connect(
            self._url,
            ping_interval=20,
            ping_timeout=20,
            close_timeout=5,
            max_size=8 * 1024 * 1024,
            compression="deflate",
            open_timeout=15,
        ) as ws:
            self._ws = ws
            await self._send_subscription(ws, boxes)
            await self._set_connected(True)
            self._last_error = None
            try:
                async for raw in ws:
                    if self._stop.is_set():
                        return
                    if not self._boxes:
                        return
                    payload = self._decode(raw)
                    if payload is None:
                        continue
                    if payload.get("error"):
                        self._last_error = str(payload["error"])
                        logger.error("AISStream error: %s", self._last_error)
                        continue
                    if payload.get("MessageType") == "SubscriptionConfirmation":
                        logger.info("AISStream subscription confirmed")
                        continue
                    await self._on_message(payload)
            finally:
                self._ws = None

    async def _send_subscription(self, ws: Any, boxes: AISBoxes) -> None:
        message = {
            "APIKey": self._api_key,
            "BoundingBoxes": boxes,
            "FilterMessageTypes": [
                "PositionReport",
                "StandardClassBPositionReport",
                "ExtendedClassBPositionReport",
                "ShipStaticData",
                "StaticDataReport",
            ],
        }
        await ws.send(json.dumps(message))
        logger.info("AISStream subscription applied (%s box(es))", len(boxes))

    @staticmethod
    def _decode(raw: str | bytes) -> dict[str, Any] | None:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            logger.debug("Ignoring non-JSON AISStream frame")
            return None
        if not isinstance(payload, dict):
            return None
        return payload

    async def _set_connected(self, connected: bool) -> None:
        if self._connected == connected:
            return
        self._connected = connected
        if self._on_state:
            result = self._on_state(connected)
            if asyncio.iscoroutine(result):
                await result
            logger.info("AISStream %s", "connected" if connected else "disconnected")


_ = ConnectionClosedError
