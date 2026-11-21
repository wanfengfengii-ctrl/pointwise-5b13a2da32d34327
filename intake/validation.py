from intake.decoder import InvalidPackage, decode_curve_body
from issue.curve import CalibratedCurve
from thermal_core import InvalidInput


def validate_curve_body(body: bytes) -> CalibratedCurve:
    knots = decode_curve_body(body)
    try:
        return CalibratedCurve(knots)
    except InvalidInput as error:
        raise InvalidPackage(str(error)) from error
