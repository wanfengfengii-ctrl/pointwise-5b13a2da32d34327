from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from compare.request import compare_and_publish
from intake.catalog import IntakeCatalog
from intake.receipts import accept_curve
from issue.package import issue_curve
from issue.registry import IssueRegistry
from report.repository import ReportRepository
from trial.calibration import register_calibration
from trial.repository import TrialRepository
from trial.revisions import record_trial


A_PROFILE = ((0, 20), (1, 21), (4, 21))
B_PROFILE = ((0, 20), (3, 21), (4, 21))
B_CORRECTION = ((0, 20), (2, 21), (4, 21))


def legal_wire(issue_id, trial_id, revision_id, points):
    """Build a stand-alone fixture from the documented V1 wire rules."""
    def fraction_pair(value):
        value = Fraction(value)
        return [value.numerator, value.denominator]

    knots = [[fraction_pair(time), fraction_pair(temperature)] for time, temperature in points]
    return bound_wire(issue_id, trial_id, revision_id, json.dumps({'knots': knots}, indent=1))


def bound_wire(issue_id, trial_id, revision_id, body):
    fields = {
        'version': 1,
        'issue_id': issue_id,
        'trial_id': trial_id,
        'revision_id': revision_id,
        'body': body,
    }
    canonical = json.dumps(fields, sort_keys=True, ensure_ascii=True, separators=(',', ':'))
    return json.dumps(dict(fields, digest=sha256(canonical.encode('ascii')).hexdigest())).encode('utf-8')


class LedgerCase(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory(prefix='thermal-test-')
        self.addCleanup(directory.cleanup)
        path = Path(directory.name)
        self.source_path = path / 'source.sqlite3'
        self.analysis_path = path / 'analysis.sqlite3'
        self.open_source()
        self.open_analysis()

    def open_source(self):
        self.source = sqlite3.connect(self.source_path)
        self.addCleanup(self.source.close)
        self.trials = TrialRepository(self.source)
        self.issues = IssueRegistry(self.source)
        self.trials.initialize()
        self.issues.initialize()

    def open_analysis(self):
        self.analysis = sqlite3.connect(self.analysis_path, isolation_level=None)
        self.addCleanup(self.analysis.close)
        self.catalog = IntakeCatalog(self.analysis)
        self.reports = ReportRepository(self.analysis)
        self.catalog.initialize()
        self.reports.initialize()

    def issue_pair(self, left=A_PROFILE, right=B_PROFILE):
        calibration = register_calibration(self.trials, 'probe-one', 1, 0)
        left_revision = record_trial(self.trials, 'trial-A', calibration, left)
        right_revision = record_trial(self.trials, 'trial-B', calibration, right)
        return (
            issue_curve(self.trials, self.issues, left_revision),
            issue_curve(self.trials, self.issues, right_revision),
        )

    def receive_pair(self, packages):
        return tuple(accept_curve(self.catalog, package.to_bytes()) for package in packages)

    def publish(self, left_id, right_id, tolerance):
        return compare_and_publish(self.catalog, self.reports, left_id, right_id, tolerance)

    def report_counts(self):
        return self.analysis.execute('''
            SELECT (SELECT COUNT(*) FROM reports), (SELECT COUNT(*) FROM success_receipts)
        ''').fetchone()

    def intake_count(self):
        return self.analysis.execute('SELECT COUNT(*) FROM accepted_curves').fetchone()[0]
