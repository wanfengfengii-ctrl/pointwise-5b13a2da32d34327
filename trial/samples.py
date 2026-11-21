from collections.abc import Iterable, Mapping, Set
from dataclasses import dataclass
from fractions import Fraction

from thermal_core import InvalidInput, exact_rational


@dataclass(frozen=True)
class Sample:
    time: Fraction
    reading: Fraction

    def __post_init__(self):
        object.__setattr__(self, 'time', exact_rational(self.time, 'sample time'))
        object.__setattr__(self, 'reading', exact_rational(self.reading, 'sample reading'))


def validate_samples(samples: Iterable) -> tuple[Sample, ...]:
    if not isinstance(samples, Iterable) or isinstance(samples, (str, bytes, Mapping, Set)):
        raise InvalidInput('samples must be an ordered iterable of time and reading pairs')
    ordered = []
    for value in samples:
        if isinstance(value, Sample):
            sample = value
        elif isinstance(value, (list, tuple)) and len(value) == 2:
            sample = Sample(value[0], value[1])
        else:
            raise InvalidInput('each sample needs a time and a reading')
        if ordered and sample.time <= ordered[-1].time:
            raise InvalidInput('sample times must be strictly increasing')
        ordered.append(sample)
    if len(ordered) < 2:
        raise InvalidInput('at least two samples are required')
    return tuple(ordered)
