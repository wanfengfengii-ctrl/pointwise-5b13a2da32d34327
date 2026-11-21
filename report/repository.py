import sqlite3

from report.snapshot import ReportSnapshot, SuccessReceipt, serialize_receipt, serialize_snapshot
from thermal_core import InvalidInput, write_transaction


class ReportRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def initialize(self) -> None:
        with write_transaction(self.connection):
            self.connection.execute('''
                CREATE TABLE IF NOT EXISTS reports (
                    report_id TEXT PRIMARY KEY NOT NULL,
                    snapshot TEXT NOT NULL
                )
            ''')
            self.connection.execute('''
                CREATE TABLE IF NOT EXISTS success_receipts (
                    receipt_id TEXT PRIMARY KEY NOT NULL,
                    report_id TEXT NOT NULL UNIQUE REFERENCES reports(report_id),
                    snapshot TEXT NOT NULL
                )
            ''')

    def commit(self, report: ReportSnapshot, receipt: SuccessReceipt) -> None:
        if (report.report_id, report.sources, report.tolerance) != (
            receipt.report_id, receipt.sources, receipt.tolerance
        ):
            raise InvalidInput('success receipt must match the published report')
        report_payload = serialize_snapshot(report)
        receipt_payload = serialize_receipt(receipt)
        with write_transaction(self.connection):
            self.connection.execute('''
                INSERT INTO reports (report_id, snapshot) VALUES (?, ?)
            ''', (report.report_id, report_payload))
            self.connection.execute('''
                INSERT INTO success_receipts (receipt_id, report_id, snapshot) VALUES (?, ?, ?)
            ''', (receipt.receipt_id, receipt.report_id, receipt_payload))

    def get(self, report_id: str) -> tuple[str, str] | None:
        row = self.connection.execute('''
            SELECT reports.snapshot, success_receipts.snapshot
            FROM reports JOIN success_receipts USING (report_id)
            WHERE reports.report_id = ?
        ''', (report_id,)).fetchone()
        return None if row is None else (row[0], row[1])
