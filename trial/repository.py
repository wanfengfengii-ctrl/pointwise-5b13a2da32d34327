from fractions import Fraction
import sqlite3

from thermal_core import write_transaction


class TrialRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def initialize(self) -> None:
        with write_transaction(self.connection):
            self.connection.execute('''
                CREATE TABLE IF NOT EXISTS calibrations (
                    revision_id TEXT PRIMARY KEY NOT NULL,
                    probe_id TEXT NOT NULL,
                    scale_n TEXT NOT NULL,
                    scale_d TEXT NOT NULL,
                    offset_n TEXT NOT NULL,
                    offset_d TEXT NOT NULL
                )
            ''')
            self.connection.execute('''
                CREATE TABLE IF NOT EXISTS trial_revisions (
                    revision_id TEXT PRIMARY KEY NOT NULL,
                    trial_id TEXT NOT NULL,
                    calibration_id TEXT NOT NULL REFERENCES calibrations(revision_id),
                    parent_id TEXT REFERENCES trial_revisions(revision_id)
                )
            ''')
            self.connection.execute('''
                CREATE TABLE IF NOT EXISTS samples (
                    revision_id TEXT NOT NULL REFERENCES trial_revisions(revision_id),
                    position INTEGER NOT NULL,
                    time_n TEXT NOT NULL,
                    time_d TEXT NOT NULL,
                    reading_n TEXT NOT NULL,
                    reading_d TEXT NOT NULL,
                    PRIMARY KEY (revision_id, position)
                )
            ''')

    def store_calibration(
        self, revision_id: str, probe_id: str, scale: Fraction, offset: Fraction
    ) -> None:
        with write_transaction(self.connection):
            self.connection.execute('''
                INSERT INTO calibrations
                    (revision_id, probe_id, scale_n, scale_d, offset_n, offset_d)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (revision_id, probe_id, *_fraction_fields(scale), *_fraction_fields(offset)))

    def get_calibration(self, revision_id: str) -> tuple[str, Fraction, Fraction] | None:
        row = self.connection.execute('''
            SELECT probe_id, scale_n, scale_d, offset_n, offset_d
            FROM calibrations WHERE revision_id = ?
        ''', (revision_id,)).fetchone()
        if row is None:
            return None
        probe_id, scale_n, scale_d, offset_n, offset_d = row
        return probe_id, _restore_fraction(scale_n, scale_d), _restore_fraction(offset_n, offset_d)

    def store_revision(self, revision_id, trial_id, calibration_id, parent_id, samples) -> None:
        with write_transaction(self.connection):
            self.connection.execute('''
                INSERT INTO trial_revisions (revision_id, trial_id, calibration_id, parent_id)
                VALUES (?, ?, ?, ?)
            ''', (revision_id, trial_id, calibration_id, parent_id))
            self.connection.executemany('''
                INSERT INTO samples (revision_id, position, time_n, time_d, reading_n, reading_d)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                (revision_id, position, *_fraction_fields(sample.time), *_fraction_fields(sample.reading))
                for position, sample in enumerate(samples)
            ))

    def get_revision(self, revision_id: str):
        header = self.connection.execute('''
            SELECT trial_id, calibration_id, parent_id
            FROM trial_revisions WHERE revision_id = ?
        ''', (revision_id,)).fetchone()
        if header is None:
            return None
        rows = self.connection.execute('''
            SELECT time_n, time_d, reading_n, reading_d
            FROM samples WHERE revision_id = ? ORDER BY position
        ''', (revision_id,))
        points = tuple(
            (_restore_fraction(time_n, time_d), _restore_fraction(reading_n, reading_d))
            for time_n, time_d, reading_n, reading_d in rows
        )
        return *header, points


def _fraction_fields(value: Fraction) -> tuple[str, str]:
    return str(value.numerator), str(value.denominator)


def _restore_fraction(numerator: str, denominator: str) -> Fraction:
    return Fraction(int(numerator), int(denominator))
