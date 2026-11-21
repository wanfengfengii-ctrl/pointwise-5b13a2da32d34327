from enum import Enum

from compare.alignment import has_full_alignment
from issue.curve import CalibratedCurve


class Verdict(str, Enum):
    EQUIVALENT = 'equivalent'
    RETEST = 'retest'


def evaluate_verdict(left: CalibratedCurve, right: CalibratedCurve, tolerance) -> Verdict:
    if has_full_alignment(left, right, tolerance):
        return Verdict.EQUIVALENT
    return Verdict.RETEST
