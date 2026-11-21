import json

from report.snapshot import ReportSnapshot, SuccessReceipt, serialize_receipt, serialize_snapshot


def export_report(report: ReportSnapshot, receipt: SuccessReceipt) -> str:
    payload = {
        'report': json.loads(serialize_snapshot(report)),
        'receipt': json.loads(serialize_receipt(receipt)),
    }
    return json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(',', ':'))
