from fractions import Fraction
import json

from intake.receipts import accept_curve, get_accepted_curve
from issue.package import issue_curve
from report.publication import PublicationError
from report.readback import read_report
from tests.support import B_CORRECTION, LedgerCase
from thermal_core import InvalidInput, MissingRecord
from trial.revisions import load_trial_revision, record_trial


class ReportTests(LedgerCase):
    def test_revision_and_reopen(self):
        left, right = self.issue_pair()
        left_id, right_id = self.receive_pair((left, right))
        self.source.close()
        old = self.publish(left_id, right_id, 0)
        old_report, old_receipt = old
        self.assertEqual(old_report.verdict, 'retest')
        old_export = read_report(self.reports, old_report.report_id, 'export')

        self.open_source()
        original = load_trial_revision(self.trials, right.revision_id)
        amended_id = record_trial(
            self.trials, original.trial_id, original.calibration_id, B_CORRECTION, original.revision_id
        )
        amended_revision = load_trial_revision(self.trials, amended_id)
        self.assertEqual(amended_revision.parent_revision_id, original.revision_id)
        self.assertEqual(load_trial_revision(self.trials, original.revision_id), original)
        self.assertEqual(issue_curve(self.trials, self.issues, original.revision_id).body, right.body)
        amended = issue_curve(self.trials, self.issues, amended_id)
        self.source.close()
        amended_receipt_id = accept_curve(self.catalog, amended.to_bytes())
        current = self.publish(left_id, amended_receipt_id, 0)
        current_report, current_receipt = current
        self.assertEqual(current_report.verdict, 'equivalent')
        self.assertEqual(current_report.received_ids, (left_id, amended_receipt_id))
        self.assertEqual(old_report.received_ids, (left_id, right_id))
        self.assertEqual(old_report.sources[1].revision_id, original.revision_id)
        self.assertEqual(current_report.sources[1].revision_id, amended_id)
        self.assertNotEqual(old_receipt.receipt_id, current_receipt.receipt_id)
        current_export = read_report(self.reports, current_report.report_id, 'export')

        self.analysis.close()
        self.open_analysis()
        self.catalog.initialize()
        self.reports.initialize()
        self.assertEqual(get_accepted_curve(self.catalog, right_id).package, right)
        self.assertEqual(get_accepted_curve(self.catalog, amended_receipt_id).package, amended)
        self.assertEqual(self.report_counts(), (2, 2))
        for stored, exported in ((old, old_export), (current, current_export)):
            report, receipt = stored
            with self.subTest(verdict=report.verdict):
                self.assertEqual(read_report(self.reports, report.report_id), stored)
                self.assertEqual(read_report(self.reports, report.report_id, 'export'), exported)
                self.assert_export_matches(exported, report, receipt)
        with self.assertRaisesRegex(MissingRecord, 'unknown report'):
            read_report(self.reports, 'missing-report')

    def assert_export_matches(self, exported, report, receipt):
        payload = json.loads(exported)
        left_id, right_id = report.received_ids
        request = {
            'left_received_id': left_id,
            'right_received_id': right_id,
            'tolerance': [report.tolerance.numerator, report.tolerance.denominator],
        }
        sources = [
            {
                'received_id': source.received_id,
                'issue_id': source.issue_id,
                'trial_id': source.trial_id,
                'revision_id': source.revision_id,
                'digest': source.digest,
            }
            for source in report.sources
        ]
        self.assertEqual(payload, {
            'report': {'report_id': report.report_id, 'request': request, 'sources': sources, 'verdict': report.verdict},
            'receipt': {
                'report_id': report.report_id, 'request': request, 'sources': sources, 'receipt_id': receipt.receipt_id,
            },
        })

    def test_repeat_initialize_preserves_source_amendments(self):
        left, right = self.issue_pair()
        original = load_trial_revision(self.trials, right.revision_id)
        amended_id = record_trial(
            self.trials, right.trial_id, original.calibration_id, B_CORRECTION, right.revision_id
        )
        amended = load_trial_revision(self.trials, amended_id)
        self.source.close()
        self.open_source()
        self.trials.initialize()
        self.issues.initialize()
        self.assertEqual(load_trial_revision(self.trials, amended_id), amended)
        self.assertEqual(load_trial_revision(self.trials, right.revision_id), original)
        self.assertEqual(self.source.execute('SELECT COUNT(*) FROM issued_curves').fetchone()[0], 2)
        self.assertEqual(issue_curve(self.trials, self.issues, left.revision_id).body, left.body)
        self.assertEqual(issue_curve(self.trials, self.issues, amended_id).body, b'{"knots":[[[0,1],[20,1]],[[2,1],[21,1]],[[4,1],[21,1]]]}')

    def test_export_roundtrips_fraction_and_order(self):
        first, second = self.receive_pair(self.issue_pair())
        self.source.close()
        report, receipt = self.publish(second, first, '7/19')
        self.assertEqual(report.tolerance, Fraction(7, 19))
        self.assertEqual(receipt.received_ids, (second, first))
        self.assert_export_matches(read_report(self.reports, report.report_id, 'export'), report, receipt)

    def test_reject_bad_request(self):
        first, second = self.receive_pair(self.issue_pair())
        self.source.close()
        good = self.publish(first, second, '1/3')
        with self.assertRaisesRegex(InvalidInput, 'nonnegative'):
            self.publish(first, second, '-1/8')
        with self.assertRaisesRegex(MissingRecord, 'unknown received curve'):
            self.publish(first, 500, 0)
        for invalid in (None, True, '1/0', 0.25):
            with self.subTest(invalid=invalid), self.assertRaises(InvalidInput):
                self.publish(first, second, invalid)
        with self.assertRaises(InvalidInput):
            self.publish(True, second, 0)
        self.assertEqual(self.report_counts(), (1, 1))
        self.assertEqual(read_report(self.reports, good[0].report_id), good)

    def test_atomic_publication(self):
        first, second = self.receive_pair(self.issue_pair())
        self.source.close()
        good = self.publish(first, second, 0)
        self.analysis.execute('''
            CREATE TRIGGER reject_test_receipt BEFORE INSERT ON success_receipts
            WHEN EXISTS (SELECT 1 FROM reports WHERE report_id = NEW.report_id)
            BEGIN
                SELECT RAISE(ABORT, 'test write failure after report insert');
            END
        ''')
        with self.assertRaises(PublicationError) as failed:
            self.publish(first, second, '1/3')
        self.assertIn('test write failure after report insert', str(failed.exception.__cause__))
        self.assert_failure_left_no_records(failed.exception, good)
        self.analysis.close()
        self.open_analysis()
        self.assert_failure_left_no_records(failed.exception, good)
        self.analysis.execute('DROP TRIGGER reject_test_receipt')
        report, receipt = self.publish(first, second, '1/3')
        self.assertEqual(report.verdict, 'equivalent')
        self.assertEqual(read_report(self.reports, report.report_id), (report, receipt))
        self.assertEqual(self.report_counts(), (2, 2))

    def assert_failure_left_no_records(self, failure, good):
        self.assertEqual(self.report_counts(), (1, 1))
        self.assertIsNone(self.analysis.execute(
            'SELECT report_id FROM reports WHERE report_id = ?', (failure.report_id,)
        ).fetchone())
        self.assertIsNone(self.analysis.execute(
            'SELECT receipt_id FROM success_receipts WHERE receipt_id = ? OR report_id = ?',
            (failure.receipt_id, failure.report_id),
        ).fetchone())
        with self.assertRaises(MissingRecord):
            read_report(self.reports, failure.report_id)
        self.assertEqual(read_report(self.reports, good[0].report_id), good)
