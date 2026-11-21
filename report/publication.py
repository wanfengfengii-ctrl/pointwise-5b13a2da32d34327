from fractions import Fraction
import sqlite3
from uuid import uuid4

from intake.receipts import AcceptedCurve
from report.repository import ReportRepository
from report.snapshot import ReportSnapshot, SourceSnapshot, SuccessReceipt


class PublicationError(RuntimeError):
    def __init__(self, report_id: str, receipt_id: str):
        super().__init__('report and success receipt could not be committed')
        self.report_id = report_id
        self.receipt_id = receipt_id


def _source(item: AcceptedCurve) -> SourceSnapshot:
    package = item.package
    return SourceSnapshot(
        item.received_id, package.issue_id, package.trial_id, package.revision_id, package.digest
    )


def publish_report(
    repository: ReportRepository,
    left: AcceptedCurve,
    right: AcceptedCurve,
    tolerance: Fraction,
    verdict: str,
) -> tuple[ReportSnapshot, SuccessReceipt]:
    report_id = f'report-{uuid4().hex}'
    receipt_id = f'receipt-{uuid4().hex}'
    sources = _source(left), _source(right)
    report = ReportSnapshot(report_id, sources, tolerance, verdict)
    receipt = SuccessReceipt(receipt_id, report_id, sources, tolerance)
    try:
        repository.commit(report, receipt)
    except sqlite3.Error as error:
        raise PublicationError(report_id, receipt_id) from error
    return report, receipt
