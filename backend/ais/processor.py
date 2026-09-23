from __future__ import annotations

import logging
from datetime import UTC, datetime

from ais.models import Vessel

logger = logging.getLogger(__name__)

# AIS sentinels
HEADING_UNAVAILABLE = 511
COURSE_UNAVAILABLE = 360.0
SPEED_UNAVAILABLE = 102.3


def _clean_ais_text(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).replace("@", " ").strip()
    return text or None


def _valid_imo(value: object | None) -> int | None:
    try:
        imo = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return imo if imo > 0 else None


def _valid_heading(value: object | None) -> float | None:
    try:
        heading = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if heading < 0 or heading >= HEADING_UNAVAILABLE:
        return None
    return heading


def _valid_course(value: object | None) -> float | None:
    try:
        course = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if course < 0 or course >= COURSE_UNAVAILABLE:
        return None
    return course


def _valid_speed(value: object | None) -> float | None:
    try:
        speed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if speed < 0 or speed >= SPEED_UNAVAILABLE:
        return None
    return speed


def _format_eta(eta: object | None) -> str | None:
    if not isinstance(eta, dict):
        return None
    month = int(eta.get("Month") or 0)
    day = int(eta.get("Day") or 0)
    hour = int(eta.get("Hour") or 24)
    minute = int(eta.get("Minute") or 60)
    if month == 0 or day == 0:
        return None
    hour_s = f"{hour:02d}" if hour < 24 else "--"
    minute_s = f"{minute:02d}" if minute < 60 else "--"
    return f"{month:02d}-{day:02d} {hour_s}:{minute_s} UTC"


def ship_type_label(code: int | None) -> str | None:
    if code is None or code <= 0:
        return None
    groups = {
        20: "Wing in ground",
        30: "Fishing",
        31: "Towing",
        32: "Towing (large)",
        33: "Dredging/underwater",
        34: "Diving",
        35: "Military",
        36: "Sailing",
        37: "Pleasure craft",
        40: "High-speed craft",
        50: "Pilot",
        51: "Search and rescue",
        52: "Tug",
        53: "Port tender",
        54: "Anti-pollution",
        55: "Law enforcement",
        58: "Medical",
        59: "Special craft",
        60: "Passenger",
        70: "Cargo",
        80: "Tanker",
        90: "Other",
    }
    if code in groups:
        return groups[code]
    tens = (code // 10) * 10
    return groups.get(tens, f"Type {code}")


def _meta_coord(metadata: dict, *keys: str) -> float | None:
    for key in keys:
        value = metadata.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


class AISProcessor:
    """Normalize AISStream envelopes into Vessel records."""

    POSITION_TYPES = {
        "PositionReport",
        "StandardClassBPositionReport",
        "ExtendedClassBPositionReport",
        "LongRangeAisBroadcastMessage",
    }
    STATIC_TYPES = {"ShipStaticData", "StaticDataReport"}

    def apply(self, envelope: dict, existing: Vessel | None) -> Vessel | None:
        message_type = envelope.get("MessageType")
        if not message_type or message_type == "SubscriptionConfirmation":
            return None
        if envelope.get("error"):
            logger.warning("AISStream error: %s", envelope["error"])
            return None

        metadata = envelope.get("MetaData") if isinstance(envelope.get("MetaData"), dict) else {}
        raw_message = envelope.get("Message") if isinstance(envelope.get("Message"), dict) else {}
        body = raw_message.get(message_type)
        if not isinstance(body, dict):
            body = {}
        mmsi = self._mmsi(metadata, body)
        if mmsi is None:
            return None

        vessel = existing.model_copy() if existing else Vessel(mmsi=mmsi, last_update=datetime.now(UTC))
        vessel.mmsi = mmsi
        vessel.last_update = datetime.now(UTC)

        name = _clean_ais_text(metadata.get("ShipName")) or _clean_ais_text(body.get("Name"))
        if name:
            vessel.name = name

        lat = _meta_coord(metadata, "Latitude", "latitude")
        lon = _meta_coord(metadata, "Longitude", "longitude")
        if lat is None:
            lat = body.get("Latitude")
        if lon is None:
            lon = body.get("Longitude")
        if lat is not None and lon is not None:
            try:
                lat_f, lon_f = float(lat), float(lon)
                if abs(lat_f) <= 90 and abs(lon_f) <= 180:
                    vessel.lat = lat_f
                    vessel.lon = lon_f
            except (TypeError, ValueError):
                pass

        if message_type in self.POSITION_TYPES:
            self._apply_position(vessel, body)
        elif message_type in self.STATIC_TYPES:
            self._apply_static(vessel, body, message_type)

        return vessel

    @staticmethod
    def _mmsi(metadata: dict, body: dict) -> int | None:
        for source in (metadata.get("MMSI"), body.get("UserID")):
            try:
                mmsi = int(source)
            except (TypeError, ValueError):
                continue
            if mmsi > 0:
                return mmsi
        return None

    @staticmethod
    def _apply_position(vessel: Vessel, body: dict) -> None:
        heading = _valid_heading(body.get("TrueHeading"))
        if heading is not None:
            vessel.heading = heading
        course = _valid_course(body.get("Cog"))
        if course is not None:
            vessel.course = course
        speed = _valid_speed(body.get("Sog"))
        if speed is not None:
            vessel.speed = speed
        nav = body.get("NavigationalStatus")
        if nav is not None:
            try:
                vessel.nav_status = int(nav)
            except (TypeError, ValueError):
                pass
        name = _clean_ais_text(body.get("Name"))
        if name:
            vessel.name = name
        ship_type = body.get("Type")
        if ship_type is not None:
            try:
                vessel.vessel_type = int(ship_type)
                vessel.vessel_type_label = ship_type_label(vessel.vessel_type)
            except (TypeError, ValueError):
                pass

    @staticmethod
    def _apply_static(vessel: Vessel, body: dict, message_type: str) -> None:
        if message_type == "StaticDataReport":
            report_a = body.get("ReportA") or {}
            report_b = body.get("ReportB") or {}
            name = _clean_ais_text(report_a.get("Name"))
            if name:
                vessel.name = name
            call_sign = _clean_ais_text(report_b.get("CallSign"))
            if call_sign:
                vessel.call_sign = call_sign
            ship_type = report_b.get("ShipType")
            if ship_type is not None:
                try:
                    vessel.vessel_type = int(ship_type)
                    vessel.vessel_type_label = ship_type_label(vessel.vessel_type)
                except (TypeError, ValueError):
                    pass
            return

        name = _clean_ais_text(body.get("Name"))
        if name:
            vessel.name = name
        call_sign = _clean_ais_text(body.get("CallSign"))
        if call_sign:
            vessel.call_sign = call_sign
        destination = _clean_ais_text(body.get("Destination"))
        if destination:
            vessel.destination = destination
        eta = _format_eta(body.get("Eta"))
        if eta:
            vessel.eta = eta
        imo = _valid_imo(body.get("ImoNumber"))
        if imo:
            vessel.imo = imo
        ship_type = body.get("Type")
        if ship_type is not None:
            try:
                vessel.vessel_type = int(ship_type)
                vessel.vessel_type_label = ship_type_label(vessel.vessel_type)
            except (TypeError, ValueError):
                pass
