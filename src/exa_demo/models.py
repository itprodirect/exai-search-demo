from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Mapping, Optional

from .api_models import (
    AnswerCitation,
    AnswerRecord,
    CostBreakdown,
    ExaResult,
    FindSimilarRecord,
    ResearchRecord,
    StructuredOutputField,
    StructuredOutputRecord,
    mapping_to_dict as _mapping_to_dict,
    optional_float as _optional_float,
    optional_str as _optional_str,
    string_list as _string_list,
)

__all__ = [
    "AnswerCitation",
    "AnswerRecord",
    "CostBreakdown",
    "ExaResult",
    "ExperimentSummaryRecord",
    "FindSimilarRecord",
    "QueryEvaluationRecord",
    "ResearchRecord",
    "StructuredOutputField",
    "StructuredOutputRecord",
]


@dataclass(frozen=True)
class QueryEvaluationRecord:
    query: str
    cache_hit: bool
    request_hash: Optional[str]
    request_payload: Dict[str, Any]
    request_id: Optional[str]
    resolved_search_type: Optional[str]
    created_at_utc: Optional[str]
    estimated_cost_usd: float
    actual_cost_usd: Optional[float]
    top_title: Optional[str]
    top_url: Optional[str]
    top_preview: str
    linkedin_present: bool
    relevance_keywords_present: bool
    result_count: int
    relevance_score: float = 0.0
    credibility_score: float = 0.0
    actionability_score: float = 0.0
    confidence_score: float = 0.0
    failure_reasons: List[str] = field(default_factory=list)
    primary_failure_reason: Optional[str] = None
    results: List[ExaResult] = field(default_factory=list)
    cost_breakdown: CostBreakdown = field(default_factory=CostBreakdown)

    @classmethod
    def from_runtime(
        cls,
        query: str,
        response_json: Mapping[str, Any] | None,
        meta: Any,
        evaluated: Mapping[str, Any],
    ) -> "QueryEvaluationRecord":
        raw_results = []
        if isinstance(response_json, Mapping):
            results_value = response_json.get("results")
            if isinstance(results_value, list):
                raw_results = [item for item in results_value if isinstance(item, Mapping)]

        failure_reasons = _string_list(evaluated.get("failure_reasons"))
        primary_failure_reason = _optional_str(evaluated.get("primary_failure_reason"))
        if primary_failure_reason is None and failure_reasons:
            primary_failure_reason = failure_reasons[0]

        return cls(
            query=query,
            cache_hit=bool(getattr(meta, "cache_hit", False)),
            request_hash=_optional_str(getattr(meta, "request_hash", None)),
            request_payload=_mapping_to_dict(getattr(meta, "request_payload", None)),
            request_id=_optional_str(getattr(meta, "request_id", None)),
            resolved_search_type=_optional_str(getattr(meta, "resolved_search_type", None)),
            created_at_utc=_optional_str(getattr(meta, "created_at_utc", None)),
            estimated_cost_usd=float(getattr(meta, "estimated_cost_usd", 0.0) or 0.0),
            actual_cost_usd=_optional_float(getattr(meta, "actual_cost_usd", None)),
            top_title=_optional_str(evaluated.get("top_title")),
            top_url=_optional_str(evaluated.get("top_url")),
            top_preview=str(evaluated.get("top_preview") or ""),
            linkedin_present=bool(evaluated.get("linkedin_present", False)),
            relevance_keywords_present=bool(evaluated.get("relevance_keywords_present", False)),
            result_count=int(evaluated.get("result_count") or len(raw_results)),
            relevance_score=float(evaluated.get("relevance_score") or 0.0),
            credibility_score=float(evaluated.get("credibility_score") or 0.0),
            actionability_score=float(evaluated.get("actionability_score") or 0.0),
            confidence_score=float(evaluated.get("confidence_score") or 0.0),
            failure_reasons=failure_reasons,
            primary_failure_reason=primary_failure_reason,
            results=[ExaResult.from_api_result(item) for item in raw_results],
            cost_breakdown=CostBreakdown.from_response(response_json),
        )

    def to_flat_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "cache_hit": self.cache_hit,
            "request_hash": self.request_hash,
            "request_id": self.request_id,
            "resolved_search_type": self.resolved_search_type,
            "est_cost_usd": self.estimated_cost_usd,
            "actual_cost_usd": self.actual_cost_usd,
            "top_title": self.top_title,
            "top_url": self.top_url,
            "top_preview": self.top_preview,
            "linkedin_present": self.linkedin_present,
            "relevance_keywords_present": self.relevance_keywords_present,
            "result_count": self.result_count,
            "relevance_score": self.relevance_score,
            "credibility_score": self.credibility_score,
            "actionability_score": self.actionability_score,
            "confidence_score": self.confidence_score,
            "failure_reasons": list(self.failure_reasons),
            "primary_failure_reason": self.primary_failure_reason,
        }

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExperimentSummaryRecord:
    run_id: str
    generated_at_utc: str
    batch_query_count: int
    request_count: int
    cache_hits: int
    uncached_calls: int
    spent_usd: float
    avg_cost_per_uncached_query: float
    projection_basis: Optional[str] = None
    unit_cost_usd: Optional[float] = None
    projected_100_queries_usd: Optional[float] = None
    projected_1000_queries_usd: Optional[float] = None
    projected_10000_queries_usd: Optional[float] = None
    headline_recommendation: Optional[str] = None
    observed_relevance_rate: Optional[float] = None
    observed_linkedin_rate: Optional[float] = None
    observed_credibility_rate: Optional[float] = None
    observed_actionability_rate: Optional[float] = None
    observed_confidence_score: Optional[float] = None
    observed_failure_rate: Optional[float] = None
    budget_cap_usd: Optional[float] = None
    qualitative_notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
