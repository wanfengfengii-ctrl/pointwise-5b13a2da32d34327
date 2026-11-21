import sqlite3

from intake.decoder import InvalidPackage
from intake.identity import same_issued_item
from issue.package import PackageEnvelope
from thermal_core import write_transaction


class IntakeConflict(InvalidPackage):
    """A received issue number is already bound to a different item."""


class IntakeCatalog:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def initialize(self) -> None:
        with write_transaction(self.connection):
            self.connection.execute('''
                CREATE TABLE IF NOT EXISTS accepted_curves (
                    received_id INTEGER PRIMARY KEY,
                    issue_id TEXT NOT NULL UNIQUE,
                    trial_id TEXT NOT NULL,
                    revision_id TEXT NOT NULL,
                    body BLOB NOT NULL,
                    digest TEXT NOT NULL
                )
            ''')

    def store_or_get(self, package: PackageEnvelope) -> int:
        with write_transaction(self.connection):
            row = self.connection.execute('''
                SELECT received_id, issue_id, trial_id, revision_id, body, digest
                FROM accepted_curves WHERE issue_id = ?
            ''', (package.issue_id,)).fetchone()
            if row is not None:
                received_id, *fields = row
                if not same_issued_item(PackageEnvelope(*fields), package):
                    raise IntakeConflict(f'issue {package.issue_id} is already bound to a different item')
                return received_id

            cursor = self.connection.execute('''
                INSERT INTO accepted_curves (issue_id, trial_id, revision_id, body, digest)
                VALUES (?, ?, ?, ?, ?)
            ''', (package.issue_id, package.trial_id, package.revision_id, package.body, package.digest))
            return cursor.lastrowid

    def get(self, received_id: int) -> PackageEnvelope | None:
        row = self.connection.execute('''
            SELECT issue_id, trial_id, revision_id, body, digest
            FROM accepted_curves WHERE received_id = ?
        ''', (received_id,)).fetchone()
        return None if row is None else PackageEnvelope(*row)
