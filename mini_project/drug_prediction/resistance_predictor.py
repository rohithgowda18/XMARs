"""
Drug Resistance Predictor
==========================
Predicts drug resistance probabilities based on a patient's mutation profile.
Uses the DrugKnowledgeBase to map mutations → pathways → drugs → resistance scores.

Scoring logic (grounded in pharmacogenomics):
  - Direct target mutation: High resistance (0.6–0.85)
    e.g., KRAS G12C mutation → resistance to EGFR inhibitors (bypass signaling)
  - Activating mutation in drug target: Sensitivity indicator (low resistance 0.1–0.3)
    e.g., EGFR mutation → sensitivity to EGFR TKIs like Erlotinib
  - Downstream pathway mutation: Moderate resistance (0.35–0.55)
    e.g., PIK3CA mutation → partial resistance to upstream RTK inhibitors
  - DNA repair deficiency: Increased sensitivity to PARP inhibitors / DNA-damaging agents
  - VAF weighting: Higher VAF → stronger effect on resistance score
"""

import numpy as np
import logging
from typing import List, Dict, Optional
from drug_knowledge_base import get_knowledge_base, DrugKnowledgeBase

logger = logging.getLogger(__name__)

# Evidence-based gene-drug sensitivity/resistance relationships
# Source: Derived from known pharmacogenomic interactions in lung cancer literature
# These map MUTATED GENE → effect on drug category
SENSITIVITY_MARKERS = {
    # Gene mutation INCREASES sensitivity to these drug targets
    'EGFR': {
        'sensitive_targets': ['EGFR'],
        'note': 'Activating EGFR mutations predict response to EGFR TKIs'
    },
    'ALK': {
        'sensitive_targets': ['ALK'],
        'note': 'ALK rearrangements predict response to ALK inhibitors'
    },
    'ROS1': {
        'sensitive_targets': ['ROS1', 'ALK'],
        'note': 'ROS1 fusions predict response to ROS1/ALK inhibitors'
    },
    'RET': {
        'sensitive_targets': ['RET'],
        'note': 'RET fusions predict response to RET inhibitors'
    },
    'BRAF': {
        'sensitive_targets': ['BRAF', 'MEK1/2'],
        'note': 'BRAF V600E predicts response to BRAF/MEK inhibitors'
    },
    'BRCA1': {
        'sensitive_targets': ['PARP'],
        'note': 'BRCA1 loss predicts PARP inhibitor sensitivity'
    },
    'BRCA2': {
        'sensitive_targets': ['PARP'],
        'note': 'BRCA2 loss predicts PARP inhibitor sensitivity'
    },
    'ATM': {
        'sensitive_targets': ['PARP', 'ATR'],
        'note': 'ATM loss predicts sensitivity to PARP/ATR inhibitors'
    },
}

# Bypass resistance: mutation in gene X confers resistance to drugs targeting gene Y
BYPASS_RESISTANCE = {
    'KRAS': {
        'resistant_targets': ['EGFR'],
        'score': 0.80,
        'note': 'KRAS mutations bypass EGFR signaling, conferring resistance to EGFR TKIs'
    },
    'PIK3CA': {
        'resistant_targets': ['EGFR', 'MEK1/2'],
        'score': 0.55,
        'note': 'PIK3CA mutations activate PI3K pathway, reducing EGFR/MEK inhibitor efficacy'
    },
    'PTEN': {
        'resistant_targets': ['EGFR'],
        'score': 0.60,
        'note': 'PTEN loss activates PI3K/AKT, bypassing EGFR blockade'
    },
    'MET': {
        'resistant_targets': ['EGFR'],
        'score': 0.65,
        'note': 'MET amplification bypasses EGFR inhibition'
    },
    'NF1': {
        'resistant_targets': ['EGFR'],
        'score': 0.50,
        'note': 'NF1 loss activates RAS pathway independent of EGFR'
    },
    'RB1': {
        'resistant_targets': ['CDK4/6'],
        'score': 0.85,
        'note': 'RB1 loss removes CDK4/6 inhibitor target dependency'
    },
    'TP53': {
        'resistant_targets': ['MDM2'],
        'score': 0.90,
        'note': 'TP53 mutations remove p53, making MDM2 inhibitors ineffective'
    },
}


class ResistancePredictor:
    """
    Predicts drug resistance and ranks candidate drugs for a mutation profile.
    """

    def __init__(self, kb: DrugKnowledgeBase = None):
        self.kb = kb or get_knowledge_base()

    def predict(self, mutations: List[Dict]) -> Dict:
        """
        Predict drug resistance for a set of mutations.

        Args:
            mutations: List of dicts with keys:
                - gene: str (gene symbol, e.g. 'EGFR')
                - vaf: float (variant allele frequency, 0.0–1.0, optional)

        Returns:
            Dict with:
                - drug_predictions: list of drug prediction dicts sorted by resistance (ascending)
                - affected_pathways: list of affected pathway dicts
                - mutation_summary: summary of input mutations
        """
        mutated_genes = {}
        for mut in mutations:
            gene = mut.get('gene', '').upper().strip()
            vaf = float(mut.get('vaf', 0.5))
            if gene:
                mutated_genes[gene] = vaf

        if not mutated_genes:
            return {'drug_predictions': [], 'affected_pathways': [], 'mutation_summary': {}}

        # Step 1: Identify affected pathways
        affected_pathways = self._get_affected_pathways(mutated_genes)

        # Step 2: Collect candidate drugs
        candidate_drugs = self._collect_candidate_drugs(mutated_genes, affected_pathways)

        # Step 3: Score each drug
        drug_predictions = []
        for drug_name, drug_info in candidate_drugs.items():
            score = self._score_drug(drug_name, drug_info, mutated_genes)
            drug_predictions.append(score)

        # Sort by resistance ascending (most sensitive = best candidates first)
        drug_predictions.sort(key=lambda x: x['resistance_score'])

        # Step 4: Build mutation summary
        mutation_summary = {
            'genes': list(mutated_genes.keys()),
            'gene_count': len(mutated_genes),
            'pathways_affected': len(affected_pathways),
            'drugs_evaluated': len(drug_predictions),
        }

        return {
            'drug_predictions': drug_predictions,
            'affected_pathways': affected_pathways,
            'mutation_summary': mutation_summary,
        }

    def _get_affected_pathways(self, mutated_genes: Dict[str, float]) -> List[Dict]:
        """Identify which pathways are affected by the mutated genes."""
        pathway_hits = {}

        for gene, vaf in mutated_genes.items():
            gene_pathways = self.kb.get_pathways_for_gene(gene)
            for pathway_name, pathway_data in gene_pathways:
                if pathway_name not in pathway_hits:
                    pathway_hits[pathway_name] = {
                        'name': pathway_name,
                        'description': pathway_data.get('description', ''),
                        'cancer_relevance': pathway_data.get('cancer_relevance', ''),
                        'drug_targets': pathway_data.get('drug_targets', []),
                        'mutated_genes': [],
                        'total_genes': len(pathway_data.get('genes', [])),
                        'activation_score': 0.0,
                    }
                pathway_hits[pathway_name]['mutated_genes'].append({
                    'gene': gene,
                    'vaf': vaf,
                })

        # Calculate activation scores
        for pathway_name, pdata in pathway_hits.items():
            n_mutated = len(pdata['mutated_genes'])
            n_total = pdata['total_genes']
            avg_vaf = np.mean([g['vaf'] for g in pdata['mutated_genes']])
            # Activation = fraction of pathway genes mutated, weighted by VAF
            pdata['activation_score'] = round(
                min((n_mutated / max(n_total, 1)) * (0.5 + avg_vaf * 0.5), 1.0), 3
            )

        return sorted(pathway_hits.values(), key=lambda x: x['activation_score'], reverse=True)

    def _collect_candidate_drugs(self, mutated_genes: Dict, affected_pathways: List[Dict]) -> Dict:
        """Collect all drugs that could be relevant based on mutations and pathways."""
        candidates = {}

        # 1. Drugs directly targeting mutated genes
        for gene in mutated_genes:
            for drug in self.kb.get_drugs_targeting_gene(gene):
                name = drug['name']
                if name not in candidates:
                    candidates[name] = {**drug, 'source': 'direct_target', 'source_gene': gene}

        # 2. Drugs targeting the affected pathways
        for pathway in affected_pathways:
            pw_name = pathway['name']
            for drug in self.kb.get_pathway_drugs_for_gene(
                pathway['mutated_genes'][0]['gene'] if pathway['mutated_genes'] else ''
            ):
                name = drug['name']
                if name not in candidates:
                    candidates[name] = {**drug, 'source': 'pathway', 'source_gene': pw_name}

        # 3. Add lung-cancer-relevant drugs from key pathways
        lung_drugs = self.kb.get_lung_cancer_relevant_drugs()
        for drug in lung_drugs:
            name = drug['name']
            if name not in candidates:
                candidates[name] = {**drug, 'source': 'lung_cancer_relevant', 'source_gene': ''}

        return candidates

    def _score_drug(self, drug_name: str, drug_info: Dict, mutated_genes: Dict) -> Dict:
        """
        Score a drug's resistance probability given the mutation profile.
        Lower score = more likely to be effective (sensitive).
        Higher score = more likely to be ineffective (resistant).
        """
        targets = [t.upper().strip() for t in drug_info.get('targets', [])]
        pathway = drug_info.get('pathway', '')
        base_score = 0.5  # Neutral: no evidence either way
        reasoning = []

        # --- Check sensitivity markers ---
        for gene, vaf in mutated_genes.items():
            if gene in SENSITIVITY_MARKERS:
                sensitive_targets = [t.upper() for t in SENSITIVITY_MARKERS[gene]['sensitive_targets']]
                # If drug targets the same gene that's a sensitivity marker
                for target in targets:
                    if target in sensitive_targets:
                        # Mutation makes the tumor dependent on this target → drug is effective
                        sensitivity_boost = 0.3 + vaf * 0.15
                        base_score -= sensitivity_boost
                        reasoning.append(
                            f"{gene} mutation (VAF={vaf:.2f}) predicts sensitivity to {target} inhibitors"
                        )
                        break

        # --- Check bypass resistance ---
        for gene, vaf in mutated_genes.items():
            if gene in BYPASS_RESISTANCE:
                bypass = BYPASS_RESISTANCE[gene]
                resistant_targets = [t.upper() for t in bypass['resistant_targets']]
                for target in targets:
                    if target in resistant_targets:
                        resistance_boost = bypass['score'] * (0.5 + vaf * 0.5)
                        base_score = max(base_score, resistance_boost)
                        reasoning.append(
                            f"{gene} mutation (VAF={vaf:.2f}) confers resistance to {target} "
                            f"inhibitors via bypass signaling"
                        )
                        break

        # --- Check direct target mutations (not in sensitivity markers) ---
        for target in targets:
            if target in mutated_genes and target not in SENSITIVITY_MARKERS:
                vaf = mutated_genes[target]
                base_score += 0.1 * vaf
                reasoning.append(
                    f"Mutation in drug target {target} (VAF={vaf:.2f}) — functional impact uncertain"
                )

        # --- DNA repair deficiency bonus ---
        dna_repair_genes = {'BRCA1', 'BRCA2', 'ATM', 'ATR', 'MLH1', 'MSH2'}
        repair_mutated = dna_repair_genes.intersection(mutated_genes.keys())
        if repair_mutated:
            if pathway in ['Genome integrity', 'DNA replication']:
                bonus = 0.15 * len(repair_mutated)
                base_score -= bonus
                reasoning.append(
                    f"DNA repair deficiency ({', '.join(repair_mutated)}) increases sensitivity "
                    f"to DNA-damaging agents"
                )

        # --- TP53 special handling ---
        if 'TP53' in mutated_genes:
            if pathway == 'p53 pathway':
                # TP53 mutant: p53-reactivation drugs might work, but MDM2 inhibitors won't
                for target in targets:
                    if 'MDM2' in target.upper():
                        base_score = 0.90
                        reasoning = [
                            f"TP53 mutation eliminates p53 protein — MDM2 inhibitors ineffective"
                        ]
                    elif 'TP53' in target.upper() or 'P53' in target.upper():
                        tp53_vaf = mutated_genes['TP53']
                        base_score = 0.25 + (1 - tp53_vaf) * 0.1
                        reasoning.append(
                            f"Drug targets mutant TP53 directly — potential efficacy"
                        )

        # Clamp score to [0.05, 0.95]
        final_score = round(max(0.05, min(0.95, base_score)), 3)

        # Classify
        if final_score <= 0.30:
            category = 'Likely Sensitive'
            category_color = '#22c55e'
        elif final_score <= 0.50:
            category = 'Potentially Sensitive'
            category_color = '#84cc16'
        elif final_score <= 0.65:
            category = 'Uncertain'
            category_color = '#eab308'
        elif final_score <= 0.80:
            category = 'Potentially Resistant'
            category_color = '#f97316'
        else:
            category = 'Likely Resistant'
            category_color = '#ef4444'

        if not reasoning:
            reasoning.append(f"No direct mutation-drug interaction evidence found — scored as neutral")

        return {
            'drug_name': drug_name,
            'targets': drug_info.get('targets_raw', ''),
            'pathway': pathway,
            'resistance_score': final_score,
            'sensitivity_score': round(1.0 - final_score, 3),
            'category': category,
            'category_color': category_color,
            'reasoning': reasoning,
            'source': drug_info.get('source', ''),
        }


def predict_resistance(mutations: List[Dict]) -> Dict:
    """
    Convenience function for quick predictions.

    Args:
        mutations: [{'gene': 'EGFR', 'vaf': 0.45}, {'gene': 'TP53', 'vaf': 0.82}]

    Returns:
        Full prediction result dict
    """
    predictor = ResistancePredictor()
    return predictor.predict(mutations)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

    # Example: Patient with EGFR, TP53, KRAS mutations
    test_mutations = [
        {'gene': 'EGFR', 'vaf': 0.45},
        {'gene': 'TP53', 'vaf': 0.82},
        {'gene': 'KRAS', 'vaf': 0.35},
    ]

    print("\n" + "=" * 70)
    print("DRUG RESISTANCE PREDICTION TEST")
    print("=" * 70)
    print(f"\nInput mutations: {test_mutations}")

    result = predict_resistance(test_mutations)

    print(f"\nAffected pathways: {len(result['affected_pathways'])}")
    for pw in result['affected_pathways']:
        print(f"  {pw['name']}: activation={pw['activation_score']:.3f}, "
              f"mutated genes: {[g['gene'] for g in pw['mutated_genes']]}")

    print(f"\nDrug predictions (top 10 most sensitive):")
    for i, pred in enumerate(result['drug_predictions'][:10], 1):
        print(f"  {i:2d}. {pred['drug_name']:25s} "
              f"resistance={pred['resistance_score']:.3f} "
              f"[{pred['category']}]")
        for r in pred['reasoning']:
            print(f"      → {r}")

    print(f"\nTotal drugs evaluated: {result['mutation_summary']['drugs_evaluated']}")
