from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Mapping, Optional


@dataclass(frozen=True)
class ExaResult:
    title: Optional[str]
    url: Optional[str]
    published_date: Optional[str] = None
    author: Optional[str] = None
    highlights: List[str] = field(default_factory=list)
    highlight_scores: List[float] = field(default_factory=list)
    summary: Optional[str] = None
    text: Optional[str] = None

    @classmethod
    def from_api_result(cls, result: Mapping[str, Any]) -> "ExaResult":
        return cls(
            title=_optional_str(result.get("title")),
            url=_optional_str(result.get("url")),
            published_date=_optional_str(result.get("publishedDate")),
            author=_optional_str(result.get("author")),
            highlights=[str(item) for item in result.get("highlights", []) if str(item).strip()],
            highlight_scores=_float_list(result.get("highlightScores", [])),
            summary=_optional_str(result.get("summary")),
            text=_optional_str(result.get("text")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CostBreakdown:
    total: float = 0.0
    search: float = 0.0
    neural_search: float = 0.0
    deep_search: float = 0.0
    content_text: float = 0.0
    content_highlights: float = 0.0
    content_summary: float = 0.0
    other_costs: Dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_response(cls, response_json: Mapping[str, Any] | None) -> "CostBreakdown":
        if not isinstance(response_json, Mapping):
            return cls()

        cost = response_json.get("costDollars")
        if not isinstance(cost, Mapping):
            return cls()

        search = _coalesce_float(cost, "search")
        neural_search = _coalesce_float(cost, "neuralSearch", "neural_search")
        deep_search = _coalesce_float(cost, "deepSearch", "deep_search")
        content_text = _coalesce_float(cost, "contentsText", "contentText", "content_text")
        content_highlights = _coalesce_float(cost, "contentsHighlights", "contentHighlights", "content_highlights", "contents")
        content_summary = _coalesce_float(cost, "contentsSummary", "contentSummary", "content_summary")

        known_keys = {
            "total",
            "search",
            "neuralSearch",
            "neural_search",
            "deepSearch",
            "deep_search",
            "contentsText",
            "contentText",
            "content_text",
            "contentsHighlights",
            "contentHighlights",
            "content_highlights",
            "contents",
            "contentsSummary",
            "contentSummary",
            "content_summary",
        }
        other_costs: Dict[str, float] = {}
        for key, value in cost.items():
            if key in known_keys:
                continue
            parsed = _optional_float(value)
            if parsed is not None:
                other_costs[str(key)] = parsed

        total = _optional_float(cost.get("total"))
        if total is None:
            total = round(
                search
                + neural_search
                + deep_search
                + content_text
                + content_highlights
                + content_summary
                + sum(other_costs.values()),
                6,
            )

        return cls(
            total=float(total),
            search=search,
            neural_search=neural_search,
            deep_search=deep_search,
            content_text=content_text,
            content_highlights=content_highlights,
            content_summary=content_summary,
            other_costs=other_costs,
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AnswerCitation:
    title: Optional[str]
    url: Optional[str]
    snippet: Optional[str] = None
    published_date: Optional[str] = None
    author: Optional[str] = None

    @classmethod
    def from_api_citation(cls, citation: Mapping[str, Any]) -> "AnswerCitation":
        return cls(
            title=_optional_str(citation.get("title") or citation.get("name")),
            url=_optional_str(citation.get("url") or citation.get("sourceUrl")),
            snippet=_optional_str(citation.get("snippet") or citation.get("text") or citation.get("passage")),
            published_date=_optional_str(citation.get("publishedDate") or citation.get("published_date")),
            author=_optional_str(citation.get("author")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AnswerRecord:
    question: str
    cache_hit: bool
    request_hash: Optional[str]
    request_payload: Dict[str, Any]
    request_id: Optional[str]
    created_at_utc: Optional[str]
    estimated_cost_usd: float
    actual_cost_usd: Optional[float]
    answer: Optional[str]
    answer_preview: str
    citation_count: int
    top_citation_title: Optional[str]
    top_citation_url: Optional[str]
    citations: List[AnswerCitation] = field(default_factory=list)

    @classmethod
    def from_runtime(
        cls,
        question: str,
        response_json: Mapping[str, Any] | None,
        meta: Any,
    ) -> "AnswerRecord":
        citations: List[Mapping[str, Any]] = []
        if isinstance(response_json, Mapping):
            citation_value = response_json.get("citations")
            if not isinstance(citation_value, list):
                citation_value = response_json.get("sources")
            if not isinstance(citation_value, list):
                citation_value = response_json.get("results")
            if isinstance(citation_value, list):
                citations = [item for item in citation_value if isinstance(item, Mapping)]

        answer_text = None
        if isinstance(response_json, Mapping):
            answer_text = _optional_str(
                response_json.get("answer")
                or response_json.get("text")
                or response_json.get("response")
                or response_json.get("content")
            )

        parsed_citations = [AnswerCitation.from_api_citation(item) for item in citations]
        top_citation = parsed_citations[0] if parsed_citations else None

        return cls(
            question=question,
            cache_hit=bool(getattr(meta, "cache_hit", False)),
            request_hash=_optional_str(getattr(meta, "request_hash", None)),
            request_payload=_mapping_to_dict(getattr(meta, "request_payload", None)),
            request_id=_optional_str(getattr(meta, "request_id", None)),
            created_at_utc=_optional_str(getattr(meta, "created_at_utc", None)),
            estimated_cost_usd=float(getattr(meta, "estimated_cost_usd", 0.0) or 0.0),
            actual_cost_usd=_optional_float(getattr(meta, "actual_cost_usd", None)),
            answer=answer_text,
            answer_preview=(answer_text or "")[:220],
            citation_count=len(parsed_citations),
            top_citation_title=top_citation.title if top_citation else None,
            top_citation_url=top_citation.url if top_citation else None,
            citations=parsed_citations,
        )

    def to_flat_dict(self) -> Dict[str, Any]:
        return {
            "question": self.question,
            "cache_hit": self.cache_hit,
            "request_hash": self.request_hash,
            "request_id": self.request_id,
            "est_cost_usd": self.estimated_cost_usd,
            "actual_cost_usd": self.actual_cost_usd,
            "answer_preview": self.answer_preview,
            "citation_count": self.citation_count,
            "top_citation_title": self.top_citation_title,
            "top_citation_url": self.top_citation_url,
        }

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


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


def _optional_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _float_list(values: Any) -> List[float]:
    if not isinstance(values, list):
        return []
    result: List[float] = []
    for value in values:
        parsed = _optional_float(value)
        if parsed is not None:
            result.append(parsed)
    return result


def _string_list(values: Any) -> List[str]:
    if not isinstance(values, list):
        return []
    result: List[str] = []
    for value in values:
        text = _optional_str(value)
        if text is not None:
            result.append(text)
    return result


def _coalesce_float(mapping: Mapping[str, Any], *keys: str) -> float:
    for key in keys:
        parsed = _optional_float(mapping.get(key))
        if parsed is not None:
            return parsed
    return 0.0


def _mapping_to_dict(value: Any) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): value[key] for key in value}
