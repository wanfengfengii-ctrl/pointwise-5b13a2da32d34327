from contextlib import closing
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

from compare.request import compare_and_publish
from intake.catalog import IntakeCatalog
from intake.receipts import accept_curve, get_accepted_curve
from issue.package import issue_curve
from issue.registry import IssueRegistry
from report.repository import ReportRepository
from tests.support import A_PROFILE, B_PROFILE, legal_wire
from trial.calibration import register_calibration
from trial.repository import TrialRepository
from trial.revisions import record_trial


TOLERANCES = ('0', '1/4', '1/3')
EXPECTED = {
    'elapsed_1s_c': ['21', '61/3'],
    'issued_verdicts': ['retest', 'retest', 'equivalent'],
    'external_verdicts': ['retest', 'retest', 'equivalent'],
}


def _verdicts(catalog, reports, left_id, right_id):
    return [
        compare_and_publish(catalog, reports, left_id, right_id, tolerance)[0].verdict
        for tolerance in TOLERANCES
    ]


def run_incident(source_path, analysis_path):
    with closing(sqlite3.connect(source_path)) as source:
        trials, issues = TrialRepository(source), IssueRegistry(source)
        trials.initialize()
        issues.initialize()
        calibration = register_calibration(trials, 'probe', 1, 0)
        wires = []
        for trial_id, samples in (('trial-A', A_PROFILE), ('trial-B', B_PROFILE)):
            revision = record_trial(trials, trial_id, calibration, samples)
            wires.append(issue_curve(trials, issues, revision).to_bytes())

    external_wires = (
        legal_wire('reference-A', 'trial-A', 'reference-revision-A', A_PROFILE),
        legal_wire('reference-B', 'trial-B', 'reference-revision-B', B_PROFILE),
    )
    with closing(sqlite3.connect(analysis_path)) as analysis:
        catalog, reports = IntakeCatalog(analysis), ReportRepository(analysis)
        catalog.initialize()
        reports.initialize()
        issued_ids = [accept_curve(catalog, wire) for wire in wires]
        external_ids = [accept_curve(catalog, wire) for wire in external_wires]
        return {
            'elapsed_1s_c': [
                str(get_accepted_curve(catalog, received_id).curve.value_at(1))
                for received_id in issued_ids
            ],
            'issued_verdicts': _verdicts(catalog, reports, *issued_ids),
            'external_verdicts': _verdicts(catalog, reports, *external_ids),
        }


def main():
    with TemporaryDirectory(prefix='thermal-incident-') as directory:
        root = Path(directory)
        actual = run_incident(root / 'source.sqlite3', root / 'analysis.sqlite3')
    print(json.dumps({'tolerances': TOLERANCES, 'actual': actual, 'expected': EXPECTED}, sort_keys=True))
    if actual != EXPECTED:
        print('THERMAL_ALIGNMENT_MISMATCH')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
