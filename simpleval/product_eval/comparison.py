from pathlib import Path

import click

from simpleval.product_eval.models import (
    CaseComparison,
    ComparisonRunMetadata,
    ComparisonSummary,
    EvaluationComparison,
    EvaluationRun,
)


def compare_evaluation_runs(baseline_path: Path, candidate_path: Path, output_dir: Path) -> EvaluationComparison:
    baseline = EvaluationRun.model_validate_json(baseline_path.read_text(encoding='utf-8'))
    candidate = EvaluationRun.model_validate_json(candidate_path.read_text(encoding='utf-8'))
    if baseline.dataset_sha256 != candidate.dataset_sha256:
        message = (
            'Dataset hashes differ. '
            f'Baseline dataset_sha256: {baseline.dataset_sha256}. '
            f'Candidate dataset_sha256: {candidate.dataset_sha256}.'
        )
        click.echo(message, err=True)
        raise ValueError(message)

    baseline_records = {record.case.case_id: record for record in baseline.records}
    candidate_records = {record.case.case_id: record for record in candidate.records}
    missing_in_candidate = sorted(baseline_records.keys() - candidate_records.keys())
    extra_in_candidate = sorted(candidate_records.keys() - baseline_records.keys())
    if missing_in_candidate or extra_in_candidate:
        message = (
            'Case ID sets differ. '
            f'Missing in candidate: {", ".join(missing_in_candidate) or "none"}. '
            f'Extra in candidate: {", ".join(extra_in_candidate) or "none"}.'
        )
        click.echo(message, err=True)
        raise ValueError(message)

    comparisons = [
        _compare_case(case_id, baseline_records[case_id], candidate_records[case_id])
        for case_id in sorted(baseline_records.keys() & candidate_records.keys())
    ]
    comparison = EvaluationComparison(
        baseline=ComparisonRunMetadata(model=baseline.model, prompt_version=baseline.prompt_version),
        candidate=ComparisonRunMetadata(model=candidate.model, prompt_version=candidate.prompt_version),
        summary=ComparisonSummary(
            total=len(comparisons),
            improved=sum(item.classification == 'improved' for item in comparisons),
            regressed=sum(item.classification == 'regressed' for item in comparisons),
            unchanged=sum(item.classification == 'unchanged' for item in comparisons),
        ),
        cases=comparisons,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / 'comparison.json').write_text(comparison.model_dump_json(indent=2), encoding='utf-8')
    (output_dir / 'comparison.md').write_text(_render_markdown(comparison), encoding='utf-8')
    return comparison


def _compare_case(case_id: str, baseline_record, candidate_record) -> CaseComparison:
    baseline_evaluation = baseline_record.evaluation
    candidate_evaluation = candidate_record.evaluation
    score_delta = round(candidate_evaluation.overall_score - baseline_evaluation.overall_score, 4)
    if score_delta > 0:
        classification = 'improved'
    elif score_delta < 0:
        classification = 'regressed'
    else:
        classification = 'unchanged'

    return CaseComparison(
        case_id=case_id,
        classification=classification,
        baseline_score=baseline_evaluation.overall_score,
        candidate_score=candidate_evaluation.overall_score,
        score_delta=score_delta,
        baseline_status=baseline_evaluation.status,
        candidate_status=candidate_evaluation.status,
        baseline_failure_codes=baseline_evaluation.failure_codes,
        candidate_failure_codes=candidate_evaluation.failure_codes,
    )


def _render_markdown(comparison: EvaluationComparison) -> str:
    lines = [
        '# 产品评测对比报告',
        '',
        '本报告来自本地确定性对比，未执行模型 API 调用。 (This is a local deterministic comparison with no model API invocation.)',
        '',
        f'- 基线模型：`{comparison.baseline.model}`（提示版本 `{comparison.baseline.prompt_version}`）',
        f'- 候选模型：`{comparison.candidate.model}`（提示版本 `{comparison.candidate.prompt_version}`）',
        '',
        '## 摘要',
        '',
        '| 改进 | 回归 | 未变化 | 总计 |',
        '| --- | --- | --- | --- |',
        (
            f'| {comparison.summary.improved} | {comparison.summary.regressed} '
            f'| {comparison.summary.unchanged} | {comparison.summary.total} |'
        ),
        '',
        '## 用例',
        '',
        '| 用例 ID | 分类 | 基线分数 | 候选分数 | 变化量 | 基线状态 | 候选状态 |',
        '| --- | --- | ---: | ---: | ---: | --- | --- |',
    ]
    for item in comparison.cases:
        lines.append(
            f'| {item.case_id} | {item.classification} | {item.baseline_score:.4f} '
            f'| {item.candidate_score:.4f} | {item.score_delta:+.4f} '
            f'| {item.baseline_status} | {item.candidate_status} |'
        )
    return '\n'.join(lines) + '\n'
