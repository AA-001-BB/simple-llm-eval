import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from simpleval.product_eval.evaluator import evaluate_case
from simpleval.product_eval.models import (
    CandidateOutput,
    EvaluatedCaseRecord,
    EvaluationCase,
    EvaluationRun,
    ReviewItem,
    RunSummary,
)

ModelType = TypeVar('ModelType', bound=BaseModel)


def _read_jsonl(path: Path, model_type: type[ModelType]) -> list[ModelType]:
    records: list[ModelType] = []
    with path.open(encoding='utf-8') as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                records.append(model_type.model_validate_json(line))
            except Exception as error:
                raise ValueError(f'Invalid record in {path} at line {line_number}: {error}') from error
    if not records:
        raise ValueError(f'No records found in {path}')
    return records


def _index_unique(records: list[BaseModel], path: Path) -> dict[str, BaseModel]:
    indexed: dict[str, BaseModel] = {}
    for record in records:
        case_id = record.case_id
        if case_id in indexed:
            raise ValueError(f'Duplicate case_id {case_id!r} in {path}')
        indexed[case_id] = record
    return indexed


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _render_markdown(run: EvaluationRun) -> str:
    lines = [
        '# 中文 AI 产品结构化输出评测报告',
        '',
        '本报告来自本地确定性评测，未执行模型 API 调用。',
        '',
        '## 运行信息',
        '',
        f'- 模型：`{run.model}`',
        f'- Prompt 版本：`{run.prompt_version}`',
        f'- 测试集 SHA-256：`{run.dataset_sha256}`',
        f'- 输出集 SHA-256：`{run.outputs_sha256}`',
        '',
        '## 结果汇总',
        '',
        '| 指标 | 数值 |',
        '| --- | ---: |',
        f'| 案例总数 | {run.summary.total} |',
        f'| 通过 | {run.summary.passed} |',
        f'| 失败 | {run.summary.failed} |',
        f'| 平均分 | {run.summary.mean_score:.4f} |',
        '',
        '## 失败案例',
        '',
    ]
    failed_records = [record for record in run.records if record.evaluation.status == 'failed']
    if not failed_records:
        lines.append('无。')
    else:
        lines.extend(['| Case ID | 任务类型 | 得分 | 失败类型 |', '| --- | --- | ---: | --- |'])
        for record in failed_records:
            codes = ', '.join(record.evaluation.failure_codes)
            lines.append(f'| {record.case.case_id} | {record.case.task_type} | {record.evaluation.overall_score:.4f} | {codes} |')
    return '\n'.join(lines) + '\n'


def run_evaluation(dataset_path: Path, outputs_path: Path, output_dir: Path) -> EvaluationRun:
    cases = _read_jsonl(dataset_path, EvaluationCase)
    outputs = _read_jsonl(outputs_path, CandidateOutput)
    cases_by_id = _index_unique(cases, dataset_path)
    outputs_by_id = _index_unique(outputs, outputs_path)

    if set(cases_by_id) != set(outputs_by_id):
        missing = sorted(set(cases_by_id) - set(outputs_by_id))
        extra = sorted(set(outputs_by_id) - set(cases_by_id))
        raise ValueError(f'Case IDs do not match: missing outputs={missing}, extra outputs={extra}')

    models = {output.model for output in outputs}
    prompt_versions = {output.prompt_version for output in outputs}
    if len(models) != 1 or len(prompt_versions) != 1:
        raise ValueError('Each output file must contain exactly one model and one prompt_version')

    records = []
    for case in cases:
        output = outputs_by_id[case.case_id]
        evaluation = evaluate_case(case, output.raw_output)
        records.append(EvaluatedCaseRecord(case=case, output=output, evaluation=evaluation))

    passed = sum(record.evaluation.status == 'passed' for record in records)
    failure_counts = Counter(code for record in records for code in record.evaluation.failure_codes)
    run = EvaluationRun(
        model=next(iter(models)),
        prompt_version=next(iter(prompt_versions)),
        dataset_sha256=_sha256(dataset_path),
        outputs_sha256=_sha256(outputs_path),
        summary=RunSummary(
            total=len(records),
            passed=passed,
            failed=len(records) - passed,
            mean_score=round(sum(record.evaluation.overall_score for record in records) / len(records), 4),
            failure_counts=dict(sorted(failure_counts.items())),
        ),
        records=records,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / 'run.json').write_text(run.model_dump_json(indent=2), encoding='utf-8')
    (output_dir / 'report.md').write_text(_render_markdown(run), encoding='utf-8')

    review_items = [
        ReviewItem(
            case_id=record.case.case_id,
            task_type=record.case.task_type,
            model=record.output.model,
            prompt_version=record.output.prompt_version,
            failure_codes=record.evaluation.failure_codes,
            failure_reasons=record.evaluation.failure_reasons,
            raw_output=record.output.raw_output,
        )
        for record in records
        if record.evaluation.status == 'failed'
    ]
    review_content = ''.join(json.dumps(item.model_dump(), ensure_ascii=False) + '\n' for item in review_items)
    (output_dir / 'review_queue.jsonl').write_text(review_content, encoding='utf-8')
    return run
