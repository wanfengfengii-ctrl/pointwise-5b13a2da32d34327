from dataclasses import dataclass
from uuid import uuid4

from thermal_core import InvalidInput, MissingRecord, identifier
from trial.calibration import load_calibration
from trial.repository import TrialRepository
from trial.samples import Sample, validate_samples


@dataclass(frozen=True)
class TrialRevision:
    revision_id: str
    trial_id: str
    calibration_id: str
    parent_revision_id: str | None
    samples: tuple[Sample, ...]


def record_trial(
    repository: TrialRepository,
    trial_id: str,
    calibration_id: str,
    samples,
    parent_revision_id: str | None = None,
) -> str:
    identifier(trial_id, 'trial identifier')
    ordered = validate_samples(samples)
    calibration = load_calibration(repository, calibration_id)
    if parent_revision_id is not None:
        parent = load_trial_revision(repository, parent_revision_id)
        if parent.trial_id != trial_id:
            raise InvalidInput('amendment parent must belong to the same trial')
    revision_id = f'rev-{uuid4().hex}'
    repository.store_revision(
        revision_id, trial_id, calibration.revision_id, parent_revision_id, ordered
    )
    return revision_id


def load_trial_revision(repository: TrialRepository, revision_id: str) -> TrialRevision:
    identifier(revision_id, 'trial revision')
    stored = repository.get_revision(revision_id)
    if stored is None:
        raise MissingRecord(f'unknown trial revision {revision_id}')
    trial_id, calibration_id, parent_revision_id, points = stored
    samples = tuple(Sample(time, reading) for time, reading in points)
    return TrialRevision(revision_id, trial_id, calibration_id, parent_revision_id, samples)
