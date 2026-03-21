from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def to_jsonable_mapping(value: Mapping[str, Any]) -> Dict[str, Any]:
    return json.loads(json.dumps(dict(value), ensure_ascii=False, default=str))


def append_jsonl(path: Path, payload: Mapping[str, Any]) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        handle.write("\n")


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


class ArtifactManifest:
    def __init__(
        self,
        *,
        run_id: str,
        artifact_dir: Path,
        manifest_path: Path,
        run_context: Mapping[str, Any],
        runtime_metadata: Mapping[str, Any],
    ) -> None:
        self.run_id = str(run_id)
        self.artifact_dir = artifact_dir
        self.manifest_path = manifest_path
        self.run_context = to_jsonable_mapping(run_context)
        self.runtime_metadata = to_jsonable_mapping(runtime_metadata)
        self._artifact_records: list[dict[str, str]] = []

    def record(self, path: Path, *, kind: str) -> None:
        record = {
            "filename": path.name,
            "kind": str(kind),
            "path": str(path),
        }
        existing_index = next(
            (
                index
                for index, item in enumerate(self._artifact_records)
                if item["filename"] == path.name
            ),
            None,
        )
        if existing_index is None:
            self._artifact_records.append(record)
        else:
            self._artifact_records[existing_index] = record
        write_json(
            self.manifest_path,
            {
                "run_id": self.run_id,
                "artifact_dir": str(self.artifact_dir),
                "run_context": self.run_context,
                "runtime": self.runtime_metadata,
                "artifacts": sorted(
                    self._artifact_records, key=lambda item: item["filename"]
                ),
            },
        )
