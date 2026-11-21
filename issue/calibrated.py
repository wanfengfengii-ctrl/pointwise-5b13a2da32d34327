from issue.curve import CalibratedCurve, CurveKnot
from trial.calibration import load_calibration
from trial.repository import TrialRepository
from trial.revisions import TrialRevision


def calibrate_revision(repository: TrialRepository, revision: TrialRevision) -> CalibratedCurve:
    calibration = load_calibration(repository, revision.calibration_id)
    samples = revision.samples
    duration = samples[-1].time - samples[0].time
    step = duration / (len(samples) - 1)
    knots = tuple(
        CurveKnot(index * step, calibration.apply(sample.reading))
        for index, sample in enumerate(samples)
    )
    return CalibratedCurve(knots)
