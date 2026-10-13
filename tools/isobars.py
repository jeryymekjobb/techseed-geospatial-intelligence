"""Isobars, and the centres of highs and lows, from a grid of sea-level pressure.

MET Norway's archived MEPS runs (tools/fetch_met_forecasts.py) hold the air pressure at sea
level; a weather map draws it as isobars every INTERVAL_HPA hPa. The field is smoothed a little,
as weather maps are, the lines are traced with marching squares and joined into polylines, and
the highs and lows are the grid's local extremes over a wide window. Only numpy is needed.
"""

from __future__ import annotations

from typing import Any

INTERVAL_HPA = 2
SMOOTHING_PASSES = 1
# A high or a low is the extreme within this many grid cells each way, and at least this much
# above or below the mean around it (hPa).
CENTRE_WINDOW = 12  # about 240 km at the chart's 20 km
CENTRE_DEPTH_HPA = 1.0
ROUND = 4  # decimals of the coordinates


def smooth(field: Any, passes: int = SMOOTHING_PASSES) -> Any:
    """A 3 x 3 mean, `passes` times; the edges repeat."""
    import numpy as np

    result = np.asarray(field, dtype=float)
    for _ in range(passes):
        padded = np.pad(result, 1, mode="edge")
        result = sum(padded[i:i + result.shape[0], j:j + result.shape[1]] for i in range(3) for j in range(3)) / 9.0
    return result


def segments(field: Any, level: float) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """Marching squares: the level's pieces in each grid cell, in (row, column) coordinates."""
    rows, cols = field.shape
    found = []
    for y in range(rows - 1):
        for x in range(cols - 1):
            corners = ((y, x), (y, x + 1), (y + 1, x + 1), (y + 1, x))
            values = [field[corner] for corner in corners]
            crossings = []
            for edge in range(4):
                a, b = values[edge], values[(edge + 1) % 4]
                if (a < level) != (b < level):
                    t = (level - a) / (b - a)
                    (y0, x0), (y1, x1) = corners[edge], corners[(edge + 1) % 4]
                    crossings.append((y0 + t * (y1 - y0), x0 + t * (x1 - x0)))
            if len(crossings) == 2:
                found.append((crossings[0], crossings[1]))
            elif len(crossings) == 4:  # a saddle: two pieces
                found += [(crossings[0], crossings[1]), (crossings[2], crossings[3])]
    return found


def join(pieces: list[tuple[tuple[float, float], tuple[float, float]]]) -> list[list[tuple[float, float]]]:
    """The pieces joined end to end into polylines (closed ones end where they start)."""
    key = lambda point: (round(point[0], 6), round(point[1], 6))  # noqa: E731
    ends: dict[tuple[float, float], list[int]] = {}
    for index, (a, b) in enumerate(pieces):
        ends.setdefault(key(a), []).append(index)
        ends.setdefault(key(b), []).append(index)
    used = [False] * len(pieces)
    lines = []
    for start in range(len(pieces)):
        if used[start]:
            continue
        used[start] = True
        line = list(pieces[start])
        for forward in (True, False):
            while True:
                tip = line[-1] if forward else line[0]
                following = next((index for index in ends.get(key(tip), []) if not used[index]), None)
                if following is None:
                    break
                used[following] = True
                a, b = pieces[following]
                nxt = b if key(a) == key(tip) else a
                if forward:
                    line.append(nxt)
                else:
                    line.insert(0, nxt)
        lines.append(line)
    return lines


def to_latlon(point: tuple[float, float], latitudes: Any, longitudes: Any) -> list[float]:
    """A (row, column) position on the grid as [latitude, longitude], interpolated bilinearly."""
    y, x = point
    rows, cols = latitudes.shape
    y0, x0 = min(int(y), rows - 2), min(int(x), cols - 2)
    fy, fx = y - y0, x - x0
    corner = lambda a: (a[y0, x0] * (1 - fy) * (1 - fx) + a[y0 + 1, x0] * fy * (1 - fx)  # noqa: E731
                        + a[y0, x0 + 1] * (1 - fy) * fx + a[y0 + 1, x0 + 1] * fy * fx)
    return [round(float(corner(latitudes)), ROUND), round(float(corner(longitudes)), ROUND)]


def centres(field: Any, window: int = CENTRE_WINDOW, depth: float = CENTRE_DEPTH_HPA) -> list[tuple[str, int, int, float]]:
    """The highs ("H") and lows ("L"): (kind, row, column, hPa), away from the grid's edges."""
    import numpy as np

    rows, cols = field.shape
    found = []
    for y in range(window, rows - window):
        for x in range(window, cols - window):
            around = field[y - window:y + window + 1, x - window:x + window + 1]
            value = field[y, x]
            if value == around.max() and value - float(np.mean(around)) >= depth:
                found.append(("H", y, x, float(value)))
            elif value == around.min() and float(np.mean(around)) - value >= depth:
                found.append(("L", y, x, float(value)))
    return found


def isobars(pressure_hpa: Any, latitudes: Any, longitudes: Any, interval: int = INTERVAL_HPA) -> dict[str, Any]:
    """The isobars as { hpa, coords: [[lat, lon], ...] } and the highs and lows as { kind, hpa, latitude, longitude }."""
    import numpy as np

    field = smooth(pressure_hpa)
    low, high = float(np.nanmin(field)), float(np.nanmax(field))
    lines = []
    for level in range(int(low // interval + 1) * interval, int(high) + 1, interval):
        for line in join(segments(field, level)):
            if len(line) >= 3:
                lines.append({"hpa": level, "coords": [to_latlon(point, latitudes, longitudes) for point in line]})
    marks = [{"kind": kind, "hpa": round(value), "latitude": round(float(latitudes[y, x]), ROUND), "longitude": round(float(longitudes[y, x]), ROUND)}
             for kind, y, x, value in centres(field)]
    return {"lines": lines, "centres": marks}
