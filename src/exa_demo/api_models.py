from __future__ import annotations

import json
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
            title=optional_str(result.get("title")),
            url=optional_str(result.get("url")),
            published_date=optional_str(result.get("publishedDate")),
            author=optional_str(result.get("author")),
            highlights=[str(item) for item in result.get("highlights", []) if str(item).strip()],
            highlight_scores=float_list(result.get("highlightScores", [])),
            summary=optional_str(result.get("summary")),
            text=optional_str(result.get("text")),
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

        search = coalesce_float(cost, "search")
        neural_search = coalesce_float(cost, "neuralSearch", "neural_search")
        deep_search = coalesce_float(cost, "deepSearch", "deep_search")
        content_text = coalesce_float(cost, "contentsText", "contentText", "content_text")
        content_highlights = coalesce_float(
            cost, "contentsHighlights", "contentHighlights", "content_highlights", "contents"
        )
        content_summary = coalesce_float(
            cost, "contentsSummary", "contentSummary", "content_summary"
        )

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
            parsed = optional_float(value)
            if parsed is not None:
                other_costs[str(key)] = parsed

        total = optional_float(cost.get("total"))
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
            title=optional_str(citation.get("title") or citation.get("name")),
            url=optional_str(citation.get("url") or citation.get("sourceUrl")),
            snippet=optional_str(
                citation.get("snippet") or citation.get("text") or citation.get("passage")
            ),
            published_date=optional_str(
                citation.get("publishedDate") or citation.get("published_date")
            ),
            author=optional_str(citation.get("author")),
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
        citations = _citation_mappings(response_json)
        answer_text = None
        if isinstance(response_json, Mapping):
            answer_text = optional_str(
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
            request_hash=optional_str(getattr(meta, "request_hash", None)),
            request_payload=mapping_to_dict(getattr(meta, "request_payload", None)),
            request_id=optional_str(getattr(meta, "request_id", None)),
            created_at_utc=optional_str(getattr(meta, "created_at_utc", None)),
            estimated_cost_usd=float(getattr(meta, "estimated_cost_usd", 0.0) or 0.0),
            actual_cost_usd=optional_float(getattr(meta, "actual_cost_usd", None)),
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
class ResearchRecord:
    query: str
    cache_hit: bool
    request_hash: Optional[str]
    request_payload: Dict[str, Any]
    request_id: Optional[str]
    created_at_utc: Optional[str]
    estimated_cost_usd: float
    actual_cost_usd: Optional[float]
    report_text: Optional[str]
    report_preview: str
    citation_count: int
    top_citation_title: Optional[str]
    top_citation_url: Optional[str]
    citations: List[AnswerCitation] = field(default_factory=list)

    @classmethod
    def from_runtime(
        cls,
        query: str,
        response_json: Mapping[str, Any] | None,
        meta: Any,
    ) -> "ResearchRecord":
        citations = _citation_mappings(response_json)
        report_text = None
        if isinstance(response_json, Mapping):
            report_text = optional_str(
                response_json.get("report")
                or response_json.get("reportText")
                or response_json.get("markdown")
                or response_json.get("summary")
                or response_json.get("text")
                or response_json.get("response")
                or response_json.get("content")
            )

        parsed_citations = [AnswerCitation.from_api_citation(item) for item in citations]
        top_citation = parsed_citations[0] if parsed_citations else None

        return cls(
            query=query,
            cache_hit=bool(getattr(meta, "cache_hit", False)),
            request_hash=optional_str(getattr(meta, "request_hash", None)),
            request_payload=mapping_to_dict(getattr(meta, "request_payload", None)),
            request_id=optional_str(getattr(meta, "request_id", None)),
            created_at_utc=optional_str(getattr(meta, "created_at_utc", None)),
            estimated_cost_usd=float(getattr(meta, "estimated_cost_usd", 0.0) or 0.0),
            actual_cost_usd=optional_float(getattr(meta, "actual_cost_usd", None)),
            report_text=report_text,
            report_preview=(report_text or "")[:220],
            citation_count=len(parsed_citations),
            top_citation_title=top_citation.title if top_citation else None,
            top_citation_url=top_citation.url if top_citation else None,
            citations=parsed_citations,
        )

    def to_flat_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "cache_hit": self.cache_hit,
            "request_hash": self.request_hash,
            "request_id": self.request_id,
            "est_cost_usd": self.estimated_cost_usd,
            "actual_cost_usd": self.actual_cost_usd,
            "report_preview": self.report_preview,
            "citation_count": self.citation_count,
            "top_citation_title": self.top_citation_title,
            "top_citation_url": self.top_citation_url,
        }

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StructuredOutputField:
    path: str
    value: Any
    value_type: Optional[str] = None

    @classmethod
    def from_value(cls, path: str, value: Any) -> "StructuredOutputField":
        return cls(path=path, value=value, value_type=type(value).__name__)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StructuredOutputRecord:
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
    result_count: int
    structured_output: Dict[str, Any]
    structured_preview: str
    field_count: int
    top_field_path: Optional[str]
    top_field_value: Optional[str]
    fields: List[StructuredOutputField] = field(default_factory=list)
    results: List[ExaResult] = field(default_factory=list)
    cost_breakdown: CostBreakdown = field(default_factory=CostBreakdown)

    @classmethod
    def from_runtime(
        cls,
        query: str,
        response_json: Mapping[str, Any] | None,
        meta: Any,
    ) -> "StructuredOutputRecord":
        raw_results = _result_mappings(response_json)
        structured_output = structured_output_from_response(response_json)
        fields = flatten_structured_output(structured_output)
        top_field = fields[0] if fields else None
        top_result = raw_results[0] if raw_results else None

        return cls(
            query=query,
            cache_hit=bool(getattr(meta, "cache_hit", False)),
            request_hash=optional_str(getattr(meta, "request_hash", None)),
            request_payload=mapping_to_dict(getattr(meta, "request_payload", None)),
            request_id=optional_str(getattr(meta, "request_id", None)),
            resolved_search_type=optional_str(getattr(meta, "resolved_search_type", None)),
            created_at_utc=optional_str(getattr(meta, "created_at_utc", None)),
            estimated_cost_usd=float(getattr(meta, "estimated_cost_usd", 0.0) or 0.0),
            actual_cost_usd=optional_float(getattr(meta, "actual_cost_usd", None)),
            top_title=optional_str(top_result.get("title")) if top_result else None,
            top_url=optional_str(top_result.get("url")) if top_result else None,
            result_count=len(raw_results),
            structured_output=structured_output,
            structured_preview=preview_json(structured_output),
            field_count=len(fields),
            top_field_path=top_field.path if top_field else None,
            top_field_value=optional_str(top_field.value) if top_field else None,
            fields=fields,
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
            "result_count": self.result_count,
            "structured_preview": self.structured_preview,
            "field_count": self.field_count,
            "top_field_path": self.top_field_path,
            "top_field_value": self.top_field_value,
        }

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FindSimilarRecord:
    source_url: str
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
    result_count: int
    context: Optional[str]
    context_preview: str
    results: List[ExaResult] = field(default_factory=list)
    cost_breakdown: CostBreakdown = field(default_factory=CostBreakdown)

    @classmethod
    def from_runtime(
        cls,
        source_url: str,
        response_json: Mapping[str, Any] | None,
        meta: Any,
    ) -> "FindSimilarRecord":
        raw_results = _result_mappings(response_json)
        context = optional_str(response_json.get("context")) if isinstance(response_json, Mapping) else None
        top_result = raw_results[0] if raw_results else None

        return cls(
            source_url=source_url,
            cache_hit=bool(getattr(meta, "cache_hit", False)),
            request_hash=optional_str(getattr(meta, "request_hash", None)),
            request_payload=mapping_to_dict(getattr(meta, "request_payload", None)),
            request_id=optional_str(getattr(meta, "request_id", None)),
            resolved_search_type=optional_str(getattr(meta, "resolved_search_type", None)),
            created_at_utc=optional_str(getattr(meta, "created_at_utc", None)),
            estimated_cost_usd=float(getattr(meta, "estimated_cost_usd", 0.0) or 0.0),
            actual_cost_usd=optional_float(getattr(meta, "actual_cost_usd", None)),
            top_title=optional_str(top_result.get("title")) if top_result else None,
            top_url=optional_str(top_result.get("url")) if top_result else None,
            result_count=len(raw_results),
            context=context,
            context_preview=preview_text(context),
            results=[ExaResult.from_api_result(item) for item in raw_results],
            cost_breakdown=CostBreakdown.from_response(response_json),
        )

    def to_flat_dict(self) -> Dict[str, Any]:
        return {
            "source_url": self.source_url,
            "cache_hit": self.cache_hit,
            "request_hash": self.request_hash,
            "request_id": self.request_id,
            "resolved_search_type": self.resolved_search_type,
            "est_cost_usd": self.estimated_cost_usd,
            "actual_cost_usd": self.actual_cost_usd,
            "top_title": self.top_title,
            "top_url": self.top_url,
            "result_count": self.result_count,
            "context_preview": self.context_preview,
        }

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def optional_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def float_list(values: Any) -> List[float]:
    if not isinstance(values, list):
        return []
    result: List[float] = []
    for value in values:
        parsed = optional_float(value)
        if parsed is not None:
            result.append(parsed)
    return result


def string_list(values: Any) -> List[str]:
    if not isinstance(values, list):
        return []
    result: List[str] = []
    for value in values:
        text = optional_str(value)
        if text is not None:
            result.append(text)
    return result


def coalesce_float(mapping: Mapping[str, Any], *keys: str) -> float:
    for key in keys:
        parsed = optional_float(mapping.get(key))
        if parsed is not None:
            return parsed
    return 0.0


def mapping_to_dict(value: Any) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): value[key] for key in value}


def structured_output_from_response(response_json: Mapping[str, Any] | None) -> Dict[str, Any]:
    if not isinstance(response_json, Mapping):
        return {}

    for key in ("structuredOutput", "structured_output", "output", "structured", "data"):
        value = response_json.get(key)
        if isinstance(value, Mapping):
            return json_value_to_python(value)
        if isinstance(value, list):
            return json_value_to_python(value)

    return {}


def flatten_structured_output(
    value: Any, *, path: str = "structuredOutput"
) -> List[StructuredOutputField]:
    fields: List[StructuredOutputField] = []
    if isinstance(value, Mapping):
        if not value:
            return fields
        for key, item in value.items():
            next_path = f"{path}.{key}" if path else str(key)
            fields.extend(flatten_structured_output(item, path=next_path))
        return fields
    if isinstance(value, list):
        if not value:
            return fields
        for index, item in enumerate(value):
            next_path = f"{path}[{index}]"
            fields.extend(flatten_structured_output(item, path=next_path))
        return fields

    fields.append(StructuredOutputField.from_value(path, value))
    return fields


def json_value_to_python(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): json_value_to_python(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_value_to_python(item) for item in value]
    return value


def preview_json(value: Any, *, max_chars: int = 220) -> str:
    try:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        text = str(value)
    return text[:max_chars]


def preview_text(value: Any, *, max_chars: int = 220) -> str:
    text = optional_str(value) or ""
    return text[:max_chars]


def _citation_mappings(response_json: Mapping[str, Any] | None) -> List[Mapping[str, Any]]:
    if not isinstance(response_json, Mapping):
        return []
    citation_value = response_json.get("citations")
    if not isinstance(citation_value, list):
        citation_value = response_json.get("sources")
    if not isinstance(citation_value, list):
        citation_value = response_json.get("results")
    if not isinstance(citation_value, list):
        return []
    return [item for item in citation_value if isinstance(item, Mapping)]


def _result_mappings(response_json: Mapping[str, Any] | None) -> List[Mapping[str, Any]]:
    if not isinstance(response_json, Mapping):
        return []
    results_value = response_json.get("results")
    if not isinstance(results_value, list):
        return []
    return [item for item in results_value if isinstance(item, Mapping)]
