from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class Viewport(BaseModel):
    west: float
    south: float
    east: float
    north: float
    zoom: float = 2.0


class AISBoundingBox(BaseModel):
    """Two-corner box in AISStream format: [[lat, lon], [lat, lon]]."""

    south: float
    west: float
    north: float
    east: float

    def to_ais(self) -> list[list[float]]:
        return [[self.south, self.west], [self.north, self.east]]


class Vessel(BaseModel):
    mmsi: int
    name: str | None = None
    imo: int | None = None
    call_sign: str | None = None
    vessel_type: int | None = None
    vessel_type_label: str | None = None
    lat: float | None = None
    lon: float | None = None
    speed: float | None = None
    course: float | None = None
    heading: float | None = None
    destination: str | None = None
    eta: str | None = None
    nav_status: int | None = None
    last_update: datetime


class ClientViewportMessage(BaseModel):
    type: Literal["viewport"]
    west: float
    south: float
    east: float
    north: float
    zoom: float = 2.0


class ClientPingMessage(BaseModel):
    type: Literal["ping"]


class SnapshotMessage(BaseModel):
    type: Literal["snapshot"] = "snapshot"
    vessels: list[Vessel]
    strategy: str
    subscription_active: bool


class UpdateMessage(BaseModel):
    type: Literal["update"] = "update"
    vessels: list[Vessel]


class RemoveMessage(BaseModel):
    type: Literal["remove"] = "remove"
    mmsis: list[int]


class StatusMessage(BaseModel):
    type: Literal["status"] = "status"
    ais_connected: bool
    subscription_active: bool
    strategy: str
    vessel_count: int
    tracked_total: int
    message: str | None = None


class ErrorMessage(BaseModel):
    type: Literal["error"] = "error"
    message: str


class PongMessage(BaseModel):
    type: Literal["pong"] = "pong"


class SearchResult(BaseModel):
    vessels: list[Vessel]
    query: str


class HealthResponse(BaseModel):
    status: str
    ais_configured: bool
    ais_connected: bool
    tracked_vessels: int


class AISEnvelope(BaseModel):
    MessageType: str | None = None
    MetaData: dict[str, Any] = Field(default_factory=dict)
    Message: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
