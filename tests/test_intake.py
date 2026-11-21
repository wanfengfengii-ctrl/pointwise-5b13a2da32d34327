from dataclasses import replace
from fractions import Fraction
import json

from intake.catalog import IntakeConflict
from intake.decoder import InvalidPackage, decode_envelope
from intake.identity import verify_package_identity
from intake.receipts import accept_curve, get_accepted_curve
from tests.support import A_PROFILE, B_PROFILE, LedgerCase, bound_wire, legal_wire


class IntakeTests(LedgerCase):
    def test_body_substitution(self):
        first, unseen = self.issue_pair()
        received = accept_curve(self.catalog, first.to_bytes())
        replaced = replace(unseen, body=first.body)
        with self.assertRaisesRegex(InvalidPackage, 'identity'):
            accept_curve(self.catalog, replaced.to_bytes())
        self.assertEqual(self.intake_count(), 1)
        accepted_original = accept_curve(self.catalog, unseen.to_bytes())
        self.assertNotEqual(received, accepted_original)
        self.source.close()
        self.assertEqual(get_accepted_curve(self.catalog, received).package, first)
        self.assertEqual(get_accepted_curve(self.catalog, accepted_original).curve.value_at(1), Fraction(61, 3))

    def test_same_number_conflict(self):
        original = legal_wire('shared-number', 'station-A', 'rev-first', A_PROFILE)
        original_id = accept_curve(self.catalog, original)
        for conflict in (
            legal_wire('shared-number', 'station-A', 'rev-first', B_PROFILE),
            legal_wire('shared-number', 'station-A', 'rev-second', A_PROFILE),
        ):
            with self.subTest(conflict=conflict):
                verify_package_identity(decode_envelope(conflict))
                with self.assertRaises(IntakeConflict):
                    accept_curve(self.catalog, conflict)
        self.assertEqual(self.intake_count(), 1)
        self.source.close()
        loaded = get_accepted_curve(self.catalog, original_id)
        self.assertEqual(loaded.package, decode_envelope(original))
        self.assertEqual(loaded.curve.value_at(1), 21)

    def test_exact_repeat(self):
        original = legal_wire('test-repeat', 'station-A', 'rev-first', A_PROFILE)
        received = accept_curve(self.catalog, original)
        self.analysis.close()
        self.open_analysis()
        self.assertEqual(accept_curve(self.catalog, original), received)
        self.assertEqual(self.intake_count(), 1)
        self.assertEqual(get_accepted_curve(self.catalog, received).package.body, decode_envelope(original).body)

    def test_reject_invalid_domain_even_with_valid_binding(self):
        invalid_bodies = [
            {'knots': [[[1, 1], [20, 1]], [[2, 1], [21, 1]]]},
            {'knots': [[[0, 1], [20, 1]], [[0, 1], [21, 1]]]},
            {'knots': [[[0, 1], [20, 1]], [[1, 0], [21, 1]]]},
            {'knots': [[[0, 1], [20, 1]], [[1, 1], [True, 1]]]},
            {'knots': [[[0, 1], [20, 1]], [[1, 1], None]]},
            {'knots': [[[0, 1], [20, 1]]]},
        ]
        for body in invalid_bodies:
            with self.subTest(body=body):
                wire = bound_wire('candidate', 'station-A', 'rev-first', json.dumps(body))
                verify_package_identity(decode_envelope(wire))
                with self.assertRaises(InvalidPackage):
                    accept_curve(self.catalog, wire)
        self.assertEqual(self.intake_count(), 0)

    def test_reject_changed_provenance_and_bad_outer_fields(self):
        wire = legal_wire('issue-A', 'station-A', 'rev-first', A_PROFILE)
        fields = json.loads(wire)
        for change in ({'issue_id': 'issue-B'}, {'revision_id': 'rev-other'}, {'version': True}, {'extra': 0}):
            with self.subTest(change=change), self.assertRaises(InvalidPackage):
                accept_curve(self.catalog, json.dumps(dict(fields, **change)).encode('utf-8'))
        duplicate = wire.rstrip()[:-1] + b', "version": 1}'
        with self.assertRaisesRegex(InvalidPackage, 'duplicate'):
            accept_curve(self.catalog, duplicate)
        self.assertEqual(self.intake_count(), 0)
