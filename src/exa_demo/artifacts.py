from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

import pandas as pd

from .models import ExperimentSummaryRecord, QueryEvaluationRecord


class ExperimentArtifactWriter:
    def __init__(
        self,
        *,
        run_id: str,
        config: Mapping[str, Any],
        pricing: Mapping[str, Any],
        run_context: Optional[Mapping[str, Any]] = None,
        base_dir: str | Path = 'experiments',
    ) -> None:
        self.run_id = str(run_id)
        self.base_dir = Path(base_dir)
        self.run_context = _to_jsonable_mapping(run_context or {})
        self.artifact_dir = self.base_dir / self.run_id
        self.config_path = self.artifact_dir / 'config.json'
        self.queries_path = self.artifact_dir / 'queries.jsonl'
        self.results_path = self.artifact_dir / 'results.jsonl'
        self.summary_path = self.artifact_dir / 'summary.json'
        self._record_count = 0

        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        for path in (self.queries_path, self.results_path, self.summary_path):
            if path.exists():
                path.unlink()

        self._write_json(
            self.config_path,
            {
                'run_id': self.run_id,
                'generated_at_utc': _utc_now(),
                'config': _to_jsonable_mapping(config),
                'pricing': _to_jsonable_mapping(pricing),
            },
        )

    def record_query(self, record: QueryEvaluationRecord) -> None:
        self._append_jsonl(
            self.queries_path,
            {
                'query': record.query,
                'request_hash': record.request_hash,
                'request_id': record.request_id,
                'resolved_search_type': record.resolved_search_type,
                **self.run_context,
                'cache_hit': record.cache_hit,
                'created_at_utc': record.created_at_utc,
                'request_payload': record.request_payload,
            },
        )
        result_payload = record.to_dict()
        if self.run_context:
            result_payload = {**self.run_context, **result_payload}
        self._append_jsonl(self.results_path, result_payload)
        self._record_count += 1

    def write_summary(
        self,
        summary_metrics: Mapping[str, Any],
        *,
        projections: Optional[Mapping[str, Any]] = None,
        recommendation_data: Optional[Mapping[str, Any]] = None,
        batch_df: Optional[pd.DataFrame] = None,
        qualitative_notes: Optional[Iterable[str]] = None,
        extra: Optional[Mapping[str, Any]] = None,
    ) -> Path:
        projections = projections or {}
        recommendation_data = recommendation_data or {}
        qualitative_notes_list = [str(note) for note in (qualitative_notes or [])]
        batch_query_count = int(len(batch_df.index)) if batch_df is not None else self._record_count
        extra_payload: Dict[str, Any] = {}
        if self.run_context:
            extra_payload["run_context"] = self.run_context
        if extra:
            extra_payload.update(_to_jsonable_mapping(extra))

        record = ExperimentSummaryRecord(
            run_id=self.run_id,
            generated_at_utc=_utc_now(),
            batch_query_count=batch_query_count,
            request_count=int(summary_metrics.get('request_count', 0) or 0),
            cache_hits=int(summary_metrics.get('cache_hits', 0) or 0),
            uncached_calls=int(summary_metrics.get('uncached_calls', 0) or 0),
            spent_usd=float(summary_metrics.get('spent_usd', 0.0) or 0.0),
            avg_cost_per_uncached_query=float(summary_metrics.get('avg_cost_per_uncached_query', 0.0) or 0.0),
            projection_basis=_optional_str(projections.get('projection_basis')),
            unit_cost_usd=_optional_float(projections.get('unit_cost_usd')),
            projected_100_queries_usd=_optional_float(projections.get('projected_100_queries_usd')),
            projected_1000_queries_usd=_optional_float(projections.get('projected_1000_queries_usd')),
            projected_10000_queries_usd=_optional_float(projections.get('projected_10000_queries_usd')),
            headline_recommendation=_optional_str(recommendation_data.get('headline_recommendation')),
            observed_relevance_rate=_optional_float(recommendation_data.get('observed_relevance_rate')),
            observed_linkedin_rate=_optional_float(recommendation_data.get('observed_linkedin_rate')),
            observed_credibility_rate=_optional_float(recommendation_data.get('observed_credibility_rate')),
            observed_actionability_rate=_optional_float(recommendation_data.get('observed_actionability_rate')),
            observed_confidence_score=_optional_float(recommendation_data.get('observed_confidence_score')),
            observed_failure_rate=_optional_float(recommendation_data.get('observed_failure_rate')),
            budget_cap_usd=_optional_float(recommendation_data.get('budget_cap_usd')),
            qualitative_notes=qualitative_notes_list,
        )

        payload: Dict[str, Any] = record.to_dict()
        payload['artifact_dir'] = str(self.artifact_dir)
        payload['query_records_written'] = self._record_count
        if extra_payload:
            payload['extra'] = extra_payload

        self._write_json(self.summary_path, payload)
        return self.summary_path

    def write_json_artifact(self, filename: str, payload: Mapping[str, Any]) -> Path:
        path = self.artifact_dir / str(filename)
        self._write_json(path, payload)
        return path

    def _append_jsonl(self, path: Path, payload: Mapping[str, Any]) -> None:
        with path.open('a', encoding='utf-8', newline='\n') as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            handle.write('\n')

    def _write_json(self, path: Path, payload: Mapping[str, Any]) -> None:
        with path.open('w', encoding='utf-8', newline='\n') as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write('\n')


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _to_jsonable_mapping(value: Mapping[str, Any]) -> Dict[str, Any]:
    return json.loads(json.dumps(dict(value), ensure_ascii=False, default=str))
