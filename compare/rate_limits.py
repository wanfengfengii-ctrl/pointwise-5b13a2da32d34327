from dataclasses import dataclass
from fractions import Fraction

from thermal_core import InvalidInput, exact_rational


@dataclass(frozen=True)
class RateLimits:
    lower: Fraction
    upper: Fraction

    def __post_init__(self):
        lower = exact_rational(self.lower, 'lower clock ratio')
        upper = exact_rational(self.upper, 'upper clock ratio')
        if not 0 < lower <= upper:
            raise InvalidInput('clock rate bounds must be positive and ordered')
        object.__setattr__(self, 'lower', lower)
        object.__setattr__(self, 'upper', upper)

    def elapsed_window(self, left_elapsed) -> tuple[Fraction, Fraction]:
        elapsed = exact_rational(left_elapsed, 'left elapsed time')
        if elapsed < 0:
            raise InvalidInput('elapsed time must be nonnegative')
        return self.lower * elapsed, self.upper * elapsed

    def allows_elapsed(self, left_elapsed, right_elapsed) -> bool:
        left_elapsed = exact_rational(left_elapsed, 'left elapsed time')
        right_elapsed = exact_rational(right_elapsed, 'right elapsed time')
        if left_elapsed < 0:
            return False
        low, high = self.elapsed_window(left_elapsed)
        return low <= right_elapsed <= high


STANDARD_RATE_LIMITS = RateLimits(Fraction(1, 2), Fraction(2))
