"""Heat index ("feels like" temperature) from air temperature and humidity.

Uses the US National Weather Service method: the simple Steadman formula when it gives below
80 °F, otherwise the Rothfusz regression with the standard low- and high-humidity adjustments.
Inputs and output are in °C; the regression itself works in °F.
"""

import math


def heat_index_c(temp_c: float, rh_pct: float) -> float:
    t = temp_c * 9 / 5 + 32
    rh = max(0.0, min(100.0, rh_pct))
    simple = 0.5 * (t + 61.0 + (t - 68.0) * 1.2 + rh * 0.094)
    if (simple + t) / 2 < 80:
        hi = simple
    else:
        hi = (
            -42.379
            + 2.04901523 * t
            + 10.14333127 * rh
            - 0.22475541 * t * rh
            - 0.00683783 * t * t
            - 0.05481717 * rh * rh
            + 0.00122874 * t * t * rh
            + 0.00085282 * t * rh * rh
            - 0.00000199 * t * t * rh * rh
        )
        if rh < 13 and 80 <= t <= 112:
            hi -= ((13 - rh) / 4) * math.sqrt((17 - abs(t - 95)) / 17)
        elif rh > 85 and 80 <= t <= 87:
            hi += ((rh - 85) / 10) * ((87 - t) / 5)
    # Below about 27 °C the heat index is not meaningful; report the air temperature instead.
    if temp_c < 26.7:
        return round(temp_c, 1)
    return round((hi - 32) * 5 / 9, 1)
