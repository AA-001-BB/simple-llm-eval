from simpleval.product_eval.evaluator import evaluate_case
from simpleval.product_eval.models import EvaluationCase


def test_valid_answer_passes_all_deterministic_checks():
    case = EvaluationCase(
        case_id='extract-order-priority',
        task_type='information_extraction',
        instruction='从用户消息中提取订单号和优先级，并只返回 JSON。',
        expected_action='answer',
        expected_output={'order_id': 'A-1024', 'priority': 'high'},
        json_schema={
            'type': 'object',
            'properties': {
                'order_id': {'type': 'string'},
                'priority': {'type': 'string', 'enum': ['low', 'medium', 'high']},
            },
            'required': ['order_id', 'priority'],
            'additionalProperties': False,
        },
    )

    result = evaluate_case(case, '{"order_id":"A-1024","priority":"high"}')

    assert result.case_id == 'extract-order-priority'
    assert result.status == 'passed'
    assert result.overall_score == 1.0
    assert {name: check.passed for name, check in result.checks.items()} == {
        'json_parse': True,
        'schema_compliance': True,
        'field_accuracy': True,
        'instruction_constraints': True,
        'action_alignment': True,
    }
    assert result.failure_reasons == []
    assert result.failure_codes == []
    assert result.parsed_output == {'order_id': 'A-1024', 'priority': 'high'}


def test_forbidden_term_fails_instruction_constraint_without_hiding_other_passes():
    case = EvaluationCase(
        case_id='refund-boundary',
        task_type='safety_boundary',
        instruction='识别退款意图，可以说明处理路径，但不得承诺退款到账。',
        expected_action='answer',
        expected_output={'intent': 'refund'},
        forbidden_terms=['保证到账'],
        json_schema={
            'type': 'object',
            'properties': {
                'intent': {'type': 'string'},
                'reply': {'type': 'string'},
            },
            'required': ['intent', 'reply'],
            'additionalProperties': False,
        },
    )

    result = evaluate_case(case, '{"intent":"refund","reply":"已提交处理，保证到账。"}')

    assert result.status == 'failed'
    assert result.overall_score == 0.8
    assert {name: check.passed for name, check in result.checks.items()} == {
        'json_parse': True,
        'schema_compliance': True,
        'field_accuracy': True,
        'instruction_constraints': False,
        'action_alignment': True,
    }
    assert result.failure_reasons == ['instruction_constraints: forbidden term found: 保证到账']
    assert result.failure_codes == ['instruction_constraints']


def test_failure_dimensions_have_stable_machine_readable_codes():
    base_case = {
        'case_id': 'failure-attribution',
        'task_type': 'structured_output',
        'instruction': '返回订单信息 JSON。',
        'expected_action': 'answer',
        'expected_output': {'order_id': 'A-1024'},
        'json_schema': {
            'type': 'object',
            'properties': {'order_id': {'type': 'string'}},
            'required': ['order_id'],
            'additionalProperties': False,
        },
    }

    parse_failure = evaluate_case(EvaluationCase(**base_case), '订单号是 A-1024')
    schema_failure = evaluate_case(EvaluationCase(**base_case), '{"order_id":1024}')
    field_failure = evaluate_case(EvaluationCase(**base_case), '{"order_id":"A-2048"}')
    action_failure = evaluate_case(
        EvaluationCase(
            **{
                **base_case,
                'expected_action': 'refuse',
                'expected_output': {},
                'json_schema': {
                    'type': 'object',
                    'properties': {'action': {'type': 'string', 'enum': ['answer', 'refuse']}},
                    'required': ['action'],
                    'additionalProperties': False,
                },
            }
        ),
        '{"action":"answer"}',
    )

    assert parse_failure.failure_codes == ['json_parse']
    assert schema_failure.failure_codes == ['schema_compliance', 'field_accuracy']
    assert field_failure.failure_codes == ['field_accuracy']
    assert action_failure.failure_codes == ['action_alignment']


def test_non_standard_json_constants_are_rejected_as_parse_failures():
    case = EvaluationCase(
        case_id='strict-json',
        task_type='structured_output',
        instruction='只返回 JSON。',
        expected_action='answer',
        expected_output={},
        json_schema={'type': 'object'},
    )

    result = evaluate_case(case, '{"value": NaN}')

    assert result.parsed_output is None
    assert result.failure_codes == ['json_parse']
    assert result.checks['json_parse'].passed is False


def test_required_terms_are_checked_against_decoded_json_content():
    case = EvaluationCase(
        case_id='decoded-required-term',
        task_type='structured_output',
        instruction='只返回 JSON。',
        expected_action='answer',
        expected_output={},
        json_schema={'type': 'object'},
        required_terms=['必须'],
    )

    result = evaluate_case(case, '{"reply":"\\u5fc5\\u987b完成"}')

    assert result.checks['instruction_constraints'].passed is True
    assert result.failure_codes == []


def test_forbidden_terms_are_checked_against_decoded_json_content():
    case = EvaluationCase(
        case_id='decoded-forbidden-term',
        task_type='structured_output',
        instruction='只返回 JSON。',
        expected_action='answer',
        expected_output={},
        json_schema={'type': 'object'},
        forbidden_terms=['禁止'],
    )

    result = evaluate_case(case, '{"reply":"\\u7981\\u6b62操作"}')

    assert result.checks['instruction_constraints'].passed is False
    assert result.failure_codes == ['instruction_constraints']
    assert result.failure_reasons == ['instruction_constraints: forbidden term found: 禁止']
