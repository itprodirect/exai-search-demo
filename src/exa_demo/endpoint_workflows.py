from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping

import pandas as pd

from .artifacts import ExperimentArtifactWriter
from .cache import SqliteCacheStore
from .client import exa_research
from .cost_model import estimate_cost_from_pricing
from .models import ResearchRecord
from .reporting import render_research_markdown
from .workflows import (
    answer_http_call,
    build_answer_artifact,
    build_answer_request_payload,
    build_find_similar_artifact,
    build_find_similar_request_payload,
    build_research_artifact,
    build_structured_search_artifact,
    build_structured_search_request_payload,
    find_similar_http_call,
    load_json_schema,
    structured_search_http_call,
)


def run_answer_workflow(
    *,
    query: str,
    artifact_dir: str,
    config: Dict[str, Any],
    pricing: Dict[str, float],
    runtime: Any,
    runtime_metadata: Mapping[str, Any],
) -> Dict[str, Any]:
    cache_store = _cache_store(config)
    request_payload = build_answer_request_payload(query)
    estimated_cost = estimate_cost_from_pricing(
        {"type": "auto"},
        1,
        pricing,
        int(config["max_supported_results_for_estimate"]),
    )

    response_json, cache_hit = cache_store.get_or_set(
        request_payload,
        estimated_cost,
        run_id=runtime.run_id,
        budget_cap_usd=float(config["budget_cap_usd"]),
        fetcher=lambda payload: answer_http_call(
            payload,
            exa_api_key=runtime.exa_api_key,
            smoke_no_network=runtime.smoke_no_network,
        ),
    )

    answer_payload = build_answer_artifact(
        query,
        request_payload=request_payload,
        response_json=response_json,
        cache_hit=cache_hit,
        estimated_cost_usd=estimated_cost,
    )
    summary = cache_store.spend_so_far(run_id=runtime.run_id)
    writer = ExperimentArtifactWriter(
        run_id=runtime.run_id,
        config=config,
        pricing=pricing,
        run_context={"workflow": "answer"},
        runtime_metadata=dict(runtime_metadata),
        base_dir=artifact_dir,
    )
    writer.write_json_artifact("answer.json", answer_payload)
    writer.write_summary(
        summary,
        projections=_summary_projections(summary),
        recommendation_data={
            "headline_recommendation": "Use for cited-answer workflows with human review"
        },
        qualitative_notes=[
            "Answer workflow active: answer text and citations are stored in answer.json.",
            "Smoke mode active: answers are mocked and costs are zero.",
        ]
        if runtime.smoke_no_network
        else [
            "Answer workflow active: answer text and citations are stored in answer.json.",
        ],
        extra={
            "workflow": "answer",
            "answer": {
                "query": query,
                "cache_hit": cache_hit,
                "citation_count": answer_payload["citation_count"],
                "answer_length": len(answer_payload["answer_text"]),
            },
        },
    )

    return {
        "workflow": "answer",
        "run_id": runtime.run_id,
        "artifact_dir": str(writer.artifact_dir),
        "answer": answer_payload["answer_text"],
        "citations": answer_payload["citations"],
        "citation_count": answer_payload["citation_count"],
        "cache_hit": cache_hit,
        "request_id": answer_payload.get("request_id"),
        "summary": summary,
    }


def emit_answer_payload(payload: Mapping[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2))
        return

    print(f"run_id: {payload['run_id']}")
    print(f"artifact_dir: {payload['artifact_dir']}")
    print(f"cache_hit: {payload['cache_hit']}")
    print(f"citation_count: {payload['citation_count']}")
    print("")
    print(payload["answer"])
    citations = payload.get("citations")
    if isinstance(citations, list) and citations:
        print("")
        print(pd.DataFrame(citations).to_markdown(index=False))


def run_research_workflow(
    *,
    query: str,
    artifact_dir: str,
    config: Dict[str, Any],
    pricing: Dict[str, float],
    runtime: Any,
    runtime_metadata: Mapping[str, Any],
) -> Dict[str, Any]:
    cache_store = _cache_store(config)
    response_json, meta = exa_research(
        query,
        config=config,
        pricing=pricing,
        exa_api_key=runtime.exa_api_key,
        smoke_no_network=runtime.smoke_no_network,
        run_id=runtime.run_id,
        cache_store=cache_store,
    )
    record = ResearchRecord.from_runtime(query, response_json, meta)
    research_payload = build_research_artifact(
        query,
        request_payload=meta.request_payload,
        response_json=response_json,
        cache_hit=meta.cache_hit,
        estimated_cost_usd=meta.estimated_cost_usd,
    )

    summary = cache_store.spend_so_far(run_id=runtime.run_id)
    writer = ExperimentArtifactWriter(
        run_id=runtime.run_id,
        config=config,
        pricing=pricing,
        run_context={"workflow": "research"},
        runtime_metadata=dict(runtime_metadata),
        base_dir=artifact_dir,
    )
    writer.write_json_artifact("research.json", research_payload)
    writer.write_text_artifact(
        "research.md",
        render_research_markdown(
            query=query,
            report_text=record.report_text or "",
            citations=[citation.to_dict() for citation in record.citations],
        ),
        kind="markdown",
    )
    writer.write_summary(
        summary,
        projections=_summary_projections(summary),
        recommendation_data={
            "headline_recommendation": "Use for research-style report generation with human review"
        },
        qualitative_notes=[
            "Research workflow active: the response payload is stored in research.json.",
            "Smoke mode active: research reports are mocked and costs are zero.",
        ]
        if runtime.smoke_no_network
        else [
            "Research workflow active: the response payload is stored in research.json.",
        ],
        extra={
            "workflow": "research",
            "research": {
                "query": query,
                "cache_hit": record.cache_hit,
                "citation_count": record.citation_count,
                "report_length": len(record.report_text or ""),
            },
        },
    )

    return {
        "workflow": "research",
        "run_id": runtime.run_id,
        "artifact_dir": str(writer.artifact_dir),
        "query": query,
        "report": record.report_text,
        "report_preview": record.report_preview,
        "citations": [citation.to_dict() for citation in record.citations],
        "citation_count": record.citation_count,
        "cache_hit": record.cache_hit,
        "request_id": record.request_id,
        "summary": summary,
    }


def emit_research_payload(payload: Mapping[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2))
        return

    print(f"run_id: {payload['run_id']}")
    print(f"artifact_dir: {payload['artifact_dir']}")
    print(f"cache_hit: {payload['cache_hit']}")
    print(f"citation_count: {payload['citation_count']}")
    print("")
    print(payload.get("report") or "")
    citations = payload.get("citations")
    if isinstance(citations, list) and citations:
        print("")
        print(pd.DataFrame(citations).to_markdown(index=False))


def run_find_similar_workflow(
    *,
    seed_url: str,
    artifact_dir: str,
    config: Dict[str, Any],
    pricing: Dict[str, float],
    runtime: Any,
    runtime_metadata: Mapping[str, Any],
) -> Dict[str, Any]:
    cache_store = _cache_store(config)
    request_payload = build_find_similar_request_payload(seed_url, config)
    estimated_cost = estimate_cost_from_pricing(
        request_payload,
        int(request_payload.get("numResults") or config["num_results"]),
        pricing,
        int(config["max_supported_results_for_estimate"]),
    )

    response_json, cache_hit = cache_store.get_or_set(
        request_payload,
        estimated_cost,
        run_id=runtime.run_id,
        budget_cap_usd=float(config["budget_cap_usd"]),
        fetcher=lambda payload: find_similar_http_call(
            payload,
            exa_api_key=runtime.exa_api_key,
            smoke_no_network=runtime.smoke_no_network,
            config=config,
        ),
    )

    find_similar_payload = build_find_similar_artifact(
        seed_url,
        request_payload=request_payload,
        response_json=response_json,
        cache_hit=cache_hit,
        estimated_cost_usd=estimated_cost,
    )
    summary = cache_store.spend_so_far(run_id=runtime.run_id)
    writer = ExperimentArtifactWriter(
        run_id=runtime.run_id,
        config=config,
        pricing=pricing,
        run_context={"workflow": "find-similar"},
        runtime_metadata=dict(runtime_metadata),
        base_dir=artifact_dir,
    )
    writer.write_json_artifact("find_similar.json", find_similar_payload)
    writer.write_summary(
        summary,
        projections=_summary_projections(summary),
        recommendation_data={
            "headline_recommendation": "Use for seed-url discovery workflows"
        },
        qualitative_notes=[
            "Find-similar workflow active: the response payload is stored in find_similar.json.",
            "Smoke mode active: similar-page results are mocked and costs are zero.",
        ]
        if runtime.smoke_no_network
        else [
            "Find-similar workflow active: the response payload is stored in find_similar.json.",
        ],
        extra={
            "workflow": "find-similar",
            "find_similar": {
                "seed_url": seed_url,
                "cache_hit": cache_hit,
                "result_count": find_similar_payload["result_count"],
                "top_result_title": (
                    find_similar_payload["top_result"]["title"]
                    if find_similar_payload["top_result"]
                    else None
                ),
            },
        },
    )

    return {
        "workflow": "find-similar",
        "run_id": runtime.run_id,
        "artifact_dir": str(writer.artifact_dir),
        "seed_url": seed_url,
        "cache_hit": cache_hit,
        "request_id": find_similar_payload.get("request_id"),
        "result_count": find_similar_payload["result_count"],
        "top_result": find_similar_payload.get("top_result"),
        "results": find_similar_payload.get("results"),
        "summary": summary,
    }


def emit_find_similar_payload(payload: Mapping[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2))
        return

    print(f"run_id: {payload['run_id']}")
    print(f"artifact_dir: {payload['artifact_dir']}")
    print(f"seed_url: {payload['seed_url']}")
    print(f"cache_hit: {payload['cache_hit']}")
    print(f"result_count: {payload['result_count']}")
    print(f"request_id: {payload.get('request_id')}")
    top_result = payload.get("top_result")
    if isinstance(top_result, Mapping):
        print("top_result:")
        print(json.dumps(dict(top_result), indent=2, sort_keys=True))


def run_structured_search_workflow(
    *,
    query: str,
    schema_file: str,
    artifact_dir: str,
    config: Dict[str, Any],
    pricing: Dict[str, float],
    runtime: Any,
    runtime_metadata: Mapping[str, Any],
) -> Dict[str, Any]:
    cache_store = _cache_store(config)
    schema_path = Path(schema_file)
    output_schema = load_json_schema(schema_path)
    request_payload = build_structured_search_request_payload(query, config, output_schema)
    estimated_cost = estimate_cost_from_pricing(
        request_payload,
        int(request_payload.get("numResults") or config["num_results"]),
        pricing,
        int(config["max_supported_results_for_estimate"]),
    )

    response_json, cache_hit = cache_store.get_or_set(
        request_payload,
        estimated_cost,
        run_id=runtime.run_id,
        budget_cap_usd=float(config["budget_cap_usd"]),
        fetcher=lambda payload: structured_search_http_call(
            payload,
            exa_api_key=runtime.exa_api_key,
            smoke_no_network=runtime.smoke_no_network,
            config=config,
        ),
    )

    structured_payload = build_structured_search_artifact(
        query,
        schema_path=schema_path,
        request_payload=request_payload,
        response_json=response_json,
        cache_hit=cache_hit,
        estimated_cost_usd=estimated_cost,
    )
    summary = cache_store.spend_so_far(run_id=runtime.run_id)
    writer = ExperimentArtifactWriter(
        run_id=runtime.run_id,
        config=config,
        pricing=pricing,
        run_context={"workflow": "structured-search"},
        runtime_metadata=dict(runtime_metadata),
        base_dir=artifact_dir,
    )
    writer.write_json_artifact("structured_output.json", structured_payload)
    writer.write_summary(
        summary,
        projections=_summary_projections(summary),
        recommendation_data={
            "headline_recommendation": "Use for schema-driven extraction workflows"
        },
        qualitative_notes=[
            "Structured output active: the response payload is stored in structured_output.json.",
            "Smoke mode active: structured output is mocked and costs are zero.",
        ]
        if runtime.smoke_no_network
        else [
            "Structured output active: the response payload is stored in structured_output.json.",
        ],
        extra={
            "workflow": "structured-search",
            "structured_search": {
                "query": query,
                "schema_file": str(schema_path),
                "cache_hit": cache_hit,
                "structured_keys": structured_payload["structured_output_keys"],
            },
        },
    )

    return {
        "workflow": "structured-search",
        "run_id": runtime.run_id,
        "artifact_dir": str(writer.artifact_dir),
        "schema_file": str(schema_path),
        "cache_hit": cache_hit,
        "request_id": structured_payload.get("request_id"),
        "structured_output": structured_payload.get("structured_output"),
        "summary": summary,
    }


def emit_structured_search_payload(payload: Mapping[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2))
        return

    print(f"run_id: {payload['run_id']}")
    print(f"artifact_dir: {payload['artifact_dir']}")
    print(f"schema_file: {payload['schema_file']}")
    print(f"cache_hit: {payload['cache_hit']}")
    print(f"request_id: {payload.get('request_id')}")
    print("structured_output:")
    print(json.dumps(payload.get("structured_output"), indent=2, sort_keys=True))


def _cache_store(config: Dict[str, Any]) -> SqliteCacheStore:
    return SqliteCacheStore(config["sqlite_path"], float(config["cache_ttl_hours"]))


def _summary_projections(summary: Mapping[str, Any]) -> Dict[str, Any]:
    unit_cost = float(summary.get("avg_cost_per_uncached_query", 0.0) or 0.0)
    return {
        "projection_basis": "observed_avg_uncached",
        "unit_cost_usd": unit_cost,
        "projected_100_queries_usd": unit_cost * 100,
        "projected_1000_queries_usd": unit_cost * 1000,
        "projected_10000_queries_usd": unit_cost * 10000,
    }
