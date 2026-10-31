"""Reproducibility metadata for a single XMARs analysis execution."""

import hashlib
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable

try:
    from .contracts import MUTATION_SCHEMA_VERSION, normalize_mutations
except ImportError:
    from contracts import MUTATION_SCHEMA_VERSION, normalize_mutations


ANALYSIS_RUN_SCHEMA_VERSION = "1.0"
PIPELINE_VERSION = "1.0"


def _file_fingerprint(path: Path) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {
        "path": str(path),
        "available": path.is_file(),
    }
    if not path.is_file():
        metadata["error"] = "Artifact does not exist"
        return metadata

    digest = hashlib.sha256()
    with path.open("rb") as artifact:
        for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
            digest.update(chunk)
    metadata["sha256"] = digest.hexdigest()
    metadata["size_bytes"] = path.stat().st_size
    return metadata


def _component_versions(project_root: Path) -> Dict[str, Any]:
    artifacts = (
        project_root / "data" / "processed" / "mutation_features.csv",
        project_root / "data" / "processed" / "pathway_reference.json",
        project_root / "data" / "processed" / "03_compounds_cleaned.csv",
        project_root / "models" / "random_forest_pipeline.pkl",
        project_root / "models" / "gradient_boosting_pipeline.pkl",
        project_root / "models" / "adaboost_pipeline.pkl",
    )
    return {
        "application_version": os.getenv("XMARS_VERSION", "development"),
        "pipeline_version": PIPELINE_VERSION,
        "mutation_schema_version": MUTATION_SCHEMA_VERSION,
        "artifacts": [_file_fingerprint(path) for path in artifacts],
    }


def start_analysis_run(
    mutations: Iterable[Dict[str, Any]],
    project_root: Path,
) -> Dict[str, Any]:
    """Create immutable input and component metadata for an analysis run."""
    normalized_mutations = normalize_mutations(mutations)
    started_at = datetime.now(timezone.utc)
    return {
        "analysis_run_schema_version": ANALYSIS_RUN_SCHEMA_VERSION,
        "analysis_run_id": str(uuid.uuid4()),
        "status": "running",
        "started_at": started_at.isoformat(),
        "input": {
            "mutations": normalized_mutations,
            "mutation_count": len(normalized_mutations),
        },
        "components": _component_versions(project_root),
    }


def finish_analysis_run(
    metadata: Dict[str, Any],
    status: str,
    elapsed_seconds: float,
) -> Dict[str, Any]:
    """Return completed run metadata without changing the original input."""
    completed = dict(metadata)
    completed["status"] = status
    completed["completed_at"] = datetime.now(timezone.utc).isoformat()
    completed["elapsed_seconds"] = elapsed_seconds
    return completed
