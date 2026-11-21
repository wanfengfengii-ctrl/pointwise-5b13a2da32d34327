from fractions import Fraction
import json

from intake.validation import validate_curve_body
from issue.package import issue_curve
from tests.support import A_PROFILE, B_PROFILE, LedgerCase
from thermal_core import InvalidInput, MissingRecord
from trial.calibration import register_calibration
from trial.revisions import load_trial_revision, record_trial


class TrialCurveTests(LedgerCase):
    def test_calibrated_curve_with_hold(self):
        calibration = register_calibration(self.trials, 'reference-1', '3/2', '1/3')
        revision = record_trial(self.trials, 'test-17', calibration, [(5, 2), (7, 4), (11, 4)])
        later_calibration = register_calibration(self.trials, 'reference-1', 7, -8)
        self.assertNotEqual(calibration, later_calibration)
        stored = load_trial_revision(self.trials, revision)
        self.assertEqual(stored.calibration_id, calibration)
        self.assertEqual([(p.time, p.reading) for p in stored.samples], [(5, 2), (7, 4), (11, 4)])
        package = issue_curve(self.trials, self.issues, revision)
        self.assertEqual((package.trial_id, package.revision_id), ('test-17', revision))
        self.assertEqual(json.loads(package.body), {
            'knots': [[[0, 1], [10, 3]], [[2, 1], [19, 3]], [[6, 1], [19, 3]]],
        })
        self.assertEqual(self.source.execute(
            'SELECT revision_id, exchange_bytes FROM issued_curves WHERE issue_id = ?',
            (package.issue_id,),
        ).fetchone(), (revision, package.to_bytes()))
        self.source.close()
        curve = validate_curve_body(package.body)
        self.assertEqual(curve.duration, 6)
        self.assertEqual(curve.value_at(1), Fraction(29, 6))
        self.assertEqual(curve.value_at(5), Fraction(19, 3))
        hold = curve.segments()[1]
        self.assertEqual(hold.end.time - hold.start.time, 4)

    def test_elapsed_profile(self):
        left, right = self.issue_pair(A_PROFILE, B_PROFILE)
        calibration = register_calibration(self.trials, 'probe-cool', 1, 0)
        cooling_revision = record_trial(self.trials, 'trial-cool', calibration, [
            ('-5/2', 20), ('-3/2', 22), ('1/2', 22), ('7/2', 19),
        ])
        cooling = issue_curve(self.trials, self.issues, cooling_revision)
        self.source.close()
        left_curve = validate_curve_body(left.body)
        right_curve = validate_curve_body(right.body)
        self.assertEqual(left_curve.value_at(1), 21)
        self.assertEqual(right_curve.value_at(1), Fraction(61, 3))
        self.assertEqual([segment.end.time - segment.start.time for segment in left_curve.segments()], [1, 3])
        self.assertEqual([segment.end.time - segment.start.time for segment in right_curve.segments()], [3, 1])
        curve = validate_curve_body(cooling.body)
        self.assertEqual([knot.time for knot in curve.knots], [0, 1, 3, 6])
        self.assertEqual([curve.value_at(time) for time in (0, '1/2', 2, 4, 6)], [20, 21, 22, 21, 19])
        with self.assertRaises(InvalidInput):
            curve.value_at('13/2')

    def test_duplicate_time(self):
        calibration = register_calibration(self.trials, 'reference-2', 1, 0)
        valid = record_trial(self.trials, 'valid', calibration, [(0, 20), (1, 21)])
        issue_curve(self.trials, self.issues, valid)
        with self.assertRaisesRegex(InvalidInput, 'strictly increasing'):
            record_trial(self.trials, 'invalid-duplicate', calibration, [(0, 20), (1, 21), (1, 22)])
        self.assertIsNone(self.source.execute(
            'SELECT revision_id FROM trial_revisions WHERE trial_id = ?', ('invalid-duplicate',)
        ).fetchone())
        with self.assertRaisesRegex(MissingRecord, 'unknown trial revision'):
            issue_curve(self.trials, self.issues, 'revision-for-rejected-submission')
        counts = self.source.execute('''
            SELECT (SELECT COUNT(*) FROM trial_revisions),
                   (SELECT COUNT(*) FROM samples),
                   (SELECT COUNT(*) FROM issued_curves)
        ''').fetchone()
        self.assertEqual(counts, (1, 2, 1))

    def test_reject_invalid_input_and_parent(self):
        for probe, scale, offset in [('', 1, 0), ('probe', '1/0', 0), ('probe', True, 0), ('probe', 1, None)]:
            with self.subTest(probe=probe, scale=scale, offset=offset):
                with self.assertRaises(InvalidInput):
                    register_calibration(self.trials, probe, scale, offset)
        self.assertEqual(self.source.execute('SELECT COUNT(*) FROM calibrations').fetchone()[0], 0)
        calibration = register_calibration(self.trials, 'probe', 0, 0)
        for points in [[(0, 1)], [(0, 1), (-1, 2)], [(0, 1), (1, None)], [(0, 1), (1,)], [(0, 1), (1, 2.0)]]:
            with self.subTest(points=points), self.assertRaises(InvalidInput):
                record_trial(self.trials, 'accepted-trial', calibration, points)
        with self.assertRaises(MissingRecord):
            record_trial(self.trials, 'accepted-trial', 'missing-cal', A_PROFILE)
        parent_id = record_trial(self.trials, 'accepted-trial', calibration, A_PROFILE)
        with self.assertRaisesRegex(InvalidInput, 'same trial'):
            record_trial(self.trials, 'different-trial', calibration, A_PROFILE, parent_id)
        with self.assertRaises(MissingRecord):
            record_trial(self.trials, 'accepted-trial', calibration, A_PROFILE, 'missing-parent')
        self.assertEqual(self.source.execute('SELECT COUNT(*) FROM trial_revisions').fetchone()[0], 1)
        parent = issue_curve(self.trials, self.issues, parent_id)
        self.assertEqual(validate_curve_body(parent.body).value_at('1/2'), 0)
