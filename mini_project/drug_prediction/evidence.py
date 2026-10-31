"""Evidence metadata for computational drug-ranking results.

The current repository contains local target/pathway mappings, not a curated
clinical evidence database. This module makes that limitation explicit while
providing a stable result shape for a future evidence repository.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List


EVIDENCE_SCHEMA_VERSION = "1.0"
EVIDENCE_LEVEL = "computational_local"
EVIDENCE_SOURCE = "XMARs local drug and pathway knowledge base"


def build_drug_evidence(
    drug_name: str,
    drug_info: Dict[str, Any],
    mutations: Iterable[Dict[str, Any]],
    reasoning: Iterable[str],
) -> List[Dict[str, Any]]:
    """Build traceable local evidence records without implying clinical validation."""
    normalized_mutations = [
        {
            "gene": str(mutation.get("gene", "")).upper().strip(),
            "vaf": mutation.get("vaf", 0.5),
        }
        for mutation in mutations
        if str(mutation.get("gene", "")).strip()
    ]
    targets = [str(target).upper().strip() for target in drug_info.get("targets", [])]
    target_genes = [
        mutation["gene"]
        for mutation in normalized_mutations
        if mutation["gene"] in targets
    ]
    relation = "pathway_relevance"
    if target_genes:
        relation = "direct_target_overlap"
    elif reasoning:
        relation = "rule_based_interaction"

    return [{
        "evidence_id": f"local:{drug_name}:{relation}",
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "drug": drug_name,
        "variant": None,
        "genes": target_genes or [mutation["gene"] for mutation in normalized_mutations],
        "cancer_type": "NSCLC",
        "effect": "sensitivity_or_resistance_score",
        "relation": relation,
        "evidence_level": EVIDENCE_LEVEL,
        "source": EVIDENCE_SOURCE,
        "citation": None,
        "approval_status": "not_assessed",
        "clinically_validated": False,
        "source_pathway": drug_info.get("pathway", ""),
        "reasoning": list(reasoning),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "limitations": [
            "Derived from local gene-target-pathway mappings and deterministic rules.",
            "Not a variant-level clinical evidence assertion.",
            "Requires review against a curated, licensed evidence source.",
        ],
    }]
