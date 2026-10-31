"""Validated local repository for curated evidence records.

Records are intentionally data-driven so a licensed, reviewed source can be
added later without changing the prediction code.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


REQUIRED_FIELDS = {
    "evidence_id",
    "drug",
    "gene",
    "cancer_type",
    "effect",
    "evidence_level",
    "source",
    "citation",
    "last_reviewed",
}


class EvidenceRepository:
    """Load and query reviewed evidence records from a JSON document."""

    def __init__(self, path: Optional[Path] = None):
        self.path = path or (
            Path(__file__).parent.parent
            / "data"
            / "evidence"
            / "curated_records.json"
        )
        self.records: List[Dict[str, Any]] = []
        self.load()

    def load(self) -> "EvidenceRepository":
        if not self.path.is_file():
            return self
        with self.path.open("r", encoding="utf-8") as evidence_file:
            payload = json.load(evidence_file)
        if not isinstance(payload, dict) or not isinstance(payload.get("records"), list):
            raise ValueError("Evidence repository must contain a 'records' array")
        self.records = [self._validate(record) for record in payload["records"]]
        return self

    def find(
        self,
        drug: str,
        genes: List[str],
        cancer_type: str = "NSCLC",
        variant: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        drug_key = drug.strip().upper()
        gene_keys = {gene.strip().upper() for gene in genes}
        cancer_key = cancer_type.strip().upper()
        matches = []
        for record in self.records:
            if record["drug"].strip().upper() != drug_key:
                continue
            if record["cancer_type"].strip().upper() != cancer_key:
                continue
            if record["gene"].strip().upper() not in gene_keys:
                continue
            record_variant = record.get("variant")
            if variant and record_variant and record_variant.upper() != variant.upper():
                continue
            matches.append({**record, "clinically_validated": True})
        return matches

    @staticmethod
    def _validate(record: Any) -> Dict[str, Any]:
        if not isinstance(record, dict):
            raise ValueError("Each evidence record must be an object")
        missing = REQUIRED_FIELDS - set(record)
        if missing:
            raise ValueError(
                f"Evidence record is missing required fields: {', '.join(sorted(missing))}"
            )
        if not all(isinstance(record[field], str) and record[field].strip() for field in REQUIRED_FIELDS):
            raise ValueError("Evidence record required fields must be non-empty strings")
        return record
