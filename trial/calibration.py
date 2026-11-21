from dataclasses import dataclass
from fractions import Fraction
from uuid import uuid4

from thermal_core import MissingRecord, exact_rational, identifier
from trial.repository import TrialRepository


@dataclass(frozen=True)
class CalibrationRevision:
    revision_id: str
    probe_id: str
    scale: Fraction
    offset: Fraction

    def __post_init__(self):
        identifier(self.revision_id, 'calibration revision')
        identifier(self.probe_id, 'probe identifier')
        object.__setattr__(self, 'scale', exact_rational(self.scale, 'calibration scale'))
        object.__setattr__(self, 'offset', exact_rational(self.offset, 'calibration offset'))

    def apply(self, reading) -> Fraction:
        return self.scale * exact_rational(reading, 'probe reading') + self.offset


def register_calibration(repository: TrialRepository, probe_id: str, scale, offset) -> str:
    calibration = CalibrationRevision(f'cal-{uuid4().hex}', probe_id, scale, offset)
    repository.store_calibration(
        calibration.revision_id, calibration.probe_id, calibration.scale, calibration.offset
    )
    return calibration.revision_id


def load_calibration(repository: TrialRepository, revision_id: str) -> CalibrationRevision:
    identifier(revision_id, 'calibration revision')
    row = repository.get_calibration(revision_id)
    if row is None:
        raise MissingRecord(f'unknown calibration revision {revision_id}')
    return CalibrationRevision(revision_id, *row)
