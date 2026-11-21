from dataclasses import asdict, dataclass
from fractions import Fraction
import json


@dataclass(frozen=True)
class SourceSnapshot:
    received_id: int
    issue_id: str
    trial_id: str
    revision_id: str
    digest: str


@dataclass(frozen=True)
class ReportSnapshot:
    report_id: str
    sources: tuple[SourceSnapshot, SourceSnapshot]
    tolerance: Fraction
    verdict: str

    @property
    def received_ids(self) -> tuple[int, int]:
        left, right = self.sources
        return left.received_id, right.received_id


@dataclass(frozen=True)
class SuccessReceipt:
    receipt_id: str
    report_id: str
    sources: tuple[SourceSnapshot, SourceSnapshot]
    tolerance: Fraction

    @property
    def received_ids(self) -> tuple[int, int]:
        left, right = self.sources
        return left.received_id, right.received_id


def _bound_fields(record: ReportSnapshot | SuccessReceipt) -> dict:
    left_id, right_id = record.received_ids
    return {
        'report_id': record.report_id,
        'request': {
            'left_received_id': left_id,
            'right_received_id': right_id,
            'tolerance': [record.tolerance.numerator, record.tolerance.denominator],
        },
        'sources': [asdict(source) for source in record.sources],
    }


def _encode(fields: dict) -> str:
    return json.dumps(fields, ensure_ascii=True, sort_keys=True, separators=(',', ':'))


def serialize_snapshot(snapshot: ReportSnapshot) -> str:
    fields = _bound_fields(snapshot)
    fields['verdict'] = snapshot.verdict
    return _encode(fields)


def serialize_receipt(receipt: SuccessReceipt) -> str:
    fields = _bound_fields(receipt)
    fields['receipt_id'] = receipt.receipt_id
    return _encode(fields)


def _restore_binding(fields: dict) -> tuple[tuple[SourceSnapshot, SourceSnapshot], Fraction]:
    left, right = (SourceSnapshot(**source) for source in fields['sources'])
    request = fields['request']
    if (left.received_id, right.received_id) != (request['left_received_id'], request['right_received_id']):
        raise ValueError('stored request and source order disagree')
    return (left, right), Fraction(*request['tolerance'])


def restore_snapshot(payload: str) -> ReportSnapshot:
    fields = json.loads(payload)
    sources, tolerance = _restore_binding(fields)
    return ReportSnapshot(fields['report_id'], sources, tolerance, fields['verdict'])


def restore_receipt(payload: str) -> SuccessReceipt:
    fields = json.loads(payload)
    sources, tolerance = _restore_binding(fields)
    return SuccessReceipt(fields['receipt_id'], fields['report_id'], sources, tolerance)
