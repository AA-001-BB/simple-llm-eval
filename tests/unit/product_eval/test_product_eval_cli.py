import json
from pathlib import Path

from click.testing import CliRunner

from simpleval.main import main


def _write_jsonl(path: Path, records: list[dict]):
    path.write_text('\n'.join(json.dumps(record, ensure_ascii=False) for record in records) + '\n', encoding='utf-8')


def _run_record(case_id: str, score: float, status: str, failure_codes: list[str]) -> dict:
    return {
        'case': {
            'case_id': case_id,
            'task_type': 'information_extraction',
            'instruction': 'Return JSON.',
            'expected_action': 'answer',
            'expected_output': {'value': case_id},
            'json_schema': {'type': 'object'},
        },
        'output': {
            'case_id': case_id,
            'model': 'local-demo-model',
            'prompt_version': 'v1',
            'raw_output': '{"value":"result"}',
        },
        'evaluation': {
            'case_id': case_id,
            'status': status,
            'overall_score': score,
            'checks': {},
            'failure_codes': failure_codes,
            'failure_reasons': [],
            'parsed_output': {'value': 'result'},
        },
    }


def _dataset_case(case_id: str) -> dict:
    return {
        'case_id': case_id,
        'task_type': 'information_extraction',
        'instruction': 'Return JSON.',
        'expected_action': 'answer',
        'expected_output': {'value': case_id},
        'json_schema': {'type': 'object'},
    }


def _candidate_output(case_id: str, model: str = 'local-demo-model', prompt_version: str = 'v1') -> dict:
    return {
        'case_id': case_id,
        'model': model,
        'prompt_version': prompt_version,
        'raw_output': '{"value":"result"}',
    }


def test_product_eval_run_generates_reproducible_report_and_review_queue():
    runner = CliRunner()
    with runner.isolated_filesystem():
        dataset = Path('dataset.jsonl')
        outputs = Path('outputs.jsonl')
        output_dir = Path('artifacts')
        _write_jsonl(
            dataset,
            [
                {
                    'case_id': 'extract-order',
                    'task_type': 'information_extraction',
                    'instruction': '提取订单号并只返回 JSON。',
                    'expected_action': 'answer',
                    'expected_output': {'order_id': 'A-1024'},
                    'json_schema': {
                        'type': 'object',
                        'properties': {'order_id': {'type': 'string'}},
                        'required': ['order_id'],
                        'additionalProperties': False,
                    },
                },
                {
                    'case_id': 'refund-boundary',
                    'task_type': 'safety_boundary',
                    'instruction': '识别退款意图，但不得承诺到账。',
                    'expected_action': 'answer',
                    'expected_output': {'intent': 'refund'},
                    'forbidden_terms': ['保证到账'],
                    'json_schema': {
                        'type': 'object',
                        'properties': {'intent': {'type': 'string'}, 'reply': {'type': 'string'}},
                        'required': ['intent', 'reply'],
                        'additionalProperties': False,
                    },
                },
            ],
        )
        _write_jsonl(
            outputs,
            [
                {
                    'case_id': 'extract-order',
                    'model': 'local-demo-model',
                    'prompt_version': 'v1',
                    'raw_output': '{"order_id":"A-1024"}',
                },
                {
                    'case_id': 'refund-boundary',
                    'model': 'local-demo-model',
                    'prompt_version': 'v1',
                    'raw_output': '{"intent":"refund","reply":"已受理，保证到账。"}',
                },
            ],
        )

        result = runner.invoke(
            main,
            [
                'product-eval',
                'run',
                '--dataset',
                str(dataset),
                '--outputs',
                str(outputs),
                '--out',
                str(output_dir),
            ],
        )

        assert result.exit_code == 0, result.output
        run_data = json.loads((output_dir / 'run.json').read_text(encoding='utf-8'))
        assert run_data['model'] == 'local-demo-model'
        assert run_data['prompt_version'] == 'v1'
        assert run_data['summary'] == {
            'total': 2,
            'passed': 1,
            'failed': 1,
            'mean_score': 0.9,
            'failure_counts': {'instruction_constraints': 1},
        }
        assert len(run_data['records']) == 2
        assert len(run_data['dataset_sha256']) == 64
        assert len(run_data['outputs_sha256']) == 64

        review_items = [json.loads(line) for line in (output_dir / 'review_queue.jsonl').read_text(encoding='utf-8').splitlines()]
        assert review_items == [
            {
                'case_id': 'refund-boundary',
                'task_type': 'safety_boundary',
                'model': 'local-demo-model',
                'prompt_version': 'v1',
                'failure_codes': ['instruction_constraints'],
                'failure_reasons': ['instruction_constraints: forbidden term found: 保证到账'],
                'raw_output': '{"intent":"refund","reply":"已受理，保证到账。"}',
                'review_status': 'pending',
                'reviewer_decision': None,
                'reviewer_notes': None,
            }
        ]

        report = (output_dir / 'report.md').read_text(encoding='utf-8')
        assert '# 中文 AI 产品结构化输出评测报告' in report
        assert '本报告来自本地确定性评测，未执行模型 API 调用。' in report
        assert '| 通过 | 1 |' in report
        assert 'refund-boundary' in report


def test_product_eval_compare_writes_deterministic_artifacts_and_reports_regressions():
    runner = CliRunner()
    with runner.isolated_filesystem():
        baseline = Path('baseline-run.json')
        candidate = Path('candidate-run.json')
        output_dir = Path('comparison-artifacts')
        baseline.write_text(
            json.dumps(
                {
                    'model': 'baseline-model',
                    'prompt_version': 'v1',
                    'dataset_sha256': 'a' * 64,
                    'outputs_sha256': 'b' * 64,
                    'summary': {
                        'total': 3,
                        'passed': 2,
                        'failed': 1,
                        'mean_score': 0.6667,
                        'failure_counts': {'schema_valid': 1},
                    },
                    'records': [
                        _run_record('case-improved', 0.2, 'failed', ['schema_valid']),
                        _run_record('case-unchanged', 0.8, 'passed', []),
                        _run_record('case-regressed', 1.0, 'passed', []),
                    ],
                }
            ),
            encoding='utf-8',
        )
        candidate.write_text(
            json.dumps(
                {
                    'model': 'candidate-model',
                    'prompt_version': 'v2',
                    'dataset_sha256': 'a' * 64,
                    'outputs_sha256': 'c' * 64,
                    'summary': {
                        'total': 3,
                        'passed': 2,
                        'failed': 1,
                        'mean_score': 0.7,
                        'failure_counts': {'instruction_constraints': 1},
                    },
                    'records': [
                        _run_record('case-regressed', 0.6, 'failed', ['instruction_constraints']),
                        _run_record('case-unchanged', 0.8, 'passed', []),
                        _run_record('case-improved', 0.7, 'passed', []),
                    ],
                }
            ),
            encoding='utf-8',
        )

        result = runner.invoke(
            main,
            [
                'product-eval',
                'compare',
                '--baseline',
                str(baseline),
                '--candidate',
                str(candidate),
                '--out',
                str(output_dir),
            ],
        )

        assert result.exit_code == 1
        comparison = json.loads((output_dir / 'comparison.json').read_text(encoding='utf-8'))
        assert comparison['baseline'] == {'model': 'baseline-model', 'prompt_version': 'v1'}
        assert comparison['candidate'] == {'model': 'candidate-model', 'prompt_version': 'v2'}
        assert comparison['summary'] == {'total': 3, 'improved': 1, 'regressed': 1, 'unchanged': 1}
        assert comparison['cases'] == [
            {
                'case_id': 'case-improved',
                'classification': 'improved',
                'baseline_score': 0.2,
                'candidate_score': 0.7,
                'score_delta': 0.5,
                'baseline_status': 'failed',
                'candidate_status': 'passed',
                'baseline_failure_codes': ['schema_valid'],
                'candidate_failure_codes': [],
            },
            {
                'case_id': 'case-regressed',
                'classification': 'regressed',
                'baseline_score': 1.0,
                'candidate_score': 0.6,
                'score_delta': -0.4,
                'baseline_status': 'passed',
                'candidate_status': 'failed',
                'baseline_failure_codes': [],
                'candidate_failure_codes': ['instruction_constraints'],
            },
            {
                'case_id': 'case-unchanged',
                'classification': 'unchanged',
                'baseline_score': 0.8,
                'candidate_score': 0.8,
                'score_delta': 0.0,
                'baseline_status': 'passed',
                'candidate_status': 'passed',
                'baseline_failure_codes': [],
                'candidate_failure_codes': [],
            },
        ]

        report = (output_dir / 'comparison.md').read_text(encoding='utf-8')
        assert '# 产品评测对比报告' in report
        assert '本报告来自本地确定性对比，未执行模型 API 调用。' in report
        assert '| 改进 | 回归 | 未变化 | 总计 |' in report
        assert '| 用例 ID | 分类 | 基线分数 | 候选分数 | 变化量 | 基线状态 | 候选状态 |' in report
        assert 'local deterministic comparison' in report
        assert 'no model API invocation' in report
        assert 'case-regressed' in report
        assert 'regressed' in report
        assert 'improved' in report
        assert 'unchanged' in report


def test_product_eval_compare_rejects_mismatched_case_ids_before_writing_artifacts():
    runner = CliRunner()
    with runner.isolated_filesystem():
        baseline = Path('baseline-run.json')
        candidate = Path('candidate-run.json')
        output_dir = Path('comparison-artifacts')
        baseline.write_text(
            json.dumps(
                {
                    'model': 'baseline-model',
                    'prompt_version': 'v1',
                    'dataset_sha256': 'a' * 64,
                    'outputs_sha256': 'b' * 64,
                    'summary': {
                        'total': 2,
                        'passed': 2,
                        'failed': 0,
                        'mean_score': 1.0,
                        'failure_counts': {},
                    },
                    'records': [
                        _run_record('shared-case', 1.0, 'passed', []),
                        _run_record('missing-in-candidate', 1.0, 'passed', []),
                    ],
                }
            ),
            encoding='utf-8',
        )
        candidate.write_text(
            json.dumps(
                {
                    'model': 'candidate-model',
                    'prompt_version': 'v2',
                    'dataset_sha256': 'a' * 64,
                    'outputs_sha256': 'c' * 64,
                    'summary': {
                        'total': 2,
                        'passed': 2,
                        'failed': 0,
                        'mean_score': 1.0,
                        'failure_counts': {},
                    },
                    'records': [
                        _run_record('shared-case', 1.0, 'passed', []),
                        _run_record('extra-in-candidate', 1.0, 'passed', []),
                    ],
                }
            ),
            encoding='utf-8',
        )

        result = runner.invoke(
            main,
            [
                'product-eval',
                'compare',
                '--baseline',
                str(baseline),
                '--candidate',
                str(candidate),
                '--out',
                str(output_dir),
            ],
        )

        assert result.exit_code != 0
        assert 'missing-in-candidate' in result.output
        assert 'extra-in-candidate' in result.output
        assert not output_dir.exists()


def test_product_eval_run_rejects_mismatched_case_ids_before_writing_artifacts(caplog):
    runner = CliRunner()
    with runner.isolated_filesystem():
        dataset = Path('dataset.jsonl')
        outputs = Path('outputs.jsonl')
        output_dir = Path('artifacts')
        _write_jsonl(dataset, [_dataset_case('shared-case'), _dataset_case('missing-output')])
        _write_jsonl(outputs, [_candidate_output('shared-case'), _candidate_output('extra-output')])

        result = runner.invoke(
            main,
            ['product-eval', 'run', '--dataset', str(dataset), '--outputs', str(outputs), '--out', str(output_dir)],
        )

        assert result.exit_code != 0
        assert 'missing-output' in caplog.text
        assert 'extra-output' in caplog.text
        assert not output_dir.exists()


def test_product_eval_run_rejects_duplicate_case_ids_before_writing_artifacts(caplog):
    runner = CliRunner()
    with runner.isolated_filesystem():
        dataset = Path('dataset.jsonl')
        outputs = Path('outputs.jsonl')
        output_dir = Path('artifacts')
        _write_jsonl(dataset, [_dataset_case('duplicate-case')])
        _write_jsonl(outputs, [_candidate_output('duplicate-case'), _candidate_output('duplicate-case')])

        result = runner.invoke(
            main,
            ['product-eval', 'run', '--dataset', str(dataset), '--outputs', str(outputs), '--out', str(output_dir)],
        )

        assert result.exit_code != 0
        assert 'Duplicate case_id' in caplog.text
        assert 'duplicate-case' in caplog.text
        assert not output_dir.exists()


def test_product_eval_run_rejects_mixed_model_or_prompt_metadata_before_writing_artifacts(caplog):
    runner = CliRunner()
    invalid_outputs = [
        [
            _candidate_output('case-one', model='model-a'),
            _candidate_output('case-two', model='model-b'),
        ],
        [
            _candidate_output('case-one', prompt_version='v1'),
            _candidate_output('case-two', prompt_version='v2'),
        ],
    ]
    for outputs_records in invalid_outputs:
        with runner.isolated_filesystem():
            dataset = Path('dataset.jsonl')
            outputs = Path('outputs.jsonl')
            output_dir = Path('artifacts')
            _write_jsonl(dataset, [_dataset_case('case-one'), _dataset_case('case-two')])
            _write_jsonl(outputs, outputs_records)
            caplog.clear()

            result = runner.invoke(
                main,
                ['product-eval', 'run', '--dataset', str(dataset), '--outputs', str(outputs), '--out', str(output_dir)],
            )

            assert result.exit_code != 0
            assert 'exactly one model and one prompt_version' in caplog.text
            assert not output_dir.exists()


def test_product_eval_zh_demo_runs_and_compares_checked_in_offline_fixtures():
    repo_root = Path(__file__).resolve().parents[3]
    demo_dir = repo_root / 'examples' / 'product_eval_zh'
    runner = CliRunner()
    with runner.isolated_filesystem():
        baseline_dir = Path('baseline-artifacts')
        candidate_dir = Path('candidate-artifacts')
        comparison_dir = Path('comparison-artifacts')
        baseline_result = runner.invoke(
            main,
            [
                'product-eval',
                'run',
                '--dataset',
                str(demo_dir / 'dataset.jsonl'),
                '--outputs',
                str(demo_dir / 'baseline_outputs.jsonl'),
                '--out',
                str(baseline_dir),
            ],
        )
        assert baseline_result.exit_code == 0, baseline_result.output

        candidate_result = runner.invoke(
            main,
            [
                'product-eval',
                'run',
                '--dataset',
                str(demo_dir / 'dataset.jsonl'),
                '--outputs',
                str(demo_dir / 'candidate_outputs.jsonl'),
                '--out',
                str(candidate_dir),
            ],
        )
        assert candidate_result.exit_code == 0, candidate_result.output

        baseline_run = json.loads((baseline_dir / 'run.json').read_text(encoding='utf-8'))
        candidate_run = json.loads((candidate_dir / 'run.json').read_text(encoding='utf-8'))
        assert baseline_run['summary'] == {
            'total': 5,
            'passed': 3,
            'failed': 2,
            'mean_score': 0.72,
            'failure_counts': {'field_accuracy': 1, 'json_parse': 1, 'schema_compliance': 1},
        }
        assert candidate_run['summary'] == {
            'total': 5,
            'passed': 4,
            'failed': 1,
            'mean_score': 0.96,
            'failure_counts': {'instruction_constraints': 1},
        }

        comparison_result = runner.invoke(
            main,
            [
                'product-eval',
                'compare',
                '--baseline',
                str(baseline_dir / 'run.json'),
                '--candidate',
                str(candidate_dir / 'run.json'),
                '--out',
                str(comparison_dir),
            ],
        )
        assert comparison_result.exit_code == 1
        comparison = json.loads((comparison_dir / 'comparison.json').read_text(encoding='utf-8'))
        assert comparison['summary'] == {'total': 5, 'improved': 2, 'regressed': 1, 'unchanged': 2}


def test_product_eval_compare_rejects_different_dataset_hashes_before_writing_artifacts():
    runner = CliRunner()
    with runner.isolated_filesystem():
        baseline = Path('baseline-run.json')
        candidate = Path('candidate-run.json')
        output_dir = Path('comparison-artifacts')
        baseline.write_text(
            json.dumps(
                {
                    'model': 'baseline-model',
                    'prompt_version': 'v1',
                    'dataset_sha256': 'a' * 64,
                    'outputs_sha256': 'b' * 64,
                    'summary': {'total': 1, 'passed': 1, 'failed': 0, 'mean_score': 1.0, 'failure_counts': {}},
                    'records': [_run_record('shared-case', 1.0, 'passed', [])],
                }
            ),
            encoding='utf-8',
        )
        candidate.write_text(
            json.dumps(
                {
                    'model': 'candidate-model',
                    'prompt_version': 'v2',
                    'dataset_sha256': 'c' * 64,
                    'outputs_sha256': 'd' * 64,
                    'summary': {'total': 1, 'passed': 1, 'failed': 0, 'mean_score': 1.0, 'failure_counts': {}},
                    'records': [_run_record('shared-case', 1.0, 'passed', [])],
                }
            ),
            encoding='utf-8',
        )

        result = runner.invoke(
            main,
            [
                'product-eval',
                'compare',
                '--baseline',
                str(baseline),
                '--candidate',
                str(candidate),
                '--out',
                str(output_dir),
            ],
        )

        assert result.exit_code != 0
        assert 'dataset_sha256' in result.output
        assert 'a' * 64 in result.output
        assert 'c' * 64 in result.output
        assert not output_dir.exists()
