from hmac import compare_digest

from intake.decoder import InvalidPackage
from issue.package import PackageEnvelope, package_digest


def verify_package_identity(package: PackageEnvelope) -> None:
    expected = package_digest(package.issue_id, package.trial_id, package.revision_id, package.body)
    if not compare_digest(expected, package.digest):
        raise InvalidPackage('package identity does not bind the supplied body and provenance')


def same_issued_item(left: PackageEnvelope, right: PackageEnvelope) -> bool:
    return left == right
