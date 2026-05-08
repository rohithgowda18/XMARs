"""
AI Agent Tools
===============
Tools that wrap the pipeline functions for use by the agent system.
Each tool has a clear description so agents know when to use it.

These tools bridge the existing rule-based pipeline, SHAP explainability,
and agent reasoning. Includes both the original tools and new SHAP tools.
"""

import sys
import json
import logging
from pathlib import Path

# Ensure we can import from this directory
sys.path.insert(0, str(Path(__file__).parent))

from drug_knowledge_base import get_knowledge_base
from resistance_predictor import ResistancePredictor

logger = logging.getLogger(__name__)

# Initialize shared resources
_kb = None
_predictor = None


def _get_kb():
    global _kb
    if _kb is None:
        _kb = get_knowledge_base()
    return _kb


def _get_predictor():
    global _predictor
    if _predictor is None:
        _predictor = ResistancePredictor(_get_kb())
    return _predictor


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════════

TOOLS = {}


def register_tool(name, description):
    """Decorator to register a function as an agent tool."""
    def decorator(func):
        TOOLS[name] = {
            'name': name,
            'description': description,
            'function': func,
        }
        return func
    return decorator


@register_tool(
    name="get_available_genes",
    description="Get the list of all available gene symbols that can be analyzed. "
                "Returns gene names and number of drugs targeting each gene."
)
def get_available_genes():
    """Return available genes with metadata."""
    kb = _get_kb()
    result = []
    for gene in kb.available_genes:
        drugs = kb.get_drugs_targeting_gene(gene)
        pathways = kb.get_pathways_for_gene(gene)
        result.append({
            'gene': gene,
            'direct_drugs': len(drugs),
            'pathways': [p[0] for p in pathways],
        })
    return json.dumps(result, indent=2)


@register_tool(
    name="get_gene_info",
    description="Get detailed information about a specific gene: which pathways it belongs to, "
                "which drugs target it, and its role in cancer. "
                "Input: gene symbol (e.g., 'EGFR', 'TP53', 'KRAS')."
)
def get_gene_info(gene: str):
    """Return detailed gene information."""
    kb = _get_kb()
    gene = gene.upper().strip()

    drugs = kb.get_drugs_targeting_gene(gene)
    drug_names = [d['name'] for d in drugs[:15]]

    pathways = kb.get_pathways_for_gene(gene)
    pathway_info = []
    for name, data in pathways:
        pathway_info.append({
            'pathway': name,
            'description': data.get('description', ''),
            'cancer_relevance': data.get('cancer_relevance', ''),
            'drug_targets': data.get('drug_targets', []),
        })

    return json.dumps({
        'gene': gene,
        'direct_targeting_drugs': drug_names,
        'drug_count': len(drugs),
        'pathways': pathway_info,
    }, indent=2)


@register_tool(
    name="analyze_pathways",
    description="Analyze which cancer pathways are disrupted by a set of mutated genes. "
                "Returns pathway names, activation scores, and affected genes. "
                "Input: comma-separated gene symbols (e.g., 'EGFR,TP53,KRAS')."
)
def analyze_pathways(genes_csv: str):
    """Analyze pathway disruption for a set of mutations."""
    predictor = _get_predictor()
    genes = [g.strip().upper() for g in genes_csv.split(',') if g.strip()]
    mutations = [{'gene': g, 'vaf': 0.5} for g in genes]
    result = predictor.predict(mutations)

    pathways = []
    for pw in result['affected_pathways']:
        pathways.append({
            'pathway': pw['name'],
            'description': pw['description'],
            'activation_score': pw['activation_score'],
            'mutated_genes': [g['gene'] for g in pw['mutated_genes']],
            'drug_targets': pw.get('drug_targets', []),
        })

    return json.dumps({
        'genes_analyzed': genes,
        'pathways_affected': len(pathways),
        'pathways': pathways,
    }, indent=2)


@register_tool(
    name="predict_drug_resistance",
    description="Predict drug resistance probabilities for a mutation profile. "
                "Returns ranked drugs sorted by sensitivity (most effective first). "
                "Input: mutations as JSON array, e.g., "
                "'[{\"gene\":\"EGFR\",\"vaf\":0.45},{\"gene\":\"TP53\",\"vaf\":0.82}]'."
)
def predict_drug_resistance(mutations_json: str):
    """Predict drug resistance for a mutation profile."""
    predictor = _get_predictor()

    try:
        mutations = json.loads(mutations_json)
    except json.JSONDecodeError:
        genes = [g.strip().upper() for g in mutations_json.split(',')]
        mutations = [{'gene': g, 'vaf': 0.5} for g in genes if g]

    result = predictor.predict(mutations)

    top_drugs = []
    for d in result['drug_predictions'][:15]:
        top_drugs.append({
            'drug': d['drug_name'],
            'targets': d['targets'],
            'pathway': d['pathway'],
            'resistance_score': d['resistance_score'],
            'sensitivity_score': d['sensitivity_score'],
            'category': d['category'],
            'reasoning': d['reasoning'],
        })

    return json.dumps({
        'mutation_summary': result['mutation_summary'],
        'top_sensitive_drugs': top_drugs,
        'total_drugs_evaluated': result['mutation_summary']['drugs_evaluated'],
    }, indent=2)


@register_tool(
    name="query_drug_database",
    description="Search the drug database for drugs by name, target, or pathway. "
                "Input: search query (e.g., 'EGFR inhibitors', 'Erlotinib', 'PI3K pathway')."
)
def query_drug_database(query: str):
    """Search drugs in the knowledge base."""
    kb = _get_kb()
    query_upper = query.upper().strip()
    results = []

    for name, info in kb.drug_to_info.items():
        name_match = query_upper in name.upper()
        target_match = query_upper in info.get('targets_raw', '').upper()
        pathway_match = query_upper in info.get('pathway', '').upper()

        if name_match or target_match or pathway_match:
            results.append({
                'drug': name,
                'targets': info.get('targets_raw', ''),
                'pathway': info.get('pathway', ''),
            })

    return json.dumps({
        'query': query,
        'matches': len(results),
        'drugs': results[:20],
    }, indent=2)


# ═══════════════════════════════════════════════════════════════════════════════
# NEW SHAP TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

@register_tool(
    name="explain_with_shap",
    description="Run SHAP explainability analysis on the ML models for a set of mutations. "
                "Returns per-feature importance values showing WHY the model predicts what it does. "
                "Input: comma-separated gene symbols (e.g., 'EGFR,TP53')."
)
def explain_with_shap(genes_csv: str):
    """Run SHAP analysis for a set of genes."""
    import pandas as pd
    from shap_explainer import get_shap_explainer

    genes = [g.strip().upper() for g in genes_csv.split(',') if g.strip()]

    # Load data
    data_dir = Path(__file__).parent.parent / 'data' / 'processed'
    df = pd.read_csv(data_dir / 'mutation_features.csv')

    explainer = get_shap_explainer()
    feature_cols = explainer.feature_names

    # Get samples for each gene
    samples = []
    for gene in genes:
        gene_rows = df[df['gene_symbol'] == gene]
        if len(gene_rows) > 0:
            samples.append(gene_rows.iloc[0:1][feature_cols].fillna(0))

    if not samples:
        return json.dumps({'error': f'No data found for genes: {genes}'})

    combined = pd.concat(samples, ignore_index=True)
    results = explainer.explain_all_models(combined)

    # Simplify for tool output
    summary = {
        'genes': genes,
        'models_analyzed': [],
        'consensus_features': [],
    }

    for model_name, result in results.items():
        if model_name == 'consensus_features':
            summary['consensus_features'] = [
                {'feature': f['feature'], 'models': f['models']}
                for f in result[:10]
            ]
            continue
        if 'error' in result:
            continue
        summary['models_analyzed'].append({
            'model': model_name,
            'top_features': [
                {'feature': f['feature'], 'importance': f['mean_shap']}
                for f in result.get('global_top_features', [])[:5]
            ]
        })

    return json.dumps(summary, indent=2)


@register_tool(
    name="get_feature_importance",
    description="Get the top N most important features from a specific ML model "
                "based on SHAP analysis for a set of mutations. "
                "Input: 'model_name,gene1,gene2,...' (e.g., 'gradient_boosting,EGFR,TP53')."
)
def get_feature_importance(input_str: str):
    """Get feature importance for a specific model."""
    import pandas as pd
    from shap_explainer import get_shap_explainer

    parts = [p.strip() for p in input_str.split(',')]
    if len(parts) < 2:
        return json.dumps({'error': 'Input format: model_name,gene1,gene2,...'})

    model_name = parts[0]
    genes = [g.upper() for g in parts[1:]]

    data_dir = Path(__file__).parent.parent / 'data' / 'processed'
    df = pd.read_csv(data_dir / 'mutation_features.csv')

    explainer = get_shap_explainer()
    feature_cols = explainer.feature_names

    samples = []
    for gene in genes:
        gene_rows = df[df['gene_symbol'] == gene]
        if len(gene_rows) > 0:
            samples.append(gene_rows.iloc[0:1][feature_cols].fillna(0))

    if not samples:
        return json.dumps({'error': f'No data found for genes: {genes}'})

    combined = pd.concat(samples, ignore_index=True)
    result = explainer.explain(combined, model_name)

    return json.dumps({
        'model': model_name,
        'genes': genes,
        'global_top_features': result.get('global_top_features', [])[:15],
        'sample_count': result.get('num_samples', 0),
    }, indent=2)


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL EXECUTOR
# ═══════════════════════════════════════════════════════════════════════════════

def execute_tool(tool_name: str, tool_input: str = "") -> str:
    """Execute a tool by name with the given input."""
    if tool_name not in TOOLS:
        return json.dumps({'error': f'Tool {tool_name} not found. Available: {list(TOOLS.keys())}'})

    tool = TOOLS[tool_name]
    func = tool['function']

    try:
        import inspect
        params = inspect.signature(func).parameters
        if len(params) == 0:
            result = func()
        else:
            result = func(tool_input)
        return result
    except Exception as e:
        return json.dumps({'error': str(e)})


def get_tools_description() -> str:
    """Get a formatted description of all available tools for the LLM."""
    desc = "Available tools:\n\n"
    for name, tool in TOOLS.items():
        desc += f"- **{name}**: {tool['description']}\n\n"
    return desc
