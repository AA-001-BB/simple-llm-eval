from typing import Any, Literal

from pydantic import BaseModel, Field


class EvaluationCase(BaseModel):
    case_id: str
    task_type: str
    instruction: str
    expected_action: Literal['answer', 'refuse']
    expected_output: dict[str, Any]
    json_schema: dict[str, Any]
    required_terms: list[str] = Field(default_factory=list)
    forbidden_terms: list[str] = Field(default_factory=list)


class CheckResult(BaseModel):
    passed: bool
    score: float = Field(ge=0.0, le=1.0)


class CaseEvaluation(BaseModel):
    case_id: str
    status: Literal['passed', 'failed']
    overall_score: float = Field(ge=0.0, le=1.0)
    checks: dict[str, CheckResult]
    failure_codes: list[str]
    failure_reasons: list[str]
    parsed_output: dict[str, Any] | None


class CandidateOutput(BaseModel):
    case_id: str
    model: str
    prompt_version: str
    raw_output: str


class EvaluatedCaseRecord(BaseModel):
    case: EvaluationCase
    output: CandidateOutput
    evaluation: CaseEvaluation


class RunSummary(BaseModel):
    total: int
    passed: int
    failed: int
    mean_score: float
    failure_counts: dict[str, int]


class EvaluationRun(BaseModel):
    schema_version: int = 1
    model: str
    prompt_version: str
    dataset_sha256: str
    outputs_sha256: str
    summary: RunSummary
    records: list[EvaluatedCaseRecord]


class ReviewItem(BaseModel):
    case_id: str
    task_type: str
    model: str
    prompt_version: str
    failure_codes: list[str]
    failure_reasons: list[str]
    raw_output: str
    review_status: Literal['pending', 'reviewed'] = 'pending'
    reviewer_decision: str | None = None
    reviewer_notes: str | None = None


class ComparisonRunMetadata(BaseModel):
    model: str
    prompt_version: str


class CaseComparison(BaseModel):
    case_id: str
    classification: Literal['improved', 'regressed', 'unchanged']
    baseline_score: float
    candidate_score: float
    score_delta: float
    baseline_status: Literal['passed', 'failed']
    candidate_status: Literal['passed', 'failed']
    baseline_failure_codes: list[str]
    candidate_failure_codes: list[str]


class ComparisonSummary(BaseModel):
    total: int
    improved: int
    regressed: int
    unchanged: int


class EvaluationComparison(BaseModel):
    baseline: ComparisonRunMetadata
    candidate: ComparisonRunMetadata
    summary: ComparisonSummary
    cases: list[CaseComparison]
