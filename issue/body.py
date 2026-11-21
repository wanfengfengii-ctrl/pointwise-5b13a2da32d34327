from fractions import Fraction
import json

from issue.curve import CalibratedCurve
from thermal_core import exact_rational


def encode_rational(value: Fraction) -> list[int]:
    rational = exact_rational(value, 'exchange value')
    return [rational.numerator, rational.denominator]


def encode_curve_body(curve: CalibratedCurve) -> bytes:
    knots = [
        [encode_rational(knot.time), encode_rational(knot.temperature)]
        for knot in curve.knots
    ]
    return json.dumps({'knots': knots}, separators=(',', ':'), ensure_ascii=True).encode('ascii')
