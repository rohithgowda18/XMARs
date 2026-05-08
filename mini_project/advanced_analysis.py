"""
Advanced Analysis: Mutation Pathways, Gene Networks, and Drug Response
This script performs detailed analysis on preprocessed genomic data
"""

import pandas as pd
import numpy as np
from pathlib import Path
import logging
from collections import Counter, defaultdict
import json

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# SECTION 1: SETUP AND CONFIGURATION
# ============================================================================

DATA_DIR = Path(__file__).parent / 'data'
PROCESSED_DIR = DATA_DIR / 'processed'
RAW_DIR = DATA_DIR / 'raw'

# Pathway and Gene Databases (can be expanded with KEGG/Reactome data)
CANCER_PATHWAYS = {
    'EGFR_SIGNALING': {
        'genes': ['EGFR', 'KRAS', 'PTEN', 'TP53', 'PIK3CA', 'BRAF'],
        'description': 'EGFR-mediated growth signaling pathway',
        'cancer_relevance': 'High',
        'drug_targets': ['EGFR', 'BRAF', 'MEK1/2']
    },
    'TP53_APOPTOSIS': {
        'genes': ['TP53', 'MDM2', 'BAX', 'PUMA', 'NOXA', 'ATM'],
        'description': 'p53-mediated apoptosis and cell cycle control',
        'cancer_relevance': 'High',
        'drug_targets': ['MDM2']
    },
    'PI3K_AKT_MTOR': {
        'genes': ['PIK3CA', 'AKT1', 'AKT2', 'PTEN', 'mTOR', 'TSC1', 'TSC2'],
        'description': 'Growth and survival signaling pathway',
        'cancer_relevance': 'High',
        'drug_targets': ['PI3K', 'AKT', 'mTOR']
    },
    'MAPK_ERK': {
        'genes': ['KRAS', 'BRAF', 'MEK1', 'MEK2', 'ERK1', 'ERK2', 'RAF1'],
        'description': 'MAPK cascade for proliferation',
        'cancer_relevance': 'High',
        'drug_targets': ['BRAF', 'MEK1/2']
    },
    'CELL_CYCLE': {
        'genes': ['RB1', 'CDK4', 'CDK6', 'CDKN2A', 'CDKN2B', 'E2F1', 'CCND1'],
        'description': 'Cell cycle checkpoint control',
        'cancer_relevance': 'High',
        'drug_targets': ['CDK4/6']
    },
    'WNT_SIGNALING': {
        'genes': ['APC', 'CTNNB1', 'GSK3B', 'AXIN1', 'TCF7L2', 'WNT'],
        'description': 'Wnt pathway for cell differentiation',
        'cancer_relevance': 'Medium',
        'drug_targets': ['Tankyrase', 'PORCN']
    },
    'RAS_PATHWAY': {
        'genes': ['KRAS', 'NRAS', 'HRAS', 'NF1', 'SPRED1', 'CBL'],
        'description': 'RAS activation and negative regulation',
        'cancer_relevance': 'High',
        'drug_targets': ['KRAS', 'MEK']
    },
    'DNA_REPAIR': {
        'genes': ['BRCA1', 'BRCA2', 'MLH1', 'MSH2', 'XRCC1', 'ATM', 'ATR'],
        'description': 'DNA damage response and repair',
        'cancer_relevance': 'High',
        'drug_targets': ['PARP']
    }
}

# ============================================================================
# SECTION 2: DATA LOADING
# ============================================================================

def load_preprocessed_data():
    """Load all preprocessed data"""
    logger.info("Loading preprocessed data...")
    
    models = pd.read_csv(PROCESSED_DIR / '01_models_preprocessed.csv')
    cnv = pd.read_csv(PROCESSED_DIR / '02_cnv_preprocessed.csv')
    mutations_features = pd.read_csv(PROCESSED_DIR / 'mutation_features.csv')
    
    logger.info(f"Loaded {len(models)} models, {len(cnv)} CNV records, {len(mutations_features)} mutation features")
    
    return models, cnv, mutations_features

# ============================================================================
# SECTION 3: MUTATION ANALYSIS
# ============================================================================

def analyze_driver_mutations():
    """Analyze cancer driver mutations"""
    logger.info("\n" + "="*70)
    logger.info("MUTATION ANALYSIS: DRIVER GENES")
    logger.info("="*70)
    
    mutations = pd.read_csv(RAW_DIR / 'mutations_all.csv', nrows=500000)
    
    # Identify driver mutations
    driver_muts = mutations[mutations.get('cancer_driver', False) == True]
    
    print(f"\nTotal Mutations (sample): {len(mutations)}")
    print(f"Driver Mutations (sample): {len(driver_muts)} ({100*len(driver_muts)/len(mutations):.2f}%)")
    
    # Top mutated genes
    print(f"\nTop 20 Most Mutated Genes:")
    gene_counts = mutations['gene_symbol'].value_counts().head(20)
    for i, (gene, count) in enumerate(gene_counts.items(), 1):
        print(f"  {i:2d}. {gene:15s} {count:6d} mutations")
    
    # Mutation types distribution
    if 'effect' in mutations.columns:
        print(f"\nMutation Effect Types Distribution:")
        effect_counts = mutations['effect'].value_counts()
        for effect, count in effect_counts.head(10).items():
            print(f"  {effect:20s} {count:8d} ({100*count/len(mutations):5.2f}%)")
    
    return mutations, driver_muts

def analyze_pathway_mutations(mutations_features):
    """Analyze mutations in cancer pathway genes"""
    logger.info("\n" + "="*70)
    logger.info("PATHWAY ANALYSIS: MUTATION DISTRIBUTION")
    logger.info("="*70)
    
    pathway_mutation_counts = {}
    
    for pathway_name, pathway_info in CANCER_PATHWAYS.items():
        genes = pathway_info['genes']
        
        # Count mutations in pathway genes
        pathway_muts = mutations_features[
            mutations_features['gene_symbol'].isin(genes)
        ]
        
        pathway_mutation_counts[pathway_name] = {
            'total_mutations': len(pathway_muts),
            'genes_mutated': pathway_muts['gene_symbol'].nunique(),
            'models_affected': pathway_muts['model_name'].nunique(),
            'avg_mutations_per_model': len(pathway_muts) / max(pathway_muts['model_name'].nunique(), 1)
        }
    
    print(f"\nPathway Mutation Summary:")
    print(f"{'Pathway':<30} {'Mutations':<12} {'Genes':<10} {'Models':<10} {'Avg/Model':<10}")
    print("-" * 72)
    
    for pathway, stats in sorted(
        pathway_mutation_counts.items(),
        key=lambda x: x[1]['total_mutations'],
        reverse=True
    ):
        print(f"{pathway:<30} {stats['total_mutations']:<12} {stats['genes_mutated']:<10} "
              f"{stats['models_affected']:<10} {stats['avg_mutations_per_model']:<10.2f}")
    
    return pathway_mutation_counts

def analyze_co_mutations(mutations_features, top_genes=15):
    """Analyze co-occurring mutations (genes mutated together)"""
    logger.info("\n" + "="*70)
    logger.info("CO-MUTATION ANALYSIS")
    logger.info("="*70)
    
    # Get top mutated genes
    top_genes_list = mutations_features['gene_symbol'].value_counts().head(top_genes).index.tolist()
    
    # For each model, identify which genes are mutated together
    co_mutation_pairs = defaultdict(int)
    
    for model in mutations_features['model_name'].unique():
        model_muts = mutations_features[mutations_features['model_name'] == model]
        mutated_genes = set(model_muts['gene_symbol'].unique()) & set(top_genes_list)
        
        # Count all gene pairs
        genes_list = list(mutated_genes)
        for i, gene1 in enumerate(genes_list):
            for gene2 in genes_list[i+1:]:
                pair = tuple(sorted([gene1, gene2]))
                co_mutation_pairs[pair] += 1
    
    print(f"\nTop 20 Co-Mutated Gene Pairs:")
    print(f"{'Gene 1':<15} {'Gene 2':<15} {'Co-mutations':<15}")
    print("-" * 45)
    
    for i, (pair, count) in enumerate(sorted(
        co_mutation_pairs.items(),
        key=lambda x: x[1],
        reverse=True
    )[:20], 1):
        print(f"{pair[0]:<15} {pair[1]:<15} {count:<15}")
    
    return co_mutation_pairs

# ============================================================================
# SECTION 4: PATHWAY ACTIVATION ANALYSIS
# ============================================================================

def calculate_pathway_activation_scores(mutations_features):
    """Calculate pathway activation scores for each model"""
    logger.info("\n" + "="*70)
    logger.info("PATHWAY ACTIVATION SCORING")
    logger.info("="*70)
    
    pathway_scores = {}
    model_pathway_profiles = []
    
    for pathway_name, pathway_info in CANCER_PATHWAYS.items():
        genes = pathway_info['genes']
        
        # Group by model
        model_scores = {}
        
        for model in mutations_features['model_name'].unique():
            model_data = mutations_features[mutations_features['model_name'] == model]
            
            # Count mutated genes in pathway
            mutated_genes = model_data[model_data['gene_symbol'].isin(genes)]
            
            # Calculate pathway activation score (0-1)
            # Based on: number of genes mutated / total genes in pathway
            # Weighted by mutation frequency
            gene_count = mutated_genes['gene_symbol'].nunique() if len(mutated_genes) > 0 else 0
            total_genes = len(genes)
            
            # Score: proportion of genes mutated + frequency factor
            base_score = gene_count / total_genes
            mutation_freq = len(mutated_genes) / max(len(model_data), 1)
            
            # Combined score
            activation_score = (base_score + mutation_freq) / 2
            model_scores[model] = min(activation_score, 1.0)
        
        pathway_scores[pathway_name] = model_scores
        
        # Calculate statistics
        scores = list(model_scores.values())
        active_models = sum(1 for s in scores if s > 0.3)
        
        print(f"\n{pathway_name}:")
        print(f"  Avg Activation: {np.mean(scores):.3f}")
        print(f"  Max Activation: {np.max(scores):.3f}")
        print(f"  Models Active (>0.3): {active_models}/{len(scores)} ({100*active_models/len(scores):.1f}%)")
    
    return pathway_scores

# ============================================================================
# SECTION 5: CNV ANALYSIS
# ============================================================================

def analyze_cnv_patterns(cnv_df):
    """Analyze copy number variation patterns"""
    logger.info("\n" + "="*70)
    logger.info("COPY NUMBER VARIATION ANALYSIS")
    logger.info("="*70)
    
    print(f"\nCNV Category Distribution:")
    category_counts = cnv_df['cn_category'].value_counts()
    for category, count in category_counts.items():
        print(f"  {category:15s} {count:8d} ({100*count/len(cnv_df):6.2f}%)")
    
    print(f"\nGenes with Frequent Amplifications:")
    amp_genes = cnv_df[cnv_df['cn_category'] == 'Amplification']['symbol'].value_counts().head(10)
    for gene, count in amp_genes.items():
        print(f"  {gene:15s} {count:3d} models")
    
    print(f"\nGenes with Frequent Deletions:")
    del_genes = cnv_df[cnv_df['cn_category'] == 'Deletion']['symbol'].value_counts().head(10)
    for gene, count in del_genes.items():
        print(f"  {gene:15s} {count:3d} models")
    
    # Models with high CNV burden
    cnv_burden = cnv_df.groupby('model_name').agg({
        'cn_category': 'count',
        'total_copy_number': ['mean', 'max']
    }).round(2)
    cnv_burden.columns = ['total_cnvs', 'avg_copy_number', 'max_copy_number']
    cnv_burden = cnv_burden.sort_values('total_cnvs', ascending=False)
    
    print(f"\nModels with Highest CNV Burden (Top 10):")
    print(cnv_burden.head(10).to_string())
    
    return cnv_burden

# ============================================================================
# SECTION 6: CANCER TYPE ANALYSIS
# ============================================================================

def analyze_by_cancer_type(models_df, mutations_features):
    """Analyze mutations and pathways by cancer type"""
    logger.info("\n" + "="*70)
    logger.info("CANCER TYPE-SPECIFIC ANALYSIS")
    logger.info("="*70)
    
    cancer_analysis = {}
    
    for cancer_type in models_df['cancer_type'].value_counts().head(5).index:
        cancer_models = models_df[models_df['cancer_type'] == cancer_type]['model_name'].tolist()
        cancer_muts = mutations_features[mutations_features['model_name'].isin(cancer_models)]
        
        top_genes = cancer_muts['gene_symbol'].value_counts().head(10)
        
        cancer_analysis[cancer_type] = {
            'models': len(cancer_models),
            'mutations': len(cancer_muts),
            'unique_genes': cancer_muts['gene_symbol'].nunique(),
            'top_genes': top_genes.to_dict()
        }
        
        print(f"\n{cancer_type}:")
        print(f"  Models: {len(cancer_models)}")
        print(f"  Total Mutations: {len(cancer_muts)}")
        print(f"  Unique Genes: {cancer_muts['gene_symbol'].nunique()}")
        print(f"  Top 5 Mutated Genes: {', '.join(top_genes.head(5).index.tolist())}")
    
    return cancer_analysis

# ============================================================================
# SECTION 7: SUMMARY STATISTICS
# ============================================================================

def generate_analysis_summary():
    """Generate comprehensive analysis summary"""
    logger.info("\n" + "="*70)
    logger.info("COMPREHENSIVE ANALYSIS SUMMARY")
    logger.info("="*70)
    
    # Load data
    models, cnv, mutations_features = load_preprocessed_data()
    
    # Run analyses
    print("\n" + "="*70)
    mutations, driver_muts = analyze_driver_mutations()
    
    print("\n" + "="*70)
    pathway_muts = analyze_pathway_mutations(mutations_features)
    
    print("\n" + "="*70)
    co_muts = analyze_co_mutations(mutations_features)
    
    print("\n" + "="*70)
    pathway_scores = calculate_pathway_activation_scores(mutations_features)
    
    print("\n" + "="*70)
    cnv_burden = analyze_cnv_patterns(cnv)
    
    print("\n" + "="*70)
    cancer_analysis = analyze_by_cancer_type(models, mutations_features)
    
    # Summary output
    print("\n" + "="*70)
    print("KEY FINDINGS")
    print("="*70)
    
    print(f"\n(1) MUTATION BURDEN:")
    print(f"    - Total unique genes: {mutations_features['gene_symbol'].nunique()}")
    print(f"    - Total mutations: {len(mutations_features)}")
    print(f"    - Models analyzed: {mutations_features['model_name'].nunique()}")
    
    print(f"\n(2) PATHWAY ALTERATIONS:")
    print(f"    - Cancer pathways analyzed: {len(CANCER_PATHWAYS)}")
    print(f"    - Most affected pathway: {max(pathway_muts, key=lambda x: pathway_muts[x]['total_mutations'])}")
    
    print(f"\n(3) CNV PATTERNS:")
    print(f"    - Total CNV records: {len(cnv)}")
    print(f"    - Models with CNV data: {cnv['model_name'].nunique()}")
    print(f"    - Top CNV category: Neutral ({sum(cnv['cn_category']=='Neutral')}/{len(cnv)})")
    
    print(f"\n(4) CANCER TYPES:")
    print(f"    - Types analyzed: {len(cancer_analysis)}")
    print(f"    - Most common type: {models['cancer_type'].value_counts().index[0]}")
    
    return {
        'models': models,
        'cnv': cnv,
        'mutations_features': mutations_features,
        'pathway_scores': pathway_scores,
        'cancer_analysis': cancer_analysis
    }

# ============================================================================
# SECTION 8: EXPORT RESULTS
# ============================================================================

def save_analysis_results(results_dict):
    """Save analysis results to files"""
    logger.info("\n" + "="*70)
    logger.info("SAVING ANALYSIS RESULTS")
    logger.info("="*70)
    
    # Save pathway information
    pathway_info_list = []
    for pathway_name, pathway_data in CANCER_PATHWAYS.items():
        pathway_info_list.append({
            'pathway_name': pathway_name,
            'genes': ','.join(pathway_data['genes']),
            'description': pathway_data['description'],
            'cancer_relevance': pathway_data['cancer_relevance'],
            'drug_targets': ','.join(pathway_data['drug_targets'])
        })
    
    pathway_df = pd.DataFrame(pathway_info_list)
    pathway_df.to_csv(PROCESSED_DIR / '05_cancer_pathways.csv', index=False)
    logger.info("[OK] Saved cancer pathways to 05_cancer_pathways.csv")
    
    # Save pathway reference
    with open(PROCESSED_DIR / 'pathway_reference.json', 'w') as f:
        json.dump(CANCER_PATHWAYS, f, indent=2)
    logger.info("[OK] Saved pathway reference to pathway_reference.json")
    
    logger.info("\n[OK] All analysis results saved successfully!")

# ============================================================================
# SECTION 9: MAIN EXECUTION
# ============================================================================

def main():
    """Main analysis execution"""
    print("\n" + "="*70)
    print("ADVANCED GENOMIC ANALYSIS: MUTATIONS, PATHWAYS & DRUG RESPONSE")
    print("="*70)
    
    try:
        # Run comprehensive analysis
        results = generate_analysis_summary()
        
        # Save results
        save_analysis_results(results)
        
        print("\n" + "="*70)
        print("[OK] ANALYSIS COMPLETED SUCCESSFULLY!")
        print("="*70)
        
    except Exception as e:
        logger.error(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    main()
