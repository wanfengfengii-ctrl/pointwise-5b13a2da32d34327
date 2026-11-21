from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

from issue.curve import LinearSegment
from thermal_core import InvalidInput


Axis = Literal['x', 'y']
Interval = tuple[Fraction, Fraction]


@dataclass(frozen=True)
class TemperatureBand:
    x_coefficient: Fraction
    y_coefficient: Fraction
    constant: Fraction
    tolerance: Fraction


def temperature_band_for_cell(
    left: LinearSegment, right: LinearSegment, tolerance: Fraction
) -> TemperatureBand:
    return TemperatureBand(left.slope, -right.slope, left.intercept - right.intercept, tolerance)


def clip_boundary_for_temperature(
    band: TemperatureBand, fixed_axis: Axis, fixed: Fraction, interval: Interval
) -> Interval | None:
    """Intersect a closed segment boundary with the cell's temperature band."""
    if fixed_axis == 'x':
        slope = band.y_coefficient
        intercept = band.constant + band.x_coefficient * fixed
    elif fixed_axis == 'y':
        slope = band.x_coefficient
        intercept = band.constant + band.y_coefficient * fixed
    else:
        raise InvalidInput('fixed boundary axis must be x or y')

    lower, upper = interval
    if slope == 0:
        if lower <= upper and abs(intercept) <= band.tolerance:
            return interval
        return None
    first = (-band.tolerance - intercept) / slope
    second = (band.tolerance - intercept) / slope
    lower = max(lower, min(first, second))
    upper = min(upper, max(first, second))
    return (lower, upper) if lower <= upper else None
