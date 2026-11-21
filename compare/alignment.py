from fractions import Fraction

from compare.rate_limits import STANDARD_RATE_LIMITS
from issue.curve import CalibratedCurve, CurveKnot
from thermal_core import InvalidInput, exact_rational


def _phase_profile(curve: CalibratedCurve) -> CalibratedCurve:
    last_index = len(curve.knots) - 1
    knots = tuple(
        CurveKnot(Fraction(index, last_index), knot.temperature)
        for index, knot in enumerate(curve.knots)
    )
    return CalibratedCurve(knots)


def has_full_alignment(left: CalibratedCurve, right: CalibratedCurve, tolerance) -> bool:
    tolerance = exact_rational(tolerance, 'temperature tolerance')
    if tolerance < 0:
        raise InvalidInput('temperature tolerance must be nonnegative')
    if not STANDARD_RATE_LIMITS.allows_elapsed(left.duration, right.duration):
        return False

    left_profile, right_profile = _phase_profile(left), _phase_profile(right)
    checkpoints = {knot.time for profile in (left_profile, right_profile) for knot in profile.knots}
    return all(
        abs(left_profile.value_at(phase) - right_profile.value_at(phase)) <= tolerance
        for phase in checkpoints
    )
