from fractions import Fraction

from compare.rate_limits import STANDARD_RATE_LIMITS
from compare.temperature_band import clip_boundary_for_temperature, temperature_band_for_cell
from issue.curve import CalibratedCurve
from thermal_core import InvalidInput, exact_rational


Interval = tuple[Fraction, Fraction]


def _merge(intervals) -> tuple[Interval, ...]:
    """Sort closed intervals and coalesce overlapping or touching ones."""
    merged: list[Interval] = []
    for low, high in sorted(intervals):
        if low > high:
            continue
        if merged and low <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], high))
        else:
            merged.append((low, high))
    return tuple(merged)


def _clip(intervals, bound: Interval | None) -> tuple[Interval, ...]:
    if bound is None or not intervals:
        return ()
    low, high = bound
    clipped = []
    for start, end in intervals:
        start, end = max(start, low), min(end, high)
        if start <= end:
            clipped.append((start, end))
    return _merge(clipped)


def _contains(intervals, value: Fraction) -> bool:
    return any(low <= value <= high for low, high in intervals)


def _shifted(intervals, lower: Fraction, upper: Fraction):
    """Images of intervals under adding a value drawn from [lower, upper]."""
    return [(low + lower, high + upper) for low, high in intervals]


def has_full_alignment(left: CalibratedCurve, right: CalibratedCurve, tolerance) -> bool:
    tolerance = exact_rational(tolerance, 'temperature tolerance')
    if tolerance < 0:
        raise InvalidInput('temperature tolerance must be nonnegative')
    if not STANDARD_RATE_LIMITS.allows_elapsed(left.duration, right.duration):
        return False

    left_segments, right_segments = left.segments(), right.segments()
    xs = [knot.time for knot in left.knots]
    ys = [knot.time for knot in right.knots]

    # A monotone aligned path moves only right and up, so it visits grid cells in a
    # staircase order.  For each cell keep the reachable elapsed coordinates on its
    # right edge (right_edges, indexed by y) and top edge (top_edges, indexed by x).
    right_edges = [[() for _ in right_segments] for _ in left_segments]
    top_edges = [[() for _ in right_segments] for _ in left_segments]

    start_ok = abs(left.knots[0].temperature - right.knots[0].temperature) <= tolerance
    for i, left_segment in enumerate(left_segments):
        x0, x1 = xs[i], xs[i + 1]
        width = x1 - x0
        for j, right_segment in enumerate(right_segments):
            y0, y1 = ys[j], ys[j + 1]
            height = y1 - y0
            band = temperature_band_for_cell(left_segment, right_segment, tolerance)
            left_clip = clip_boundary_for_temperature(band, 'x', x0, (y0, y1))
            bottom_clip = clip_boundary_for_temperature(band, 'y', y0, (x0, x1))
            right_clip = clip_boundary_for_temperature(band, 'x', x1, (y0, y1))
            top_clip = clip_boundary_for_temperature(band, 'y', y1, (x0, x1))
            if (right_clip is None and top_clip is None):
                continue
            if left_clip is None and bottom_clip is None:
                continue

            if i == 0 and j == 0:
                left_reachable = [(Fraction(0), Fraction(0))] if start_ok else ()
                bottom_reachable = [(Fraction(0), Fraction(0))] if start_ok else ()
            else:
                left_reachable = right_edges[i - 1][j] if i > 0 else ()
                bottom_reachable = top_edges[i][j - 1] if j > 0 else ()
                # A staircase may touch the shared corner of the diagonal neighbour.
                if i > 0 and j > 0:
                    if _contains(right_edges[i - 1][j - 1], y0):
                        left_reachable = _merge(left_reachable + ((y0, y0),))
                    if _contains(top_edges[i - 1][j - 1], x0):
                        bottom_reachable = _merge(bottom_reachable + ((x0, x0),))

            # The entry point itself must already respect this cell's temperature band.
            left_reachable = _clip(left_reachable, left_clip)
            bottom_reachable = _clip(bottom_reachable, bottom_clip)
            if not left_reachable and not bottom_reachable:
                continue

            # Slope bounds are dy/dx and dx/dy both in [1/2, 2].
            right_candidates = _shifted(left_reachable, width / 2, 2 * width)
            right_candidates += [
                (y0 + (x1 - high) / 2, y0 + 2 * (x1 - low))
                for low, high in bottom_reachable
            ]
            right_edges[i][j] = _clip(_merge(right_candidates), right_clip)

            top_candidates = _shifted(bottom_reachable, height / 2, 2 * height)
            top_candidates += [
                (x0 + (y1 - high) / 2, x0 + 2 * (y1 - low))
                for low, high in left_reachable
            ]
            top_edges[i][j] = _clip(_merge(top_candidates), top_clip)

    last_i, last_j = len(left_segments) - 1, len(right_segments) - 1
    return _contains(top_edges[last_i][last_j], left.duration) or _contains(
        right_edges[last_i][last_j], right.duration
    )
