"""Versioned domain contracts shared by analysis services and agent tools."""

from dataclasses import dataclass
from math import isfinite
from typing import Any, Dict, Iterable, List, Mapping, Optional


MUTATION_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class MutationInput:
    """Canonical representation of a mutation accepted by the analysis pipeline."""

    gene: str
    vaf: float = 0.5
    variant: Optional[str] = None
    effect: Optional[str] = None
    chromosome: Optional[Any] = None
    position: Optional[Any] = None
    protein_mutation: Optional[str] = None
    coding: Optional[bool] = None
    cancer_predisposition_variant: Optional[bool] = None

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "MutationInput":
        if not isinstance(value, Mapping):
            raise ValueError("Each mutation must be an object")

        gene = str(value.get("gene", "")).strip().upper()
        if not gene:
            raise ValueError("Mutation gene must be a non-empty string")

        raw_vaf = value.get("vaf", 0.5)
        if isinstance(raw_vaf, bool):
            raise ValueError(f"Mutation '{gene}' vaf must be a number")
        try:
            vaf = float(raw_vaf)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Mutation '{gene}' vaf must be a number") from exc
        if not isfinite(vaf) or not 0 <= vaf <= 1:
            raise ValueError(f"Mutation '{gene}' vaf must be between 0 and 1")

        return cls(
            gene=gene,
            vaf=vaf,
            variant=_optional_string(value.get("variant")),
            effect=_optional_string(value.get("effect")),
            chromosome=value.get("chromosome"),
            position=value.get("position"),
            protein_mutation=_optional_string(value.get("protein_mutation")),
            coding=value.get("coding"),
            cancer_predisposition_variant=value.get("cancer_predisposition_variant"),
        )

    def to_mapping(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "gene": self.gene,
            "vaf": self.vaf,
        }
        optional_fields = (
            "variant",
            "effect",
            "chromosome",
            "position",
            "protein_mutation",
            "coding",
            "cancer_predisposition_variant",
        )
        for field in optional_fields:
            value = getattr(self, field)
            if value is not None:
                result[field] = value
        return result


def _optional_string(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def normalize_mutations(mutations: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Validate and normalize mutations at a pipeline boundary."""
    if isinstance(mutations, (str, bytes)) or mutations is None:
        raise ValueError("Mutations must be an array of objects")
    normalized = [MutationInput.from_mapping(mutation).to_mapping() for mutation in mutations]
    if not normalized:
        raise ValueError("At least one mutation is required")
    return normalized
