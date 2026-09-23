from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from ais.models import Vessel
from ais.processor import AISProcessor

logger = logging.getLogger(__name__)


class VesselStore:
    """In-memory collection of recently seen vessels."""

    def __init__(self, *, ttl_seconds: int, sweep_interval: float) -> None:
        self._ttl = timedelta(seconds=ttl_seconds)
        self._sweep_interval = sweep_interval
        self._vessels: dict[int, Vessel] = {}
        self._dirty: set[int] = set()
        self._removed: set[int] = set()
        self._lock = asyncio.Lock()
        self._processor = AISProcessor()

    async def ingest(self, envelope: dict) -> Vessel | None:
        message_type = envelope.get("MessageType")
        if not message_type or message_type == "SubscriptionConfirmation" or envelope.get("error"):
            return None

        async with self._lock:
            metadata = envelope.get("MetaData") if isinstance(envelope.get("MetaData"), dict) else {}
            message = envelope.get("Message") if isinstance(envelope.get("Message"), dict) else {}
            body = message.get(message_type)
            if not isinstance(body, dict):
                body = {}

            mmsi_hint = None
            for source in (metadata.get("MMSI"), body.get("UserID")):
                try:
                    mmsi_hint = int(source)
                    break
                except (TypeError, ValueError):
                    continue

            existing = self._vessels.get(mmsi_hint) if mmsi_hint else None
            vessel = self._processor.apply(envelope, existing)
            if vessel is None:
                return None
            self._vessels[vessel.mmsi] = vessel
            self._dirty.add(vessel.mmsi)
            self._removed.discard(vessel.mmsi)
            return vessel

    async def get(self, mmsi: int) -> Vessel | None:
        async with self._lock:
            return self._vessels.get(mmsi)

    async def all_vessels(self) -> list[Vessel]:
        async with self._lock:
            return list(self._vessels.values())

    async def search(self, query: str, limit: int = 20) -> list[Vessel]:
        needle = query.strip().lower()
        if not needle:
            return []
        async with self._lock:
            matches: list[Vessel] = []
            for vessel in self._vessels.values():
                haystacks = [
                    str(vessel.mmsi),
                    (vessel.name or "").lower(),
                    str(vessel.imo or ""),
                    (vessel.call_sign or "").lower(),
                ]
                if any(needle in item for item in haystacks if item):
                    matches.append(vessel)
                if len(matches) >= limit:
                    break
            return matches

    async def take_dirty(self) -> tuple[list[Vessel], list[int]]:
        async with self._lock:
            vessels = [self._vessels[mmsi] for mmsi in self._dirty if mmsi in self._vessels]
            removed = list(self._removed)
            self._dirty.clear()
            self._removed.clear()
            return vessels, removed

    async def count(self) -> int:
        async with self._lock:
            return len(self._vessels)

    async def sweep_once(self) -> list[int]:
        cutoff = datetime.now(UTC) - self._ttl
        removed: list[int] = []
        async with self._lock:
            stale = [mmsi for mmsi, vessel in self._vessels.items() if vessel.last_update < cutoff]
            for mmsi in stale:
                self._vessels.pop(mmsi, None)
                self._dirty.discard(mmsi)
                self._removed.add(mmsi)
                removed.append(mmsi)
        if removed:
            logger.info("Removed %s stale vessels", len(removed))
        return removed

    async def sweep_loop(self) -> None:
        while True:
            await asyncio.sleep(self._sweep_interval)
            await self.sweep_once()
