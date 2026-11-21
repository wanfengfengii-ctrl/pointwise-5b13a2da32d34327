from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from thermal_core import write_transaction

if TYPE_CHECKING:
    from issue.package import PackageEnvelope


class IssueRegistry:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def initialize(self) -> None:
        with write_transaction(self.connection):
            self.connection.execute('''
                CREATE TABLE IF NOT EXISTS issued_curves (
                    issue_id TEXT PRIMARY KEY NOT NULL,
                    revision_id TEXT NOT NULL REFERENCES trial_revisions(revision_id),
                    exchange_bytes BLOB NOT NULL
                )
            ''')

    def store_issue(self, package: PackageEnvelope) -> None:
        exchange_bytes = package.to_bytes()
        with write_transaction(self.connection):
            self.connection.execute('''
                INSERT INTO issued_curves (issue_id, revision_id, exchange_bytes)
                VALUES (?, ?, ?)
            ''', (package.issue_id, package.revision_id, exchange_bytes))
