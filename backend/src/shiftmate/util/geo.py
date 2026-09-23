"""Small geometry helpers for site layouts (local metres)."""

import math

from shiftmate.schema.config import Layout, Zone
from shiftmate.schema.enums import ZoneType

ROAD_HALF_WIDTH_M = 15.0  # haul roads are drawn as lines; count 15 m either side as "on the road"


def point_in_polygon(x: float, y: float, polygon: list[tuple[float, float]]) -> bool:
    """Ray casting: count how many polygon edges a ray to the right crosses."""
    inside = False
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            x_cross = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < x_cross:
                inside = not inside
    return inside


def distance_to_polyline(x: float, y: float, line: list[tuple[float, float]]) -> float:
    best = math.inf
    for (x1, y1), (x2, y2) in zip(line, line[1:], strict=False):
        dx, dy = x2 - x1, y2 - y1
        length2 = dx * dx + dy * dy
        t = 0.0 if length2 == 0 else max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / length2))
        best = min(best, math.hypot(x - (x1 + t * dx), y - (y1 + t * dy)))
    return best


def zone_at(layout: Layout, x: float, y: float) -> Zone | None:
    """The zone containing the point (areas first, then the nearest haul road within 15 m)."""
    for zone in layout.zones:
        if zone.polygon and point_in_polygon(x, y, zone.polygon):
            return zone
    roads = [
        (distance_to_polyline(x, y, z.polyline or []), z)
        for z in layout.zones
        if z.type == ZoneType.HAUL_ROAD and z.polyline
    ]
    roads = [r for r in roads if r[0] <= ROAD_HALF_WIDTH_M]
    return min(roads, key=lambda r: r[0])[1] if roads else None
