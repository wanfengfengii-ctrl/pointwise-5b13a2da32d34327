from dataclasses import dataclass
from fractions import Fraction

from compare.verdict import evaluate_verdict
from intake.catalog import IntakeCatalog
from intake.receipts import get_accepted_curve, validate_received_id
from report.publication import publish_report
from report.repository import ReportRepository
from report.snapshot import ReportSnapshot, SuccessReceipt
from thermal_core import InvalidInput, exact_rational


@dataclass(frozen=True)
class ComparisonRequest:
    left_received_id: int
    right_received_id: int
    tolerance: Fraction


def validate_request(left_received_id, right_received_id, tolerance) -> ComparisonRequest:
    left_id = validate_received_id(left_received_id)
    right_id = validate_received_id(right_received_id)
    limit = exact_rational(tolerance, 'temperature tolerance')
    if limit < 0:
        raise InvalidInput('temperature tolerance must be nonnegative')
    return ComparisonRequest(left_id, right_id, limit)


def compare_and_publish(
    catalog: IntakeCatalog,
    reports: ReportRepository,
    left_received_id: int,
    right_received_id: int,
    tolerance,
) -> tuple[ReportSnapshot, SuccessReceipt]:
    request = validate_request(left_received_id, right_received_id, tolerance)
    left = get_accepted_curve(catalog, request.left_received_id)
    right = get_accepted_curve(catalog, request.right_received_id)
    verdict = evaluate_verdict(left.curve, right.curve, request.tolerance)
    return publish_report(reports, left, right, request.tolerance, verdict.value)
