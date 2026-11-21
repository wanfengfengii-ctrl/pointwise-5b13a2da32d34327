from dataclasses import dataclass
from hashlib import sha256
import json
from uuid import uuid4

from issue.body import encode_curve_body
from issue.calibrated import calibrate_revision
from issue.curve import CalibratedCurve
from issue.registry import IssueRegistry
from thermal_core import InvalidInput, identifier
from trial.repository import TrialRepository
from trial.revisions import load_trial_revision


V1_VERSION = 1


def _encode(fields: dict) -> bytes:
    return json.dumps(fields, sort_keys=True, ensure_ascii=True, separators=(',', ':')).encode('ascii')


def _bound_fields(issue_id: str, trial_id: str, revision_id: str, body: bytes) -> dict:
    return {
        'version': V1_VERSION,
        'issue_id': issue_id,
        'trial_id': trial_id,
        'revision_id': revision_id,
        'body': body.decode('utf-8'),
    }


@dataclass(frozen=True)
class PackageEnvelope:
    issue_id: str
    trial_id: str
    revision_id: str
    body: bytes
    digest: str
    version: int = V1_VERSION

    def to_bytes(self) -> bytes:
        if type(self.version) is not int or self.version != V1_VERSION:
            raise InvalidInput('unsupported curve envelope version')
        fields = _bound_fields(self.issue_id, self.trial_id, self.revision_id, self.body)
        fields['digest'] = self.digest
        return _encode(fields)


def package_digest(issue_id: str, trial_id: str, revision_id: str, body: bytes) -> str:
    return sha256(_encode(_bound_fields(issue_id, trial_id, revision_id, body))).hexdigest()


def build_package(
    issue_id: str, trial_id: str, revision_id: str, curve: CalibratedCurve
) -> PackageEnvelope:
    identifier(issue_id, 'issue identifier')
    identifier(trial_id, 'trial identifier')
    identifier(revision_id, 'trial revision')
    body = encode_curve_body(curve)
    digest = package_digest(issue_id, trial_id, revision_id, body)
    return PackageEnvelope(issue_id, trial_id, revision_id, body, digest)


def issue_curve(
    repository: TrialRepository, registry: IssueRegistry, revision_id: str
) -> PackageEnvelope:
    revision = load_trial_revision(repository, revision_id)
    curve = calibrate_revision(repository, revision)
    package = build_package(f'issue-{uuid4().hex}', revision.trial_id, revision.revision_id, curve)
    registry.store_issue(package)
    return package
