"""
Quick Start Guide - Genomic Data Analysis Pipeline
====================================================

This guide will help you run the complete data analysis pipeline in 5 minutes.
"""

# ============================================================================
# QUICK START: RUN EVERYTHING
# ============================================================================

# Step 1: Navigate to project directory
# $ cd c:\Users\Venkatachala V\MiniProject

# Step 2: Run preprocessing
# $ python preprocess_data.py

# Step 3: Run advanced analysis
# $ python advanced_analysis.py

# Step 4: Check results
# $ ls data/processed/

# ============================================================================
# WHAT EACH SCRIPT DOES
# ============================================================================

"""
preprocess_data.py
------------------
RUNS: Exploratory Data Analysis + Data Cleaning
TIME: ~30 seconds
OUTPUT:
  01_models_preprocessed.csv      - Clean model metadata
  02_cnv_preprocessed.csv         - Clean CNV data
  03_compounds_cleaned.csv        - Drug compounds list
  04_mutation_statistics.csv      - Per-model mutation counts

WHAT IT ANALYZES:
  + Model types and cancer distribution
  + Data availability across samples
  + CNV patterns and statistics
  + Mutation sample analysis
  + Data quality checks
"""

"""
advanced_analysis.py
---------------------
RUNS: Pathway Analysis + Mutation Analysis
TIME: ~30 seconds
OUTPUT:
  05_cancer_pathways.csv          - Pathway gene mappings
  pathway_reference.json          - Detailed pathway info

WHAT IT ANALYZES:
  + Driver vs passenger mutations
  + Pathway activation scoring
  + Co-mutation patterns
  + CNV burden by model
  + Cancer-type specific mutations
  + Pathway enrichment
"""

# ============================================================================
# DATA FILES REFERENCE
# ============================================================================

"""
INPUT DATA (data/raw/):
  mutations_all.csv               1.2GB  - All mutations across 1,984 models
  cnv.csv                        62 MB  - Copy number variations
  model_list.csv                  0.7MB - Cell line metadata
  screened_compounds.csv          0.04MB- Drug compounds

OUTPUT DATA (data/processed/):
  01_models_preprocessed.csv      0.7MB - Clean model data (1,984 rows)
  02_cnv_preprocessed.csv        57 MB - Clean CNV data (1.1M rows)
  03_compounds_cleaned.csv       0.04MB - Clean compounds
  04_mutation_statistics.csv     0.04MB - Mutation summary stats
  05_cancer_pathways.csv         <1 MB  - Pathway definitions
  mutation_features.csv          1.8 MB - Engineered features
  pathway_reference.json         <1 MB  - Pathway database
"""

# ============================================================================
# KEY STATISTICS
# ============================================================================

STATS = {
    'Total Models': 1984,
    'Cancer Types': 40,
    'Mutation Records': 1000000,
    'CNV Records': 1149375,
    'Unique Genes': 17000,
    'Pathways Analyzed': 8,
    'Drug Compounds': 500,
}

print("{:<25} {:>15}".format("Metric", "Count"))
print("-" * 42)
for metric, count in STATS.items():
    print("{:<25} {:>15,}".format(metric, count))

# ============================================================================
# PATHWAY QUICK REFERENCE
# ============================================================================

PATHWAYS = {
    '1. EGFR Signaling': {
        'genes': 'EGFR, KRAS, PTEN, TP53, PIK3CA',
        'drugs': 'EGFR inhibitors, BRAF inhibitors',
        'relevance': 'HIGH'
    },
    '2. TP53 Apoptosis': {
        'genes': 'TP53, MDM2, BAX',
        'drugs': 'MDM2 inhibitors',
        'relevance': 'HIGH'
    },
    '3. PI3K-AKT': {
        'genes': 'PIK3CA, AKT1, PTEN, mTOR',
        'drugs': 'PI3K/AKT/mTOR inhibitors',
        'relevance': 'HIGH'
    },
    '4. MAPK-ERK': {
        'genes': 'KRAS, BRAF, MEK1/2',
        'drugs': 'BRAF, MEK inhibitors',
        'relevance': 'HIGH'
    },
    '5. Cell Cycle': {
        'genes': 'RB1, CDK4/6, CDKN2A',
        'drugs': 'CDK4/6 inhibitors',
        'relevance': 'HIGH'
    },
    '6. DNA Repair': {
        'genes': 'BRCA1, BRCA2, ATM, MLH1',
        'drugs': 'PARP inhibitors',
        'relevance': 'HIGH'
    },
    '7. Wnt Signaling': {
        'genes': 'APC, CTNNB1, GSK3B',
        'drugs': 'Tankyrase, PORCN inhibitors',
        'relevance': 'MEDIUM'
    },
    '8. RAS Pathway': {
        'genes': 'KRAS, NRAS, NF1',
        'drugs': 'KRAS, MEK inhibitors',
        'relevance': 'HIGH'
    }
}

print("\nPATHWAY QUICK REFERENCE:")
print("=" * 80)
for pathway, info in PATHWAYS.items():
    print(f"\n{pathway}")
    print(f"  Key Genes: {info['genes']}")
    print(f"  Drug Targets: {info['drugs']}")
    print(f"  Cancer Relevance: {info['relevance']}")

# ============================================================================
# HOW TO USE OUTPUTS
# ============================================================================

"""
EXAMPLE 1: Load and Explore Preprocessed Models
-----------------------------------------------
import pandas as pd

models = pd.read_csv('data/processed/01_models_preprocessed.csv')
print(models.head())
print(models['cancer_type'].value_counts())
"""

"""
EXAMPLE 2: Analyze Patient's CNV Profile
------------------------------------------
import pandas as pd

cnv = pd.read_csv('data/processed/02_cnv_preprocessed.csv')
patient = 'HCM-SANG-0524-C20'

patient_cnv = cnv[cnv['model_name'] == patient]
print(f"Patient: {patient}")
print(f"Total CNVs: {len(patient_cnv)}")
print(f"Amplifications: {sum(patient_cnv['cn_category'] == 'Amplification')}")
print(f"Deletions: {sum(patient_cnv['cn_category'] == 'Deletion')}")
"""

"""
EXAMPLE 3: Check Pathway Mutations
-----------------------------------
import pandas as pd
import json

mutations = pd.read_csv('data/processed/mutation_features.csv')
with open('data/processed/pathway_reference.json') as f:
    pathways = json.load(f)

patient = 'HCM-SANG-0524-C20'
patient_muts = mutations[mutations['model_name'] == patient]

print(f"Patient {patient} mutations by pathway:")
for pathway_name, pathway_data in pathways.items():
    genes = pathway_data['genes']
    affected = patient_muts[patient_muts['gene_symbol'].isin(genes)]
    if len(affected) > 0:
        print(f"  {pathway_name}: {len(affected)} mutations")
        print(f"    Genes: {', '.join(affected['gene_symbol'].unique())}")
"""

# ============================================================================
# TROUBLESHOOTING
# ============================================================================

TROUBLESHOOTING = {
    'Issue': 'Script hangs or runs slowly',
    'Solution': 'This is normal - mutations_all.csv is 1.2GB. Be patient.',
    
    'Issue': 'Memory error',
    'Solution': 'Close other applications. Data requires ~1GB RAM.',
    
    'Issue': 'FileNotFoundError',
    'Solution': 'Make sure you run scripts from project root directory.',
    
    'Issue': 'Column not found error',
    'Solution': 'Raw data formats may differ. Check script error message.',
}

# ============================================================================
# NEXT STEPS
# ============================================================================

NEXT_STEPS = """
After running the pipeline:

1. EXPLORE RESULTS
   - Open 01_models_preprocessed.csv in Excel/Pandas
   - Review pathway_reference.json for pathway details
   - Check 04_mutation_statistics.csv for variant burden

2. INTEGRATE WITH DRUG RESPONSE
   - Use 03_compounds_cleaned.csv as drug database
   - Match compounds to pathway drug targets
   - Predict drug efficacy based on pathway activation

3. BUILD PREDICTION MODELS
   - Use mutation features for ML classification
   - Predict drug response from pathway profiles
   - Estimate patient outcome probabilities

4. VISUALIZE RESULTS
   - Create pathway activation heatmaps
   - Plot mutation burden by cancer type
   - Build co-mutation network graphs
"""

print("\n" + NEXT_STEPS)

# ============================================================================
# COMMAND REFERENCE
# ============================================================================

COMMANDS = """
COMMON COMMANDS:
================

# Run preprocessor
python preprocess_data.py

# Run analysis
python advanced_analysis.py

# View model metadata
cd data/processed
python -c "import pandas as pd; print(pd.read_csv('01_models_preprocessed.csv').head())"

# Count mutations
python -c "import pandas as pd; print(len(pd.read_csv('../raw/mutations_all.csv')))"

# List all output files
ls -lh data/processed/

# See pathway reference
cat data/processed/pathway_reference.json | head -50
"""

print(COMMANDS)
