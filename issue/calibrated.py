from issue.curve import CalibratedCurve, CurveKnot
from trial.calibration import load_calibration
from trial.repository import TrialRepository
from trial.revisions import TrialRevision


def calibrate_revision(repository: TrialRepository, revision: TrialRevision) -> CalibratedCurve:
    calibration = load_calibration(repository, revision.calibration_id)
    samples = revision.samples
    origin = samples[0].time
    knots = tuple(
        CurveKnot(sample.time - origin, calibration.apply(sample.reading))
        for sample in samples
    )
    return CalibratedCurve(knots)
