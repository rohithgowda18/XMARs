"""Deterministic checks for Gemini responses against executed tool evidence."""

import re
from typing import Any, Dict, List

GENE_TOKEN = re.compile(r'\b[A-Z][A-Z0-9]{1,10}\b')
CLINICAL_CAVEAT_TERMS = (
    'clinical validation',
    'clinician',
    'oncologist',
    'computational',
    'not medical advice',
)


def _evidence_text(tool_calls: List[Dict[str, Any]]) -> str:
    return '\n'.join(str(call.get('result', '')) for call in tool_calls)


def verify_response(answer: str, tool_calls: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Return warnings when a response cannot be traced to tool evidence."""
    warnings = []
    evidence = _evidence_text(tool_calls)
    successful_calls = [call for call in tool_calls if call.get('ok')]

    if not successful_calls:
        warnings.append('No successful deterministic tool result supports this response.')

    known_genes = set(GENE_TOKEN.findall(evidence))
    answer_genes = set(GENE_TOKEN.findall(answer or ''))
    unsupported_genes = sorted(
        gene for gene in answer_genes
        if gene not in known_genes and gene not in {'AI', 'LLM', 'SHAP', 'VAF', 'PDF', 'DNA', 'RNA'}
    )
    if unsupported_genes:
        warnings.append(
            f'Potentially unsupported gene tokens in response: {", ".join(unsupported_genes)}'
        )

    if not any(term in (answer or '').lower() for term in CLINICAL_CAVEAT_TERMS):
        warnings.append('Response does not contain an explicit clinical-validation caveat.')

    if any(word in (answer or '').lower() for word in ('recommend', 'prescribe', 'treat')) \
            and not any(call.get('tool') == 'predict_drug_resistance' for call in successful_calls):
        warnings.append('Treatment language was used without a drug-resistance tool result.')

    return {
        'status': 'verified' if not warnings else 'review',
        'warnings': warnings,
        'successful_tool_calls': len(successful_calls),
        'evidence_execution_ids': [
            call.get('provenance', {}).get('execution_id')
            for call in successful_calls
            if call.get('provenance', {}).get('execution_id')
        ],
    }
