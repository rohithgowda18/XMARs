"""
Real Multi-Agent Pipeline
===========================
4 independent AI agents that each perform actual computational work
in a sequential pipeline. Gemini is used ONLY at the final step
to translate the structured technical results into human-understandable language.

Agent 1: Mutation Analyst   → SHAP-based mutation classification
Agent 2: Pathway Specialist → Pathway mapping and disruption analysis
Agent 3: Drug Strategist    → Drug ranking with evidence chains
Agent 4: Clinical Advisor   → Synthesis + Gemini human explanation

Each agent is a standalone Python class with a run() method.
"""

import os
import json
import time
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent.parent / '.env')
import numpy as np
import pandas as pd
from typing import List, Dict, Optional
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / 'data' / 'processed'

# Lazy imports to avoid circular dependencies
_kb = None
_predictor = None
_shap_explainer = None


def _get_kb():
    global _kb
    if _kb is None:
        from drug_knowledge_base import get_knowledge_base
        _kb = get_knowledge_base()
    return _kb


def _get_predictor():
    global _predictor
    if _predictor is None:
        from resistance_predictor import ResistancePredictor
        _predictor = ResistancePredictor(_get_kb())
    return _predictor


def _get_shap():
    global _shap_explainer
    if _shap_explainer is None:
        from shap_explainer import get_shap_explainer
        _shap_explainer = get_shap_explainer()
    return _shap_explainer


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT 1: MUTATION ANALYST
# ═══════════════════════════════════════════════════════════════════════════════

class MutationAnalystAgent:
    """
    Agent 1: Analyzes patient mutations using trained ML models + SHAP.

    Real work performed:
    - Loads trained ML models
    - Extracts feature vectors for the patient's mutated genes
    - Runs SHAP TreeExplainer to get per-feature importance
    - Classifies each mutation as driver/passenger based on SHAP values
    - Reports which features contribute most to the prediction
    """

    name = "Mutation Analyst"
    role = "Genomic mutation classification and feature importance analysis"

    def run(self, mutations: List[Dict]) -> Dict:
        start_time = time.time()
        thinking = []

        genes = [m['gene'].upper().strip() for m in mutations]
        vafs = {m['gene'].upper().strip(): float(m.get('vaf', 0.5)) for m in mutations}

        thinking.append(f"Received {len(mutations)} mutation(s) for analysis: {', '.join(genes)}")
        thinking.append(f"VAF values: {', '.join(f'{g}={v:.2f}' for g,v in vafs.items())}")

        # Load mutation features data
        features_path = DATA_DIR / 'mutation_features.csv'
        df = pd.read_csv(features_path)
        thinking.append(f"Loaded mutation_features.csv — {len(df)} rows, {len(df.columns)} columns")

        feature_cols = [col for col in df.columns if col.startswith('ohe_')]
        feature_cols.extend(['vaf', 'vaf_high', 'vaf_low', 'coding',
                             'cancer_predisposition_variant', 'gene_mutation_count'])
        feature_cols = [col for col in feature_cols if col in df.columns]
        thinking.append(f"Using {len(feature_cols)} features for ML models")

        gene_samples = {}
        for gene in genes:
            gene_rows = df[df['gene_symbol'] == gene]
            if len(gene_rows) > 0:
                sample = gene_rows.iloc[0:1][feature_cols].fillna(0).copy()
                if 'vaf' in sample.columns:
                    sample['vaf'] = vafs.get(gene, 0.5)
                gene_samples[gene] = sample
                thinking.append(f"Found {len(gene_rows)} samples for {gene} in dataset, extracted feature vector")
            else:
                thinking.append(f"⚠ Gene {gene} not found in mutation_features.csv — skipping")

        if not gene_samples:
            elapsed = round(time.time() - start_time, 2)
            thinking.append("No matching genes found — returning empty analysis")
            return {'agent': self.name, 'status': 'completed', 'elapsed_seconds': elapsed,
                    'gene_analyses': [], 'shap_results': {}, 'thinking': thinking,
                    'error': 'No matching genes found in the dataset'}

        combined_df = pd.concat(gene_samples.values(), ignore_index=True)
        thinking.append(f"Combined feature matrix: {combined_df.shape[0]} samples × {combined_df.shape[1]} features")

        # Run SHAP
        thinking.append("Loading trained ML models (RandomForest, GradientBoosting, AdaBoost)...")
        shap_explainer = _get_shap()
        model_names = list(shap_explainer.explainers.keys())
        thinking.append(f"SHAP explainers ready for: {', '.join(model_names)}")
        thinking.append("Running SHAP TreeExplainer on all 3 models — computing Shapley values for each feature...")

        shap_results = shap_explainer.explain_all_models(combined_df)

        for mn, res in shap_results.items():
            if mn == 'consensus_features':
                continue
            if 'error' not in res:
                top3 = [f['feature'] for f in res.get('global_top_features', [])[:3]]
                thinking.append(f"  {mn}: top features → {', '.join(top3)}")

        # Build per-gene analysis
        gene_analyses = []
        sample_idx = 0
        for gene in genes:
            if gene not in gene_samples:
                gene_analyses.append({'gene': gene, 'vaf': vafs.get(gene, 0.5),
                    'status': 'not_found', 'classification': 'unknown', 'shap_features': []})
                continue

            thinking.append(f"Analyzing {gene} (VAF={vafs.get(gene, 0.5):.2f})...")

            all_model_features = {}
            for model_name, result in shap_results.items():
                if model_name == 'consensus_features' or 'error' in result:
                    continue
                if sample_idx < len(result.get('sample_explanations', [])):
                    sample_exp = result['sample_explanations'][sample_idx]
                    for feat in sample_exp['top_features'][:10]:
                        fname = feat['feature']
                        if fname not in all_model_features:
                            all_model_features[fname] = {'feature': fname, 'models': {}, 'value': feat['value']}
                        all_model_features[fname]['models'][model_name] = {
                            'importance': feat['shap_importance'], 'direction': feat['direction']}

            sorted_features = sorted(
                all_model_features.values(),
                key=lambda x: np.mean([v['importance'] for v in x['models'].values()]),
                reverse=True
            )[:10]

            vaf = vafs.get(gene, 0.5)
            avg_importance = np.mean([
                np.mean([v['importance'] for v in f['models'].values()])
                for f in sorted_features
            ]) if sorted_features else 0

            if sorted_features:
                top_feat = sorted_features[0]
                top_imp = np.mean([v['importance'] for v in top_feat['models'].values()])
                thinking.append(f"  Strongest SHAP feature: '{top_feat['feature']}' (importance={top_imp:.4f})")

            if vaf >= 0.3 and avg_importance > 0.01:
                classification = 'likely_driver'
                confidence = min(0.95, 0.5 + vaf * 0.3 + avg_importance * 10)
                thinking.append(f"  VAF={vaf:.2f} ≥ 0.3 AND avg_SHAP={avg_importance:.4f} > 0.01 → classifying as LIKELY DRIVER (conf={confidence:.1%})")
            elif vaf >= 0.1:
                classification = 'possible_driver'
                confidence = min(0.7, 0.3 + vaf * 0.2 + avg_importance * 5)
                thinking.append(f"  VAF={vaf:.2f} ≥ 0.1 but moderate SHAP → classifying as POSSIBLE DRIVER (conf={confidence:.1%})")
            else:
                classification = 'likely_passenger'
                confidence = max(0.2, 0.5 - vaf * 0.3)
                thinking.append(f"  VAF={vaf:.2f} < 0.1 → classifying as LIKELY PASSENGER (conf={confidence:.1%})")

            gene_analyses.append({
                'gene': gene, 'vaf': vaf, 'status': 'analyzed',
                'classification': classification, 'confidence': round(confidence, 3),
                'avg_shap_importance': round(float(avg_importance), 6),
                'shap_features': sorted_features, 'models_used': list(shap_results.keys()),
            })
            sample_idx += 1

        # Chart data
        chart_data = {}
        thinking.append("Generating SHAP visualization data for frontend charts...")
        for model_name in shap_explainer.explainers:
            try:
                chart_data[model_name] = shap_explainer.generate_shap_chart_data(combined_df, model_name)
            except Exception as e:
                logger.error(f"Chart data failed for {model_name}: {e}")

        drivers = [g for g in gene_analyses if 'driver' in g.get('classification', '')]
        thinking.append(f"Analysis complete: {len(drivers)} driver(s), {len(gene_analyses)-len(drivers)} passenger(s) identified")
        thinking.append(f"Passing mutation analysis to Agent 2 (Pathway Specialist)...")

        elapsed = round(time.time() - start_time, 2)
        return {
            'agent': self.name, 'status': 'completed', 'elapsed_seconds': elapsed,
            'thinking': thinking,
            'gene_analyses': gene_analyses,
            'shap_results': {'consensus_features': shap_results.get('consensus_features', [])},
            'chart_data': chart_data,
            'summary': {
                'total_genes': len(genes),
                'genes_analyzed': len([g for g in gene_analyses if g['status'] == 'analyzed']),
                'drivers': len(drivers),
                'passengers': len([g for g in gene_analyses if g.get('classification') == 'likely_passenger']),
                'models_used': list(shap_explainer.explainers.keys()),
            }
        }


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT 2: PATHWAY SPECIALIST
# ═══════════════════════════════════════════════════════════════════════════════

class PathwaySpecialistAgent:
    """
    Agent 2: Maps mutations to biological pathways and analyzes disruption.

    Real work performed:
    - Uses DrugKnowledgeBase to map genes → pathways
    - Calculates pathway activation scores weighted by VAF + SHAP importance
    - Identifies cross-pathway interactions
    - Finds which pathway drug targets are compromised
    """

    name = "Pathway Specialist"
    role = "Cancer pathway mapping and disruption scoring"

    def run(self, mutations: List[Dict], mutation_analysis: Dict) -> Dict:
        start_time = time.time()
        thinking = []

        kb = _get_kb()
        gene_analyses = mutation_analysis.get('gene_analyses', [])

        thinking.append("Received mutation analysis from Agent 1 (Mutation Analyst)")
        thinking.append(f"Processing {len(gene_analyses)} analyzed gene(s)")

        gene_importance = {}
        for ga in gene_analyses:
            gene = ga['gene']
            gene_importance[gene] = {
                'vaf': ga.get('vaf', 0.5),
                'classification': ga.get('classification', 'unknown'),
                'shap_importance': ga.get('avg_shap_importance', 0),
            }
            thinking.append(f"  {gene}: {ga.get('classification','?')} (SHAP={ga.get('avg_shap_importance',0):.4f}, VAF={ga.get('vaf',0):.2f})")

        thinking.append("Querying DrugKnowledgeBase for pathway mappings...")

        pathway_data = {}
        for gene, info in gene_importance.items():
            pathways = kb.get_pathways_for_gene(gene)
            thinking.append(f"  {gene} → found in {len(pathways)} pathway(s): {', '.join(p[0] for p in pathways) if pathways else 'none'}")
            for pw_name, pw_data in pathways:
                if pw_name not in pathway_data:
                    pathway_data[pw_name] = {
                        'name': pw_name, 'description': pw_data.get('description', ''),
                        'cancer_relevance': pw_data.get('cancer_relevance', ''),
                        'all_genes': pw_data.get('genes', []),
                        'drug_targets': pw_data.get('drug_targets', []),
                        'mutated_genes': [], 'total_genes': len(pw_data.get('genes', [])),
                    }
                pathway_data[pw_name]['mutated_genes'].append({
                    'gene': gene, 'vaf': info['vaf'],
                    'classification': info['classification'], 'shap_importance': info['shap_importance'],
                })

        thinking.append(f"Total pathways affected: {len(pathway_data)}")
        thinking.append("Calculating activation scores (weighted by VAF + SHAP importance)...")

        affected_pathways = []
        for pw_name, pw in pathway_data.items():
            n_mutated = len(pw['mutated_genes'])
            n_total = pw['total_genes']
            avg_vaf = np.mean([g['vaf'] for g in pw['mutated_genes']])
            avg_shap = np.mean([g['shap_importance'] for g in pw['mutated_genes']])
            driver_count = len([g for g in pw['mutated_genes'] if 'driver' in g['classification']])

            base_activation = min(1.0, (n_mutated / max(n_total, 1)) * (0.5 + avg_vaf * 0.5))
            shap_boost = min(0.3, avg_shap * 50)
            driver_boost = 0.1 * driver_count
            activation_score = round(min(1.0, base_activation + shap_boost + driver_boost), 3)

            thinking.append(f"  {pw_name}: {n_mutated}/{n_total} genes mutated, base={base_activation:.3f} + shap_boost={shap_boost:.3f} + driver_boost={driver_boost:.1f} → activation={activation_score:.1%}")

            mutated_gene_names = {g['gene'] for g in pw['mutated_genes']}
            compromised_targets = [t for t in pw['drug_targets'] if t.upper() in mutated_gene_names]
            if compromised_targets:
                thinking.append(f"    ⚠ Compromised drug targets in {pw_name}: {', '.join(compromised_targets)}")

            affected_pathways.append({
                **pw, 'activation_score': activation_score,
                'avg_vaf': round(avg_vaf, 3), 'avg_shap_importance': round(float(avg_shap), 6),
                'driver_mutations': driver_count, 'compromised_drug_targets': compromised_targets,
            })

        affected_pathways.sort(key=lambda x: x['activation_score'], reverse=True)

        thinking.append("Checking for cross-pathway interactions (genes in multiple pathways)...")
        cross_talk = []
        gene_pathway_map = {}
        for pw in affected_pathways:
            for mg in pw['mutated_genes']:
                gene = mg['gene']
                if gene not in gene_pathway_map:
                    gene_pathway_map[gene] = []
                gene_pathway_map[gene].append(pw['name'])

        for gene, pathways in gene_pathway_map.items():
            if len(pathways) > 1:
                cross_talk.append({'gene': gene, 'pathways': pathways,
                    'impact': f"{gene} mutation disrupts {len(pathways)} pathways simultaneously"})
                thinking.append(f"  Cross-talk: {gene} appears in {len(pathways)} pathways → {', '.join(pathways)}")

        if not cross_talk:
            thinking.append("  No cross-pathway interactions detected")

        thinking.append(f"Pathway analysis complete — passing {len(affected_pathways)} pathway(s) to Agent 3 (Drug Strategist)")

        elapsed = round(time.time() - start_time, 2)
        return {
            'agent': self.name, 'status': 'completed', 'elapsed_seconds': elapsed,
            'thinking': thinking,
            'affected_pathways': affected_pathways, 'cross_talk': cross_talk,
            'summary': {
                'pathways_affected': len(affected_pathways),
                'total_cross_talk': len(cross_talk),
                'most_disrupted': affected_pathways[0]['name'] if affected_pathways else None,
                'highest_activation': affected_pathways[0]['activation_score'] if affected_pathways else 0,
            }
        }


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT 3: DRUG STRATEGIST
# ═══════════════════════════════════════════════════════════════════════════════

class DrugStrategistAgent:
    """
    Agent 3: Ranks drugs with evidence-based reasoning.

    Real work performed:
    - Uses ResistancePredictor to score all candidate drugs
    - Cross-references SHAP feature importance with drug targets
    - Builds evidence chains (mutation → pathway → drug → reasoning)
    - Ranks top recommendations with multi-model confidence
    """

    name = "Drug Strategist"
    role = "Drug resistance scoring and evidence-based ranking"

    def run(self, mutations: List[Dict],
            mutation_analysis: Dict,
            pathway_analysis: Dict) -> Dict:
        start_time = time.time()
        thinking = []

        thinking.append("Received mutation analysis from Agent 1 and pathway analysis from Agent 2")

        predictor = _get_predictor()
        thinking.append("Initializing ResistancePredictor with pharmacogenomic knowledge base...")

        prediction_result = predictor.predict(mutations)
        drug_predictions = prediction_result['drug_predictions']
        thinking.append(f"Resistance predictor evaluated {len(drug_predictions)} candidate drugs")

        gene_importance = {}
        for ga in mutation_analysis.get('gene_analyses', []):
            gene_importance[ga['gene']] = {
                'classification': ga.get('classification', 'unknown'),
                'shap_importance': ga.get('avg_shap_importance', 0),
                'top_shap_features': [f['feature'] for f in ga.get('shap_features', [])[:5]],
            }

        pathway_lookup = {}
        for pw in pathway_analysis.get('affected_pathways', []):
            pathway_lookup[pw['name']] = {
                'activation_score': pw['activation_score'],
                'driver_mutations': pw.get('driver_mutations', 0),
                'compromised_targets': pw.get('compromised_drug_targets', []),
            }

        thinking.append("Cross-referencing SHAP feature importance with drug targets...")
        thinking.append("Building evidence chains: mutation → SHAP → pathway → drug → reasoning")

        enhanced_drugs = []
        shap_matches = 0
        pw_matches = 0
        for drug in drug_predictions:
            drug_name = drug['drug_name']
            targets = drug.get('targets', '')
            pathway = drug.get('pathway', '')
            evidence_chain = []

            target_genes = [t.strip().upper() for t in targets.split(',') if t.strip()]
            for tg in target_genes:
                if tg in gene_importance:
                    gi = gene_importance[tg]
                    evidence_chain.append({
                        'type': 'shap_evidence',
                        'description': f"SHAP analysis confirms {tg} is a {gi['classification']} (importance={gi['shap_importance']:.4f}). Drug directly targets this gene.",
                        'strength': 'strong' if 'driver' in gi['classification'] else 'moderate',
                    })
                    shap_matches += 1

            for pw_name, pw_info in pathway_lookup.items():
                if pathway and pw_name.lower().replace('_', ' ') in pathway.lower().replace('_', ' '):
                    evidence_chain.append({
                        'type': 'pathway_evidence',
                        'description': f"Drug targets {pw_name} pathway (activation={pw_info['activation_score']:.2f}, {pw_info['driver_mutations']} driver mutations)",
                        'strength': 'strong' if pw_info['activation_score'] > 0.5 else 'moderate',
                    })
                    pw_matches += 1

            for reason in drug.get('reasoning', []):
                evidence_chain.append({'type': 'resistance_evidence', 'description': reason, 'strength': 'strong'})

            confidence = 'high' if len(evidence_chain) >= 3 else 'medium' if evidence_chain else 'low'
            enhanced_drugs.append({
                'rank': 0, 'drug_name': drug_name, 'targets': targets, 'pathway': pathway,
                'resistance_score': drug['resistance_score'], 'sensitivity_score': drug['sensitivity_score'],
                'category': drug['category'], 'category_color': drug.get('category_color', '#64748b'),
                'evidence_chain': evidence_chain, 'evidence_count': len(evidence_chain),
                'confidence': confidence, 'reasoning': drug.get('reasoning', []),
            })

        thinking.append(f"  SHAP-drug target matches found: {shap_matches}")
        thinking.append(f"  Pathway-drug matches found: {pw_matches}")

        enhanced_drugs.sort(key=lambda x: x['resistance_score'])
        for i, drug in enumerate(enhanced_drugs):
            drug['rank'] = i + 1

        top_10 = enhanced_drugs[:10]
        thinking.append("Ranking drugs by predicted sensitivity (lower resistance = better)...")
        for d in top_10[:5]:
            thinking.append(f"  #{d['rank']} {d['drug_name']}: sensitivity={d['sensitivity_score']:.0%}, evidence={d['evidence_count']} chains, confidence={d['confidence']}")

        categories = {}
        for d in enhanced_drugs:
            cat = d['category']
            categories[cat] = categories.get(cat, 0) + 1
        for cat, count in categories.items():
            thinking.append(f"  Category '{cat}': {count} drugs")

        thinking.append(f"Drug strategy complete — top recommendation: {top_10[0]['drug_name'] if top_10 else 'none'}")
        thinking.append("Passing ranked drugs and evidence to Agent 4 (Clinical Advisor)...")

        elapsed = round(time.time() - start_time, 2)
        return {
            'agent': self.name, 'status': 'completed', 'elapsed_seconds': elapsed,
            'thinking': thinking,
            'ranked_drugs': enhanced_drugs, 'top_10': top_10,
            'summary': {
                'total_drugs_evaluated': len(enhanced_drugs),
                'likely_sensitive': len([d for d in enhanced_drugs if d['category'] == 'Likely Sensitive']),
                'potentially_sensitive': len([d for d in enhanced_drugs if d['category'] == 'Potentially Sensitive']),
                'uncertain': len([d for d in enhanced_drugs if d['category'] == 'Uncertain']),
                'resistant': len([d for d in enhanced_drugs if 'Resistant' in d['category']]),
                'top_drug': top_10[0]['drug_name'] if top_10 else None,
                'top_drug_sensitivity': top_10[0]['sensitivity_score'] if top_10 else 0,
            }
        }


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT 4: CLINICAL ADVISOR
# ═══════════════════════════════════════════════════════════════════════════════

class ClinicalAdvisorAgent:
    """
    Agent 4: Synthesizes all results + uses Gemini for human-readable explanation.

    Real work performed:
    - Compiles structured clinical report from all 3 agents
    - Identifies key findings, red flags, and treatment considerations
    - Calls Gemini ONCE to translate the technical report into
      human-understandable language
    - Falls back gracefully if Gemini is unavailable
    """

    name = "Clinical Advisor"
    role = "Clinical synthesis and human-readable explanation (Gemini-powered)"

    def run(self, mutations: List[Dict],
            mutation_analysis: Dict,
            pathway_analysis: Dict,
            drug_strategy: Dict,
            api_key: str = None) -> Dict:
        start_time = time.time()
        thinking = []

        thinking.append("Received outputs from all 3 upstream agents")
        ms = mutation_analysis.get('summary', {})
        thinking.append(f"  Agent 1 found {ms.get('drivers', 0)} driver(s) and {ms.get('passengers', 0)} passenger(s)")
        ps = pathway_analysis.get('summary', {})
        thinking.append(f"  Agent 2 mapped {ps.get('pathways_affected', 0)} affected pathway(s)")
        ds = drug_strategy.get('summary', {})
        thinking.append(f"  Agent 3 ranked {ds.get('total_drugs_evaluated', 0)} drugs, top pick: {ds.get('top_drug', '?')}")

        thinking.append("Compiling structured clinical report from all agent data...")
        structured_report = self._build_structured_report(
            mutations, mutation_analysis, pathway_analysis, drug_strategy
        )
        thinking.append(f"  Key findings: {len(structured_report.get('key_findings', []))}")
        thinking.append(f"  Drug recommendations: {len(structured_report.get('drug_recommendations', []))}")
        thinking.append(f"  Clinical considerations: {len(structured_report.get('considerations', []))}")

        human_report = None
        gemini_used = False

        if api_key:
            thinking.append("Gemini API key available — attempting to generate human-readable explanation")
            thinking.append("Sending structured data to Gemini (trying gemini-2.5-flash, 2.0-flash, 1.5-flash)...")
            human_report = self._generate_gemini_explanation(structured_report, api_key)
            if human_report:
                gemini_used = True
                thinking.append("✓ Gemini successfully generated human-readable clinical report")
            else:
                thinking.append("⚠ Gemini unavailable (rate limit or error) — using structured fallback")
        else:
            thinking.append("No Gemini API key — generating structured text report")

        if not human_report:
            human_report = self._generate_fallback_report(structured_report)
            thinking.append("Generated formatted fallback report from structured data")

        thinking.append("Clinical report synthesis complete — pipeline finished")

        elapsed = round(time.time() - start_time, 2)
        return {
            'agent': self.name, 'status': 'completed', 'elapsed_seconds': elapsed,
            'thinking': thinking,
            'structured_report': structured_report, 'human_report': human_report,
            'gemini_used': gemini_used,
        }

    def _build_structured_report(self, mutations, mutation_analysis,
                                  pathway_analysis, drug_strategy) -> Dict:
        """Compile structured data from all agents."""
        genes = [m['gene'] for m in mutations]
        gene_analyses = mutation_analysis.get('gene_analyses', [])
        pathways = pathway_analysis.get('affected_pathways', [])
        top_drugs = drug_strategy.get('top_10', [])
        cross_talk = pathway_analysis.get('cross_talk', [])

        # Key findings
        key_findings = []

        # Driver mutations
        drivers = [g for g in gene_analyses if 'driver' in g.get('classification', '')]
        if drivers:
            driver_names = ', '.join(g['gene'] for g in drivers)
            key_findings.append(
                f"Identified {len(drivers)} likely driver mutation(s): {driver_names}"
            )

        # Cross-pathway disruption
        if cross_talk:
            for ct in cross_talk:
                key_findings.append(
                    f"{ct['gene']} disrupts {len(ct['pathways'])} pathways: "
                    f"{', '.join(ct['pathways'])}"
                )

        # Most disrupted pathway
        if pathways:
            top_pw = pathways[0]
            key_findings.append(
                f"Most disrupted pathway: {top_pw['name']} "
                f"(activation={top_pw['activation_score']:.1%})"
            )

        # Drug recommendations
        drug_recommendations = []
        for drug in top_drugs[:5]:
            rec = {
                'rank': drug['rank'],
                'drug': drug['drug_name'],
                'targets': drug['targets'],
                'sensitivity': f"{drug['sensitivity_score']:.0%}",
                'category': drug['category'],
                'evidence_count': drug['evidence_count'],
                'key_evidence': [e['description'] for e in drug['evidence_chain'][:2]],
            }
            drug_recommendations.append(rec)

        # Treatment considerations
        considerations = []
        passengers = [g for g in gene_analyses if g.get('classification') == 'likely_passenger']
        if passengers:
            considerations.append(
                f"{len(passengers)} passenger mutation(s) detected — "
                f"these are unlikely to drive tumor growth"
            )

        resistant_drugs = [d for d in drug_strategy.get('ranked_drugs', [])
                          if 'Resistant' in d.get('category', '')]
        if resistant_drugs:
            considerations.append(
                f"{len(resistant_drugs)} drugs show resistance markers — "
                f"these should be avoided or used with caution"
            )

        considerations.append(
            "All predictions are computational and require clinical validation. "
            "SHAP-based explanations show feature-level model reasoning."
        )

        return {
            'patient_mutations': [{'gene': g, 'vaf': m.get('vaf', 0.5)}
                                 for g, m in zip(genes, mutations)],
            'key_findings': key_findings,
            'mutation_summary': mutation_analysis.get('summary', {}),
            'pathway_summary': pathway_analysis.get('summary', {}),
            'drug_summary': drug_strategy.get('summary', {}),
            'drug_recommendations': drug_recommendations,
            'considerations': considerations,
        }

    def _generate_gemini_explanation(self, structured_report: Dict,
                                      api_key: str) -> Optional[str]:
        """
        Call Gemini ONCE to translate structured data into human language.
        This is the ONLY Gemini call in the entire pipeline.
        """
        try:
            from google import genai
        except ImportError:
            logger.warning("google-genai not installed, skipping Gemini explanation")
            return None

        prompt = f"""You are a clinical genomics assistant. Below is a structured analysis 
from our multi-agent cancer genomics pipeline. Your job is to translate this data into 
a clear, human-understandable clinical report.

IMPORTANT: Do NOT invent or hallucinate data. Only explain what's in the structured data below.
Use the actual drug names, scores, and pathway names from the data.

## Structured Analysis Data

### Key Findings
{json.dumps(structured_report['key_findings'], indent=2)}

### Mutation Summary  
{json.dumps(structured_report['mutation_summary'], indent=2)}

### Pathway Summary
{json.dumps(structured_report['pathway_summary'], indent=2)}

### Top 5 Drug Recommendations
{json.dumps(structured_report['drug_recommendations'], indent=2)}

### Drug Evaluation Summary
{json.dumps(structured_report['drug_summary'], indent=2)}

### Clinical Considerations
{json.dumps(structured_report['considerations'], indent=2)}

---

Write a clear clinical report in markdown with these sections:
1. **Patient Overview** - Summarize the mutation profile in plain language
2. **Key Findings** - Explain the most important findings in simple terms  
3. **Top Drug Recommendations** - Explain the top 5 drugs and WHY they are recommended, using the evidence data
4. **Treatment Considerations** - Important caveats and next steps

Keep the language accessible to a clinician who is not a bioinformatician.
Use the actual numbers and drug names from the data above."""

        logger.info("Sending structured data to Gemini for human explanation...")

        client = genai.Client(api_key=api_key)

        # Try compatible models in sequence (matching the log statement)
        models_to_try = ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash']
        for model_name in models_to_try:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config={
                        "temperature": 0.3,
                        "max_output_tokens": 2048,
                    }
                )
                logger.info(f"Gemini explanation generated successfully using {model_name}")
                return response.text
            except Exception as e:
                logger.warning(f"Failed to generate explanation with {model_name}: {e}")
                # Continue to next model if we hit rate limits or model not found errors
                continue

        logger.error("All Gemini models failed to generate clinical explanation. Falling back to structured report.")
        return None

    def _generate_fallback_report(self, structured_report: Dict) -> str:
        """Generate a clean text report when Gemini is unavailable."""
        lines = []
        lines.append("# Clinical Analysis Report")
        lines.append("")
        lines.append("*Generated by Multi-Agent Pipeline (Gemini unavailable — showing structured analysis)*")
        lines.append("")

        # Key findings
        lines.append("## Key Findings")
        for finding in structured_report.get('key_findings', []):
            lines.append(f"- {finding}")
        lines.append("")

        # Mutations
        ms = structured_report.get('mutation_summary', {})
        lines.append("## Mutation Analysis")
        lines.append(f"- **Genes analyzed:** {ms.get('total_genes', 0)}")
        lines.append(f"- **Driver mutations:** {ms.get('drivers', 0)}")
        lines.append(f"- **Passenger mutations:** {ms.get('passengers', 0)}")
        lines.append(f"- **ML models used:** {', '.join(ms.get('models_used', []))}")
        lines.append("")

        # Pathways
        ps = structured_report.get('pathway_summary', {})
        lines.append("## Pathway Analysis")
        lines.append(f"- **Pathways disrupted:** {ps.get('pathways_affected', 0)}")
        if ps.get('most_disrupted'):
            lines.append(f"- **Most disrupted:** {ps['most_disrupted']} "
                         f"(activation: {ps.get('highest_activation', 0):.1%})")
        lines.append("")

        # Drug recommendations
        lines.append("## Top Drug Recommendations")
        for drug in structured_report.get('drug_recommendations', []):
            lines.append(f"### {drug['rank']}. {drug['drug']}")
            lines.append(f"- **Targets:** {drug['targets']}")
            lines.append(f"- **Sensitivity:** {drug['sensitivity']}")
            lines.append(f"- **Category:** {drug['category']}")
            if drug.get('key_evidence'):
                lines.append(f"- **Evidence:** {'; '.join(drug['key_evidence'])}")
            lines.append("")

        # Drug summary
        ds = structured_report.get('drug_summary', {})
        lines.append("## Drug Evaluation Summary")
        lines.append(f"- **Total drugs evaluated:** {ds.get('total_drugs_evaluated', 0)}")
        lines.append(f"- **Likely sensitive:** {ds.get('likely_sensitive', 0)}")
        lines.append(f"- **Uncertain:** {ds.get('uncertain', 0)}")
        lines.append(f"- **Resistant:** {ds.get('resistant', 0)}")
        lines.append("")

        # Considerations
        lines.append("## Clinical Considerations")
        for c in structured_report.get('considerations', []):
            lines.append(f"- {c}")

        return '\n'.join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# PIPELINE ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════════

class AgentPipeline:
    """
    Orchestrates the 4-agent pipeline in sequence.
    Each agent processes data and passes results to the next.
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self.agents = {
            'mutation_analyst': MutationAnalystAgent(),
            'pathway_specialist': PathwaySpecialistAgent(),
            'drug_strategist': DrugStrategistAgent(),
            'clinical_advisor': ClinicalAdvisorAgent(),
        }

    def run(self, mutations: List[Dict]) -> Dict:
        """
        Execute the full agent pipeline.

        Args:
            mutations: [{'gene': 'EGFR', 'vaf': 0.45}, ...]

        Returns:
            Combined results from all 4 agents
        """
        pipeline_start = time.time()
        logger.info(f"Starting Agent Pipeline with {len(mutations)} mutations")

        execution_log = []

        # ── Agent 1: Mutation Analyst ──
        try:
            mutation_result = self.agents['mutation_analyst'].run(mutations)
            execution_log.append({
                'agent': 'Mutation Analyst', 'status': 'completed',
                'elapsed': mutation_result['elapsed_seconds'],
                'summary': mutation_result.get('summary', {}),
                'thinking': mutation_result.get('thinking', []),
            })
        except Exception as e:
            logger.error(f"Agent 1 failed: {e}")
            mutation_result = {'gene_analyses': [], 'summary': {}, 'chart_data': {}}
            execution_log.append({'agent': 'Mutation Analyst', 'status': 'failed', 'error': str(e), 'thinking': [f'Error: {e}']})

        # ── Agent 2: Pathway Specialist ──
        try:
            pathway_result = self.agents['pathway_specialist'].run(mutations, mutation_result)
            execution_log.append({
                'agent': 'Pathway Specialist', 'status': 'completed',
                'elapsed': pathway_result['elapsed_seconds'],
                'summary': pathway_result.get('summary', {}),
                'thinking': pathway_result.get('thinking', []),
            })
        except Exception as e:
            logger.error(f"Agent 2 failed: {e}")
            pathway_result = {'affected_pathways': [], 'cross_talk': [], 'summary': {}}
            execution_log.append({'agent': 'Pathway Specialist', 'status': 'failed', 'error': str(e), 'thinking': [f'Error: {e}']})

        # ── Agent 3: Drug Strategist ──
        try:
            drug_result = self.agents['drug_strategist'].run(mutations, mutation_result, pathway_result)
            execution_log.append({
                'agent': 'Drug Strategist', 'status': 'completed',
                'elapsed': drug_result['elapsed_seconds'],
                'summary': drug_result.get('summary', {}),
                'thinking': drug_result.get('thinking', []),
            })
        except Exception as e:
            logger.error(f"Agent 3 failed: {e}")
            drug_result = {'ranked_drugs': [], 'top_10': [], 'summary': {}}
            execution_log.append({'agent': 'Drug Strategist', 'status': 'failed', 'error': str(e), 'thinking': [f'Error: {e}']})

        # ── Agent 4: Clinical Advisor ──
        try:
            clinical_result = self.agents['clinical_advisor'].run(
                mutations, mutation_result, pathway_result, drug_result, self.api_key
            )
            execution_log.append({
                'agent': 'Clinical Advisor', 'status': 'completed',
                'elapsed': clinical_result['elapsed_seconds'],
                'gemini_used': clinical_result.get('gemini_used', False),
                'thinking': clinical_result.get('thinking', []),
            })
        except Exception as e:
            logger.error(f"Agent 4 failed: {e}")
            clinical_result = {'human_report': f'Report generation failed: {e}', 'gemini_used': False}
            execution_log.append({'agent': 'Clinical Advisor', 'status': 'failed', 'error': str(e), 'thinking': [f'Error: {e}']})

        pipeline_elapsed = round(time.time() - pipeline_start, 2)
        logger.info(f"Pipeline complete in {pipeline_elapsed}s")

        return {
            'pipeline_status': 'completed',
            'pipeline_elapsed_seconds': pipeline_elapsed,
            'execution_log': execution_log,
            'mutations_analyzed': [m['gene'] for m in mutations],

            # Agent 1 outputs
            'mutation_analysis': {
                'gene_analyses': mutation_result.get('gene_analyses', []),
                'shap_results': mutation_result.get('shap_results', {}),
                'chart_data': mutation_result.get('chart_data', {}),
                'summary': mutation_result.get('summary', {}),
            },

            # Agent 2 outputs
            'pathway_analysis': {
                'affected_pathways': pathway_result.get('affected_pathways', []),
                'cross_talk': pathway_result.get('cross_talk', []),
                'summary': pathway_result.get('summary', {}),
            },

            # Agent 3 outputs
            'drug_strategy': {
                'top_10': drug_result.get('top_10', []),
                'total_evaluated': drug_result.get('summary', {}).get('total_drugs_evaluated', 0),
                'summary': drug_result.get('summary', {}),
            },

            # Agent 4 outputs
            'clinical_report': clinical_result.get('human_report', ''),
            'structured_report': clinical_result.get('structured_report', {}),
            'gemini_used': clinical_result.get('gemini_used', False),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# STANDALONE TEST
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    API_KEY = os.getenv("GEMINI_API_KEY")

    test_mutations = [
        {'gene': 'EGFR', 'vaf': 0.45},
        {'gene': 'TP53', 'vaf': 0.82},
    ]

    pipeline = AgentPipeline(api_key=API_KEY)
    result = pipeline.run(test_mutations)

    print("\n" + "=" * 70)
    print("  AGENT PIPELINE RESULTS")
    print("=" * 70)

    print("\nExecution Log:")
    for entry in result['execution_log']:
        status = '✅' if entry['status'] == 'completed' else '❌'
        elapsed = entry.get('elapsed', '?')
        print(f"  {status} {entry['agent']:25s} ({elapsed}s)")

    print(f"\nTotal pipeline time: {result['pipeline_elapsed_seconds']}s")
    print(f"Gemini used: {'Yes' if result['gemini_used'] else 'No (fallback)'}")

    print("\n" + "=" * 70)
    print("  CLINICAL REPORT")
    print("=" * 70)
    print(result['clinical_report'])
