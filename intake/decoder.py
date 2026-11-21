from fractions import Fraction
import json
import re

from issue.curve import CurveKnot
from issue.package import PackageEnvelope, V1_VERSION
from thermal_core import InvalidInput, identifier


class InvalidPackage(ValueError):
    """An exchange item could not be admitted."""


_ENVELOPE_FIELDS = {'version', 'issue_id', 'trial_id', 'revision_id', 'body', 'digest'}
_HEX_DIGEST = re.compile(r'[0-9a-f]{64}')


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidPackage(f'duplicate JSON field {key}')
        result[key] = value
    return result


def _invalid_constant(value):
    raise InvalidPackage(f'invalid JSON constant {value}')


def _parse_object(wire: bytes, field: str) -> dict:
    if not isinstance(wire, bytes):
        raise InvalidPackage(f'{field} must be UTF-8 bytes')
    try:
        result = json.loads(
            wire.decode('utf-8'), object_pairs_hook=_unique_object, parse_constant=_invalid_constant
        )
    except InvalidPackage:
        raise
    except (ValueError, RecursionError) as error:
        raise InvalidPackage(f'invalid {field} JSON') from error
    if not isinstance(result, dict):
        raise InvalidPackage(f'{field} must be a JSON object')
    return result


def decode_envelope(wire: bytes) -> PackageEnvelope:
    fields = _parse_object(wire, 'envelope')
    if fields.keys() != _ENVELOPE_FIELDS:
        raise InvalidPackage('invalid envelope fields')
    if type(fields['version']) is not int or fields['version'] != V1_VERSION:
        raise InvalidPackage('unsupported envelope version')
    body = fields['body']
    digest = fields['digest']
    if not isinstance(body, str) or not isinstance(digest, str) or not _HEX_DIGEST.fullmatch(digest):
        raise InvalidPackage('invalid envelope body or digest')
    try:
        return PackageEnvelope(
            identifier(fields['issue_id'], 'issue identifier'),
            identifier(fields['trial_id'], 'trial identifier'),
            identifier(fields['revision_id'], 'trial revision'),
            body.encode('utf-8'),
            digest,
        )
    except (InvalidInput, UnicodeError) as error:
        raise InvalidPackage('invalid envelope identifiers or body encoding') from error


def _read_fraction(value, field: str) -> Fraction:
    if (
        not isinstance(value, list)
        or len(value) != 2
        or any(type(component) is not int for component in value)
        or value[1] == 0
    ):
        raise InvalidPackage(f'{field} must contain an integer numerator and nonzero denominator')
    return Fraction(value[0], value[1])


def decode_curve_body(body: bytes) -> tuple[CurveKnot, ...]:
    fields = _parse_object(body, 'curve body')
    if fields.keys() != {'knots'} or not isinstance(fields['knots'], list):
        raise InvalidPackage('invalid curve body fields')
    knots = []
    for pair in fields['knots']:
        if not isinstance(pair, list) or len(pair) != 2:
            raise InvalidPackage('each knot needs a time and a temperature')
        knots.append(CurveKnot(_read_fraction(pair[0], 'time'), _read_fraction(pair[1], 'temperature')))
    return tuple(knots)
