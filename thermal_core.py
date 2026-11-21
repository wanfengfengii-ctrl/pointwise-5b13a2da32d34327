from contextlib import contextmanager
from fractions import Fraction
import re
import sqlite3


class InvalidInput(ValueError):
    """A supplied business value could not be accepted."""


class MissingRecord(LookupError):
    """A specified fixed record does not exist."""


_RATIONAL = re.compile(r'[+-]?[0-9]+(?:/[+-]?[0-9]+)?')


def exact_rational(value, field: str) -> Fraction:
    if isinstance(value, Fraction):
        return value
    if type(value) is int:
        return Fraction(value)
    if isinstance(value, str) and _RATIONAL.fullmatch(value):
        numerator, separator, denominator = value.partition('/')
        try:
            return Fraction(int(numerator), int(denominator) if separator else 1)
        except (ValueError, ZeroDivisionError) as error:
            raise InvalidInput(f'{field} must be an exact rational') from error
    raise InvalidInput(f'{field} must be an exact rational')


def identifier(value, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
    ):
        raise InvalidInput(f'{field} must be a nonempty identifier')
    try:
        value.encode('utf-8')
    except UnicodeError as error:
        raise InvalidInput(f'{field} must be valid UTF-8') from error
    return value


@contextmanager
def write_transaction(connection: sqlite3.Connection):
    """Own one repository write, even on a connection in autocommit mode."""
    if connection.in_transaction:
        raise sqlite3.ProgrammingError('repository writes require an idle connection')
    connection.execute('PRAGMA foreign_keys = ON')
    connection.execute('BEGIN IMMEDIATE')
    try:
        yield
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
