"""
Drug Prediction Web Application
=================================
Flask web server that serves the drug resistance prediction interface.
Takes user input (mutated genes + VAF values) and returns ranked drug candidates.

Features:
  - Rule-based drug resistance prediction
  - Real multi-agent AI pipeline (4 independent agents)
  - SHAP explainability for ML model predictions
  - Gemini-powered human-readable clinical reports
  - Genomics chatbot

Run:
    python app.py
    Then open http://localhost:5000
"""

import sys
import json
import logging
from pathlib import Path
from flask import Flask, render_template, request, jsonify

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from drug_knowledge_base import get_knowledge_base
from resistance_predictor import ResistancePredictor

# Setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Load knowledge base at startup
logger.info("Loading drug knowledge base...")
kb = get_knowledge_base()
predictor = ResistancePredictor(kb)
logger.info("Knowledge base loaded successfully")


@app.route('/')
def index():
    """Serve the main prediction page."""
    return render_template('index.html')


@app.route('/api/genes', methods=['GET'])
def get_genes():
    """Return available genes for selection."""
    genes = kb.available_genes
    gene_info = []
    for gene in genes:
        pathways = kb.get_pathways_for_gene(gene)
        pathway_names = [p[0] for p in pathways]
        direct_drugs = kb.get_drugs_targeting_gene(gene)
        gene_info.append({
            'symbol': gene,
            'pathways': pathway_names,
            'direct_drug_count': len(direct_drugs),
        })
    return jsonify({'genes': gene_info})


@app.route('/api/pathways', methods=['GET'])
def get_pathways():
    """Return pathway data for visualization."""
    pathways = []
    for name, data in kb.pathways.items():
        pathways.append({
            'name': name,
            'description': data.get('description', ''),
            'cancer_relevance': data.get('cancer_relevance', ''),
            'genes': data.get('genes', []),
            'drug_targets': data.get('drug_targets', []),
        })
    return jsonify({'pathways': pathways})


@app.route('/predict', methods=['POST'])
def predict():
    """
    Run drug resistance prediction (rule-based).

    Expected JSON body:
    {
        "mutations": [
            {"gene": "EGFR", "vaf": 0.45},
            {"gene": "TP53", "vaf": 0.82}
        ]
    }
    """
    try:
        data = request.get_json()
        if not data or 'mutations' not in data:
            return jsonify({'error': 'Missing mutations in request body'}), 400

        mutations = data['mutations']

        # Validate input
        valid_genes = set(g.upper() for g in kb.available_genes)
        for mut in mutations:
            gene = mut.get('gene', '').upper().strip()
            if not gene:
                return jsonify({'error': 'Each mutation must have a gene symbol'}), 400
            if gene not in valid_genes:
                logger.warning(f"Gene {gene} not in mutation_features.csv but allowing")

            vaf = mut.get('vaf', 0.5)
            if not isinstance(vaf, (int, float)) or vaf < 0 or vaf > 1:
                mut['vaf'] = 0.5

        # Run prediction
        result = predictor.predict(mutations)

        return jsonify(result)

    except Exception as e:
        logger.error(f"Prediction error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/summary', methods=['GET'])
def get_summary():
    """Return knowledge base summary."""
    return jsonify(kb.get_summary())


# ═══════════════════════════════════════════════════════════════════
# AI AGENT PIPELINE ENDPOINTS
# ═══════════════════════════════════════════════════════════════════

GEMINI_API_KEY = "AIzaSyDXOyLIe6qbKzeGWV9O31YjrV7SQjxQSYk"


@app.route('/api/ai-status', methods=['GET'])
def ai_status():
    """Check AI agent system status."""
    return jsonify({
        'configured': bool(GEMINI_API_KEY),
        'architecture': 'real_multi_agent',
        'model': 'gemini (auto-detect compatible version)',
        'agents': [
            {
                'name': 'Mutation Analyst',
                'role': 'SHAP-based mutation classification using ML models',
                'type': 'computational',
            },
            {
                'name': 'Pathway Specialist',
                'role': 'Biological pathway mapping and disruption scoring',
                'type': 'computational',
            },
            {
                'name': 'Drug Strategist',
                'role': 'Drug resistance scoring with evidence chains',
                'type': 'computational',
            },
            {
                'name': 'Clinical Advisor',
                'role': 'Synthesis + Gemini human-readable explanation',
                'type': 'hybrid (compute + LLM)',
            },
        ],
        'shap_enabled': True,
        'models_available': ['random_forest', 'gradient_boosting', 'adaboost'],
    })


@app.route('/predict-ai', methods=['POST'])
def predict_ai():
    """
    Run the REAL multi-agent pipeline.

    4 independent agents execute sequentially:
      Agent 1: Mutation Analyst (SHAP + ML models)
      Agent 2: Pathway Specialist (pathway mapping)
      Agent 3: Drug Strategist (drug ranking + evidence)
      Agent 4: Clinical Advisor (synthesis + Gemini explanation)

    Expected JSON body:
    {
        "mutations": [
            {"gene": "EGFR", "vaf": 0.45},
            {"gene": "TP53", "vaf": 0.82}
        ]
    }
    """
    try:
        data = request.get_json()
        if not data or 'mutations' not in data:
            return jsonify({'error': 'Missing mutations in request body'}), 400

        mutations = data['mutations']
        if not mutations:
            return jsonify({'error': 'At least one mutation is required'}), 400

        # Import and run the real agent pipeline
        from agents import AgentPipeline
        pipeline = AgentPipeline(api_key=GEMINI_API_KEY)
        result = pipeline.run(mutations)

        return jsonify(result)

    except Exception as e:
        logger.error(f"AI pipeline error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ═══════════════════════════════════════════════════════════════════
# SHAP EXPLAINABILITY ENDPOINT
# ═══════════════════════════════════════════════════════════════════

@app.route('/api/shap', methods=['POST'])
def shap_explain():
    """
    Get SHAP feature importance for a mutation profile.

    Expected JSON body:
    {
        "mutations": [
            {"gene": "EGFR", "vaf": 0.45},
            {"gene": "TP53", "vaf": 0.82}
        ],
        "model": "gradient_boosting"  (optional, default: all models)
    }
    """
    try:
        data = request.get_json()
        if not data or 'mutations' not in data:
            return jsonify({'error': 'Missing mutations'}), 400

        mutations = data['mutations']
        model_name = data.get('model', None)

        # Build feature DataFrame from mutations
        import pandas as pd
        from shap_explainer import get_shap_explainer

        features_path = Path(__file__).parent.parent / 'data' / 'processed' / 'mutation_features.csv'
        df = pd.read_csv(features_path)

        explainer = get_shap_explainer()
        feature_cols = explainer.feature_names

        # Extract rows for the mutated genes
        samples = []
        for mut in mutations:
            gene = mut['gene'].upper().strip()
            gene_rows = df[df['gene_symbol'] == gene]
            if len(gene_rows) > 0:
                sample = gene_rows.iloc[0:1][feature_cols].fillna(0).copy()
                if 'vaf' in sample.columns:
                    sample['vaf'] = float(mut.get('vaf', 0.5))
                samples.append(sample)

        if not samples:
            return jsonify({'error': 'No matching genes found'}), 400

        combined = pd.concat(samples, ignore_index=True)

        if model_name:
            result = explainer.explain(combined, model_name)
        else:
            result = explainer.explain_all_models(combined)

        # Also get chart data for each model
        chart_data = {}
        for mn in explainer.explainers:
            try:
                chart_data[mn] = explainer.generate_shap_chart_data(combined, mn)
            except Exception as e:
                chart_data[mn] = {'error': str(e)}

        return jsonify({
            'shap_results': result,
            'chart_data': chart_data,
            'genes': [m['gene'] for m in mutations],
        })

    except Exception as e:
        logger.error(f"SHAP error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ═══════════════════════════════════════════════════════════════════
# CHATBOT ENDPOINT
# ═══════════════════════════════════════════════════════════════════

@app.route('/chat', methods=['POST'])
def chat():
    """Chat with Gemini about cancer genomics."""
    try:
        if not GEMINI_API_KEY:
            return jsonify({'error': 'Gemini API key not configured'}), 400

        data = request.get_json()
        message = data.get('message', '').strip()
        context = data.get('context', '')

        if not message:
            return jsonify({'error': 'Message is required'}), 400

        kb_summary = kb.get_summary()
        system_context = (
            "You are a cancer genomics assistant for a Drug Resistance Prediction system. "
            "You help oncology researchers understand mutation profiles, pathway disruptions, "
            "and drug resistance mechanisms in lung cancer.\n\n"
            f"Knowledge base: {kb_summary['total_drugs']} drugs, "
            f"{kb_summary['total_pathways']} pathways, "
            f"{kb_summary['gene_count']} genes.\n\n"
            "Keep responses concise (2-4 paragraphs max). Use markdown formatting. "
            "If asked about specific drugs or genes, provide factual information from oncology. "
            "Always note that predictions are computational and require clinical validation."
        )

        if context:
            system_context += f"\n\nCurrent analysis context:\n{context}"

        from google import genai
        client = genai.Client(api_key=GEMINI_API_KEY)

        # Try compatible models
        models_to_try = ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash']
        for model_name in models_to_try:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=f"{system_context}\n\n---\n\nUser question: {message}",
                    config={
                        "temperature": 0.5,
                        "max_output_tokens": 1024,
                    }
                )
                return jsonify({'reply': response.text})
            except Exception as e:
                if "429" in str(e):
                    continue
                elif "not found" in str(e).lower():
                    continue
                else:
                    raise

        return jsonify({'error': 'All Gemini models rate-limited. Please wait and try again.'}), 429

    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/chat-page')
def chat_page():
    """Serve the dedicated chat page."""
    return render_template('chat.html')


if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("  DRUG RESISTANCE PREDICTION SERVER")
    print("  + Real Multi-Agent Pipeline (4 Agents)")
    print("  + SHAP Explainability")
    print("  + Gemini Human Explanation")
    print("=" * 60)
    print(f"  Knowledge base: {len(kb.drug_to_info)} drugs, "
          f"{len(kb.pathways)} pathways, {len(kb.available_genes)} genes")
    print(f"  Agent Pipeline:")
    print(f"    1. Mutation Analyst   (SHAP + ML models)")
    print(f"    2. Pathway Specialist (pathway mapping)")
    print(f"    3. Drug Strategist    (drug ranking)")
    print(f"    4. Clinical Advisor   (Gemini explanation)")
    print(f"  Open http://localhost:5000 in your browser")
    print("=" * 60 + "\n")
    app.run(debug=True, host='0.0.0.0', port=5000)
