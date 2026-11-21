from fractions import Fraction

from intake.receipts import accept_curve
from report.readback import read_report
from tests.support import A_PROFILE, B_PROFILE, LedgerCase, legal_wire


class AlignmentTests(LedgerCase):
    def test_identical_offline(self):
        first, second = self.issue_pair(A_PROFILE, A_PROFILE)
        first_id, second_id = self.receive_pair((first, second))
        self.assertLess(first_id, second_id)
        self.source.close()
        report, receipt = self.publish(second_id, first_id, 0)
        self.assertEqual(report.verdict, 'equivalent')
        self.assertEqual(report.received_ids, (second_id, first_id))
        self.assertEqual(receipt.received_ids, (second_id, first_id))
        self.assertEqual(receipt.tolerance, 0)
        for origin, package in zip(report.sources, (second, first)):
            self.assertEqual(
                (origin.issue_id, origin.trial_id, origin.revision_id, origin.digest),
                (package.issue_id, package.trial_id, package.revision_id, package.digest),
            )
        self.assertEqual(receipt.sources, report.sources)
        self.assertEqual(receipt.report_id, report.report_id)
        self.assertEqual(read_report(self.reports, report.report_id), (report, receipt))

    def test_local_rate_and_touch(self):
        left_id, right_id = self.receive_pair(self.issue_pair())
        self.source.close()
        for tolerance, expected in ((0, 'retest'), ('1/4', 'retest'), ('1/3', 'equivalent')):
            with self.subTest(tolerance=tolerance):
                report, receipt = self.publish(left_id, right_id, tolerance)
                self.assertEqual(report.verdict, expected)
                self.assertEqual(report.tolerance, Fraction(tolerance))
                self.assertEqual(receipt.tolerance, Fraction(tolerance))
                self.assertEqual(read_report(self.reports, report.report_id), (report, receipt))
        self.assertEqual(self.report_counts(), (3, 3))

    def test_legal_fixture(self):
        self.source.close()
        first = accept_curve(self.catalog, legal_wire('external-A', 'A', 'rev-A', A_PROFILE))
        second = accept_curve(self.catalog, legal_wire('external-B', 'B', 'rev-B', B_PROFILE))
        self.assertEqual(self.publish(first, second, 0)[0].verdict, 'retest')
        self.assertEqual(self.publish(first, second, '1/4')[0].verdict, 'retest')

    def test_closed_touch(self):
        self.source.close()
        first = accept_curve(self.catalog, legal_wire('external-A', 'A', 'rev-A', A_PROFILE))
        second = accept_curve(self.catalog, legal_wire('external-B', 'B', 'rev-B', B_PROFILE))
        # At x=1 the rate bound is y<=2 and the temperature bound is y>=2.
        # Straight pieces (0,0)->(1,2)->(4,4) meet both bounds throughout.
        for left_id, right_id in ((first, second), (second, first)):
            with self.subTest(left_id=left_id):
                self.assertEqual(self.publish(left_id, right_id, '1/3')[0].verdict, 'equivalent')
                self.assertEqual(self.publish(left_id, right_id, Fraction(1, 3) - Fraction(1, 300))[0].verdict, 'retest')

    def test_resampled_reversal_and_shared_corners(self):
        left = ((0, 20), (1, 22), (2, 20), (3, 20), (4, 21))
        right = ((0, 20), (1, 21), (2, 22), (3, 20), (4, 20), ('9/2', '41/2'), (5, 21))
        left_id, right_id = self.receive_pair(self.issue_pair(left, right))
        self.source.close()
        # Corresponding extrema and hold endpoints give rates 2, 1, 1, 1.
        self.assertEqual(self.publish(left_id, right_id, 0)[0].verdict, 'equivalent')
        self.assertEqual(self.publish(right_id, left_id, 0)[0].verdict, 'equivalent')

    def test_duration_bounds_are_closed(self):
        self.source.close()
        first = accept_curve(self.catalog, legal_wire('flat-A', 'A', 'rev-A', ((0, 20), (2, 20))))
        at_limit = accept_curve(self.catalog, legal_wire('flat-B', 'B', 'rev-B', ((0, 20), (4, 20))))
        too_long = accept_curve(self.catalog, legal_wire('flat-C', 'C', 'rev-C', ((0, 20), ('41/10', 20))))
        self.assertEqual(self.publish(first, at_limit, 0)[0].verdict, 'equivalent')
        self.assertEqual(self.publish(at_limit, first, 0)[0].verdict, 'equivalent')
        self.assertEqual(self.publish(first, too_long, 10)[0].verdict, 'retest')

    def test_meeting_endpoints_alone_does_not_admit_interior_peak(self):
        left = ((0, 20), (2, 23), (4, 20))
        right = ((0, 20), (4, 20))
        left_id, right_id = self.receive_pair(self.issue_pair(left, right))
        self.source.close()
        self.assertEqual(self.publish(left_id, right_id, '299/100')[0].verdict, 'retest')
        self.assertEqual(self.publish(left_id, right_id, 3)[0].verdict, 'equivalent')
