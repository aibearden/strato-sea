from __future__ import annotations

from dataclasses import dataclass

from ais.models import AISBoundingBox, Viewport


MIN_LAT = -85.0
MAX_LAT = 85.0

# Zoom-based subscription strategies. MVP uses "viewport" or "defer".
# Future options could include grid sampling or port-centric boxes at low zoom.
STRATEGY_VIEWPORT = "viewport"
STRATEGY_DEFER = "defer"


@dataclass(frozen=True)
class ViewportPlan:
    strategy: str
    boxes: list[AISBoundingBox]
    west: float
    south: float
    east: float
    north: float
    zoom: float
    crosses_antimeridian: bool


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def wrap_longitude(lon: float) -> float:
    wrapped = ((lon + 180.0) % 360.0 + 360.0) % 360.0 - 180.0
    if wrapped == -180.0:
        return 180.0
    return wrapped


def longitude_span(west: float, east: float) -> float:
    if east >= west:
        return min(east - west, 360.0)
    return min((180.0 - west) + (east + 180.0), 360.0)


def point_in_viewport(lat: float, lon: float, viewport: Viewport, buffer_ratio: float = 0.0) -> bool:
    plan = plan_viewport(viewport, buffer_ratio=buffer_ratio)
    if plan.strategy == STRATEGY_DEFER:
        return False
    return any(_point_in_box(lat, lon, box) for box in plan.boxes)


def _point_in_box(lat: float, lon: float, box: AISBoundingBox) -> bool:
    if lat < box.south or lat > box.north:
        return False
    if box.west <= box.east:
        return box.west <= lon <= box.east
    return lon >= box.west or lon <= box.east


def plan_viewport(
    viewport: Viewport,
    *,
    buffer_ratio: float,
    min_zoom: float = 5.0,
    max_span_deg: float = 35.0,
) -> ViewportPlan:
    """Turn a MapLibre viewport into AISStream bounding boxes.

    Handles antimeridian wrapping by splitting into two boxes. Adds a
    geographic buffer so vessels do not disappear at the map edge. Refuses
    worldwide / very-zoomed-out coverage so we never subscribe to the
    entire AIS stream.
    """
    south = clamp(viewport.south, MIN_LAT, MAX_LAT)
    north = clamp(viewport.north, MIN_LAT, MAX_LAT)
    if north < south:
        south, north = north, south

    west = viewport.west
    east = viewport.east
    lat_span = max(north - south, 0.01)
    lon_span = max(longitude_span(west, east), 0.01)

    lat_pad = lat_span * buffer_ratio
    lon_pad = lon_span * buffer_ratio
    south = clamp(south - lat_pad, MIN_LAT, MAX_LAT)
    north = clamp(north + lat_pad, MIN_LAT, MAX_LAT)
    west -= lon_pad
    east += lon_pad

    buffered_span = longitude_span(west, east)
    too_zoomed_out = viewport.zoom < min_zoom
    too_wide = buffered_span >= max_span_deg or (north - south) >= max_span_deg

    if too_zoomed_out or too_wide:
        return ViewportPlan(
            strategy=STRATEGY_DEFER,
            boxes=[],
            west=west,
            south=south,
            east=east,
            north=north,
            zoom=viewport.zoom,
            crosses_antimeridian=east < west or buffered_span >= 360,
        )

    boxes = _boxes_from_bounds(west, south, east, north)
    return ViewportPlan(
        strategy=STRATEGY_VIEWPORT,
        boxes=boxes,
        west=west,
        south=south,
        east=east,
        north=north,
        zoom=viewport.zoom,
        crosses_antimeridian=len(boxes) > 1,
    )


def _boxes_from_bounds(west: float, south: float, east: float, north: float) -> list[AISBoundingBox]:
    span = longitude_span(west, east)
    if span >= 359.9:
        return []

    west_n = wrap_longitude(west)
    east_n = wrap_longitude(east)
    crosses_antimeridian = west + span > 180.0 or west_n > east_n

    if not crosses_antimeridian:
        return [AISBoundingBox(south=south, west=west_n, north=north, east=east_n)]

    boxes: list[AISBoundingBox] = []
    if west_n < 180.0:
        boxes.append(AISBoundingBox(south=south, west=west_n, north=north, east=180.0))
    if east_n > -180.0:
        boxes.append(AISBoundingBox(south=south, west=-180.0, north=north, east=east_n))
    return boxes


def merge_boxes(boxes: list[AISBoundingBox]) -> list[AISBoundingBox]:
    """Merge overlapping / adjacent boxes that do not cross the antimeridian."""
    if len(boxes) <= 1:
        return list(boxes)

    simple = [box for box in boxes if box.west <= box.east]
    wrapping = [box for box in boxes if box.west > box.east]
    simple.sort(key=lambda box: (box.west, box.south))

    merged: list[AISBoundingBox] = []
    for box in simple:
        if not merged:
            merged.append(box)
            continue
        prev = merged[-1]
        if box.west <= prev.east and box.south <= prev.north and box.north >= prev.south:
            merged[-1] = AISBoundingBox(
                south=min(prev.south, box.south),
                west=min(prev.west, box.west),
                north=max(prev.north, box.north),
                east=max(prev.east, box.east),
            )
        else:
            merged.append(box)

    return merged + wrapping
