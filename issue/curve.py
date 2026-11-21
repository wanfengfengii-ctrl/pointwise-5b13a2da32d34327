from bisect import bisect_right
from dataclasses import dataclass
from fractions import Fraction
from operator import attrgetter

from thermal_core import InvalidInput, exact_rational


@dataclass(frozen=True)
class CurveKnot:
    time: Fraction
    temperature: Fraction

    def __post_init__(self):
        object.__setattr__(self, 'time', exact_rational(self.time, 'elapsed time'))
        object.__setattr__(self, 'temperature', exact_rational(self.temperature, 'temperature'))


@dataclass(frozen=True)
class LinearSegment:
    start: CurveKnot
    end: CurveKnot

    def __post_init__(self):
        if self.end.time <= self.start.time:
            raise InvalidInput('a segment must have positive duration')

    @property
    def slope(self) -> Fraction:
        return (self.end.temperature - self.start.temperature) / (self.end.time - self.start.time)

    @property
    def intercept(self) -> Fraction:
        return self.start.temperature - self.slope * self.start.time

    def value_at(self, time) -> Fraction:
        elapsed = exact_rational(time, 'elapsed time')
        if not self.start.time <= elapsed <= self.end.time:
            raise InvalidInput('elapsed time falls outside the segment')
        return self.start.temperature + self.slope * (elapsed - self.start.time)


@dataclass(frozen=True)
class CalibratedCurve:
    knots: tuple[CurveKnot, ...]

    def __post_init__(self):
        knots = tuple(self.knots)
        if len(knots) < 2 or any(not isinstance(knot, CurveKnot) for knot in knots):
            raise InvalidInput('a curve needs at least two valid knots')
        if knots[0].time != 0:
            raise InvalidInput('a curve must start at zero elapsed seconds')
        if any(right.time <= left.time for left, right in zip(knots, knots[1:])):
            raise InvalidInput('knot times must be strictly increasing')
        object.__setattr__(self, 'knots', knots)

    @property
    def duration(self) -> Fraction:
        return self.knots[-1].time

    def segments(self) -> tuple[LinearSegment, ...]:
        return tuple(LinearSegment(left, right) for left, right in zip(self.knots, self.knots[1:]))

    def value_at(self, time) -> Fraction:
        elapsed = exact_rational(time, 'elapsed time')
        if not 0 <= elapsed <= self.duration:
            raise InvalidInput('elapsed time falls outside the curve')
        if elapsed == self.duration:
            return self.knots[-1].temperature
        index = bisect_right(self.knots, elapsed, key=attrgetter('time'))
        return LinearSegment(self.knots[index - 1], self.knots[index]).value_at(elapsed)
