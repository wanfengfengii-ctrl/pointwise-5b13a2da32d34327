from dataclasses import dataclass

from intake.catalog import IntakeCatalog
from intake.decoder import decode_envelope
from intake.identity import verify_package_identity
from intake.validation import validate_curve_body
from issue.curve import CalibratedCurve
from issue.package import PackageEnvelope
from thermal_core import InvalidInput, MissingRecord


@dataclass(frozen=True)
class AcceptedCurve:
    received_id: int
    package: PackageEnvelope
    curve: CalibratedCurve


def accept_curve(catalog: IntakeCatalog, exchange_bytes: bytes) -> int:
    package = decode_envelope(exchange_bytes)
    verify_package_identity(package)
    validate_curve_body(package.body)
    return catalog.store_or_get(package)


def validate_received_id(received_id) -> int:
    if type(received_id) is not int or received_id < 1:
        raise InvalidInput('received identifier must be a positive integer')
    return received_id


def get_accepted_curve(catalog: IntakeCatalog, received_id: int) -> AcceptedCurve:
    received_id = validate_received_id(received_id)
    if received_id > 2**63 - 1:
        raise MissingRecord(f'unknown received curve {received_id}')
    package = catalog.get(received_id)
    if package is None:
        raise MissingRecord(f'unknown received curve {received_id}')
    return AcceptedCurve(received_id, package, validate_curve_body(package.body))
