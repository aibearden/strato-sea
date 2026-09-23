from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable

from ais.models import AISBoundingBox

logger = logging.getLogger(__name__)

AISBoxes = list[list[list[float]]]
BoxesListener = Callable[[AISBoxes | None], Awaitable[None]]


class SubscriptionManager:
    """Translate client viewports into a single AISStream subscription.

    AISStream replaces (does not merge) subscriptions, and allows at most
    one update per second. This manager coalesces requested boxes and
    applies the latest set at that rate.
    """

    def __init__(
        self,
        *,
        min_interval_seconds: float,
        on_boxes: BoxesListener,
    ) -> None:
        self._min_interval = min_interval_seconds
        self._on_boxes = on_boxes
        self._desired: list[AISBoundingBox] | None = None
        self._applied: AISBoxes | None = None
        self._changed = asyncio.Event()
        self._stop = asyncio.Event()

    def request(self, boxes: list[AISBoundingBox]) -> None:
        self._desired = boxes
        self._changed.set()

    def current_ais_boxes(self) -> AISBoxes | None:
        return self._applied

    async def stop(self) -> None:
        self._stop.set()
        self._changed.set()

    async def run(self) -> None:
        last_sent = 0.0
        while not self._stop.is_set():
            await self._changed.wait()
            if self._stop.is_set():
                return
            self._changed.clear()

            elapsed = time.monotonic() - last_sent
            if elapsed < self._min_interval:
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=self._min_interval - elapsed)
                    return
                except TimeoutError:
                    pass

            payload = self._to_ais_payload(self._desired or [])
            if payload == self._applied:
                continue
            try:
                await self._on_boxes(payload)
                self._applied = payload
                last_sent = time.monotonic()
            except Exception:
                logger.exception("Failed to apply AISStream subscription")

    @staticmethod
    def _to_ais_payload(boxes: list[AISBoundingBox]) -> AISBoxes | None:
        if not boxes:
            return None
        return [box.to_ais() for box in boxes]
