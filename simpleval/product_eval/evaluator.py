import json
from typing import Any

from jsonschema import Draft202012Validator

from simpleval.product_eval.models import CaseEvaluation, CheckResult, EvaluationCase


def _matches_expected(expected: Any, candidate: Any) -> bool:
    if isinstance(expected, dict):
        return isinstance(candidate, dict) and all(
            key in candidate and _matches_expected(value, candidate[key]) for key, value in expected.items()
        )
    return expected == candidate


def _reject_json_constant(value: str) -> None:
    raise ValueError(f'non-standard JSON constant: {value}')


def _parse_output(raw_output: str) -> tuple[dict[str, Any] | None, bool, list[str], list[str]]:
    failure_codes: list[str] = []
    failure_reasons: list[str] = []
    try:
        candidate = json.loads(raw_output, parse_constant=_reject_json_constant)
        if not isinstance(candidate, dict):
            raise TypeError('top-level JSON value must be an object')
        return candidate, True, failure_codes, failure_reasons
    except (json.JSONDecodeError, TypeError, ValueError) as error:
        failure_codes.append('json_parse')
        failure_reasons.append(f'json_parse: {error}')
        return None, False, failure_codes, failure_reasons


def _evaluate_schema_and_fields(case: EvaluationCase, parsed_output: dict[str, Any]) -> tuple[bool, bool, list[str], list[str]]:
    failure_codes: list[str] = []
    failure_reasons: list[str] = []
    schema_errors = list(Draft202012Validator(case.json_schema).iter_errors(parsed_output))
    schema_passed = not schema_errors
    if schema_errors:
        failure_codes.append('schema_compliance')
        failure_reasons.append(f'schema_compliance: {schema_errors[0].message}')

    fields_passed = _matches_expected(case.expected_output, parsed_output)
    if not fields_passed:
        failure_codes.append('field_accuracy')
        failure_reasons.append('field_accuracy: output does not match the expected fields')
    return schema_passed, fields_passed, failure_codes, failure_reasons


def _evaluate_constraints(case: EvaluationCase, parsed_output: dict[str, Any]) -> tuple[bool, list[str], list[str]]:
    failure_codes: list[str] = []
    failure_reasons: list[str] = []
    decoded_content = json.dumps(parsed_output, ensure_ascii=False)
    missing_terms = [term for term in case.required_terms if term not in decoded_content]
    forbidden_terms = [term for term in case.forbidden_terms if term in decoded_content]
    constraints_passed = not missing_terms and not forbidden_terms
    if missing_terms:
        failure_codes.append('instruction_constraints')
        failure_reasons.append(f'instruction_constraints: required term missing: {missing_terms[0]}')
    if forbidden_terms:
        if 'instruction_constraints' not in failure_codes:
            failure_codes.append('instruction_constraints')
        failure_reasons.append(f'instruction_constraints: forbidden term found: {forbidden_terms[0]}')
    return constraints_passed, failure_codes, failure_reasons


def _evaluate_action(case: EvaluationCase, parsed_output: dict[str, Any]) -> tuple[bool, list[str], list[str]]:
    actual_action = parsed_output.get('action', 'answer')
    action_passed = actual_action == case.expected_action
    if action_passed:
        return True, [], []
    return (
        False,
        ['action_alignment'],
        [f'action_alignment: expected {case.expected_action}, got {actual_action}'],
    )


def evaluate_case(case: EvaluationCase, raw_output: str) -> CaseEvaluation:
    parsed_output, parse_passed, failure_codes, failure_reasons = _parse_output(raw_output)
    schema_passed = False
    fields_passed = False
    constraints_passed = False
    action_passed = False
    if parsed_output is not None:
        schema_passed, fields_passed, schema_codes, schema_reasons = _evaluate_schema_and_fields(case, parsed_output)
        constraints_passed, constraint_codes, constraint_reasons = _evaluate_constraints(case, parsed_output)
        action_passed, action_codes, action_reasons = _evaluate_action(case, parsed_output)
        failure_codes.extend(schema_codes + constraint_codes + action_codes)
        failure_reasons.extend(schema_reasons + constraint_reasons + action_reasons)

    checks = {
        'json_parse': CheckResult(passed=parse_passed, score=float(parse_passed)),
        'schema_compliance': CheckResult(passed=schema_passed, score=float(schema_passed)),
        'field_accuracy': CheckResult(passed=fields_passed, score=float(fields_passed)),
        'instruction_constraints': CheckResult(passed=constraints_passed, score=float(constraints_passed)),
        'action_alignment': CheckResult(passed=action_passed, score=float(action_passed)),
    }
    overall_score = sum(check.score for check in checks.values()) / len(checks)

    return CaseEvaluation(
        case_id=case.case_id,
        status='passed' if all(check.passed for check in checks.values()) else 'failed',
        overall_score=overall_score,
        checks=checks,
        failure_codes=failure_codes,
        failure_reasons=failure_reasons,
        parsed_output=parsed_output,
    )
