from report.export import export_report
from report.repository import ReportRepository
from report.snapshot import ReportSnapshot, SuccessReceipt, restore_receipt, restore_snapshot
from thermal_core import InvalidInput, MissingRecord, identifier


def read_report(
    repository: ReportRepository, report_id: str, mode: str = 'receive'
) -> tuple[ReportSnapshot, SuccessReceipt] | str:
    identifier(report_id, 'report identifier')
    if mode not in ('receive', 'export'):
        raise InvalidInput('report mode must be receive or export')
    row = repository.get(report_id)
    if row is None:
        raise MissingRecord(f'unknown report {report_id}')
    report = restore_snapshot(row[0])
    receipt = restore_receipt(row[1])
    if mode == 'export':
        return export_report(report, receipt)
    return report, receipt
