from contextlib import closing
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

from compare.request import compare_and_publish
from intake.catalog import IntakeCatalog
from intake.receipts import accept_curve, get_accepted_curve
from intake.validation import validate_curve_body
from issue.package import issue_curve
from issue.registry import IssueRegistry
from report.readback import read_report
from report.repository import ReportRepository
from trial.calibration import register_calibration
from trial.repository import TrialRepository
from trial.revisions import load_trial_revision, record_trial


def _source(connection):
    trials = TrialRepository(connection)
    issues = IssueRegistry(connection)
    trials.initialize()
    issues.initialize()
    return trials, issues


def _analysis(connection):
    catalog = IntakeCatalog(connection)
    reports = ReportRepository(connection)
    catalog.initialize()
    reports.initialize()
    return catalog, reports


def _issue_sample(trials, issues, sample):
    calibration = register_calibration(trials, sample['probe_id'], **sample['calibration'])
    revision = record_trial(trials, sample['trial_id'], calibration, sample['samples'])
    return issue_curve(trials, issues, revision)


def _scenario(case_id, inputs, expected, actual, downstream_expected, downstream_actual, code_paths, oracle):
    if actual != expected or downstream_actual != downstream_expected:
        raise AssertionError(f'{case_id} observed {actual!r}, downstream {downstream_actual!r}')
    print('POINTWISE_SCENARIO ' + json.dumps({
        'case_id': case_id,
        'input': inputs,
        'expected': expected,
        'actual': actual,
        'downstream_expected': downstream_expected,
        'downstream_actual': downstream_actual,
        'code_paths': code_paths,
        'oracle': oracle,
    }, ensure_ascii=False, separators=(',', ':')))


def main():
    examples = Path(__file__).resolve().parent / 'examples'
    samples = [json.loads((examples / name).read_text(encoding='utf-8')) for name in ('trial_a.json', 'trial_b.json')]
    with TemporaryDirectory(prefix='thermal-demo-') as directory:
        root = Path(directory)
        source_path, analysis_path = root / 'source.sqlite3', root / 'analysis.sqlite3'
        exchange = root / 'exchange'
        exchange.mkdir()
        paths = [exchange / 'trial_a.v1.json', exchange / 'trial_b.v1.json']
        with closing(sqlite3.connect(source_path)) as source:
            trials, issues = _source(source)
            packages = [_issue_sample(trials, issues, sample) for sample in samples]
            issued_values = [str(validate_curve_body(package.body).value_at(1)) for package in packages]
            for path, package in zip(paths, packages):
                path.write_bytes(package.to_bytes())

        with closing(sqlite3.connect(analysis_path)) as analysis:
            catalog, reports = _analysis(analysis)
            left_id, right_id = [accept_curve(catalog, path.read_bytes()) for path in paths]
            accepted_values = [
                str(get_accepted_curve(catalog, received_id).curve.value_at(1))
                for received_id in (left_id, right_id)
            ]
            _scenario(
                'v1.elapsed_profile', {'elapsed_seconds': 1, 'trials': samples},
                ['21', '61/3'], issued_values, ['21', '61/3'], accepted_values,
                ['issue/calibrated.py', 'issue/curve.py', 'intake/receipts.py'],
                '先换算样例两端温度 20 与 21 °C，再按各自的 1 秒与 3 秒升温时长线性求值。',
            )
            tolerances = ['0', '1/4', '1/3']
            published = [
                compare_and_publish(catalog, reports, left_id, right_id, tolerance)
                for tolerance in tolerances
            ]
            recorded = [read_report(reports, report.report_id) for report, _ in published]
            _scenario(
                'v5', {'a_reaches_at': 1, 'b_reaches_at': 3, 'end': 4, 'tolerance_c': tolerances},
                ['retest', 'retest', 'equivalent'], [report.verdict for report, _ in published],
                {'verdicts': ['retest', 'retest', 'equivalent'], 'bound_to_request': True},
                {
                    'verdicts': [report.verdict for report, _ in recorded],
                    'bound_to_request': all(
                        report.received_ids == (left_id, right_id) and receipt.sources == report.sources
                        for report, receipt in recorded
                    ),
                },
                ['compare/request.py', 'compare/alignment.py', 'report/repository.py'],
                '甲第 1 秒时乙至多经过 2 秒，最低温差为 1/3 °C；路径经 (1,2) 可继续到 (4,4)。',
            )
            original, _ = published[0]
            before = read_report(reports, original.report_id, 'export')

            with closing(sqlite3.connect(source_path)) as source:
                trials, issues = _source(source)
                parent = load_trial_revision(trials, packages[1].revision_id)
                amended = record_trial(
                    trials, parent.trial_id, parent.calibration_id, samples[1]['amendment_samples'], parent.revision_id,
                )
                corrected_path = exchange / 'trial_b_corrected.v1.json'
                corrected_path.write_bytes(issue_curve(trials, issues, amended).to_bytes())

            corrected_id = accept_curve(catalog, corrected_path.read_bytes())
            corrected, _ = compare_and_publish(catalog, reports, left_id, corrected_id, 0)
            corrected_export = read_report(reports, corrected.report_id, 'export')

        with closing(sqlite3.connect(analysis_path)) as analysis:
            _, reports = _analysis(analysis)
            old_after = read_report(reports, original.report_id, 'export')
            new_after = read_report(reports, corrected.report_id, 'export')
            _scenario(
                'v6.original_export', {'corrected_b_reaches_at': 2, 'a_reaches_at': 1, 'tolerance_c': '0'},
                ['retest', 'equivalent'], [original.verdict, corrected.verdict],
                {'verdicts': ['retest', 'equivalent'], 'original_exports_preserved': True, 'different_b_revisions': True},
                {
                    'verdicts': [json.loads(export)['report']['verdict'] for export in (old_after, new_after)],
                    'original_exports_preserved': (old_after, new_after) == (before, corrected_export),
                    'different_b_revisions': original.sources[1].revision_id != corrected.sources[1].revision_id,
                },
                ['trial/revisions.py', 'report/readback.py', 'report/export.py'],
                '勘误后可经 (1,2) 零温差对齐，报告号各自绑定签发当时的原快照。',
            )


if __name__ == '__main__':
    main()
