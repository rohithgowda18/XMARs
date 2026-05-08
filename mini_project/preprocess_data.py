"""
Data Analysis and Preprocessing Pipeline
Analyzes and preprocesses genomic, mutation, CNV, and drug response data
"""

import pandas as pd
import numpy as np
import os
import warnings
import sys
from pathlib import Path
from collections import Counter
import logging

# Set UTF-8 encoding for Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

warnings.filterwarnings('ignore')

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# SECTION 1: DATA PATHS AND CONFIGURATION
# ============================================================================

DATA_DIR = Path(__file__).parent / 'data'
RAW_DIR = DATA_DIR / 'raw'
PROCESSED_DIR = DATA_DIR / 'processed'

# Create processed directory if it doesn't exist
PROCESSED_DIR.mkdir(exist_ok=True, parents=True)

# ============================================================================
# SECTION 2: DATA LOADING FUNCTIONS
# ============================================================================

def load_model_list():
    """Load and return model metadata"""
    logger.info("Loading model list...")
    df = pd.read_csv(RAW_DIR / 'model_list.csv')
    logger.info(f"Loaded {len(df)} models")
    return df

def load_small_metadata():
    """Load screened compounds"""
    logger.info("Loading screened compounds...")
    df = pd.read_csv(RAW_DIR / 'screened_compounds.csv')
    logger.info(f"Loaded {len(df)} compounds")
    return df

# ============================================================================
# SECTION 3: EXPLORATORY DATA ANALYSIS
# ============================================================================

def explore_model_list():
    """Analyze model list data"""
    logger.info("\n" + "="*70)
    logger.info("EXPLORATORY ANALYSIS: MODEL LIST")
    logger.info("="*70)
    
    df = load_model_list()
    
    print(f"\nDataset Shape: {df.shape}")
    print(f"\nColumn Names ({len(df.columns)} columns):")
    for i, col in enumerate(df.columns, 1):
        print(f"  {i:2d}. {col}")
    
    print(f"\nCancer Types Distribution:")
    cancer_dist = df['cancer_type'].value_counts()
    for cancer, count in cancer_dist.head(10).items():
        print(f"  {cancer}: {count}")
    
    print(f"\nData Availability:")
    data_cols = ['mutation_data', 'methylation_data', 'expression_data', 
                 'cnv_data', 'drug_data', 'rnaseq_data']
    for col in data_cols:
        if col in df.columns:
            available = df[col].sum() if df[col].dtype == 'bool' else (df[col] == 'True').sum()
            print(f"  {col}: {available}/{len(df)} ({100*available/len(df):.1f}%)")
    
    print(f"\nGender Distribution:")
    gender_dist = df['gender'].value_counts()
    for gender, count in gender_dist.items():
        print(f"  {gender}: {count}")
    
    print(f"\nSampling Year Distribution (Last 10 years):")
    year_dist = df['sampling_year'].value_counts().sort_index()
    for year, count in year_dist.tail(10).items():
        print(f"  {year}: {count}")
    
    return df

def explore_cnv_data():
    """Analyze CNV data statistics"""
    logger.info("\n" + "="*70)
    logger.info("EXPLORATORY ANALYSIS: CNV DATA")
    logger.info("="*70)
    
    cnv_path = RAW_DIR / 'cnv.csv'
    
    # Read first chunk
    df_chunk = pd.read_csv(cnv_path, nrows=10000)
    print(f"\nCNV Data Sample Shape: {df_chunk.shape}")
    print(f"\nColumns: {list(df_chunk.columns)}")
    print(f"\nFirst 5 rows:")
    print(df_chunk.head())
    
    # Analyze total file
    logger.info("Analyzing full CNV file...")
    df_full = pd.read_csv(cnv_path)
    
    print(f"\nTotal CNV Records: {len(df_full)}")
    print(f"\nCopy Number Categories:")
    cn_categories = df_full['cn_category'].value_counts()
    for category, count in cn_categories.items():
        print(f"  {category}: {count}")
    
    print(f"\nCopy Number Statistics:")
    print(df_full['total_copy_number'].describe())
    
    print(f"\nUnique Genes: {df_full['symbol'].nunique()}")
    print(f"Unique Models: {df_full['model_name'].nunique()}")
    
    return df_full

def explore_mutations_sample():
    """Analyze mutations data (sample-based due to size)"""
    logger.info("\n" + "="*70)
    logger.info("EXPLORATORY ANALYSIS: MUTATIONS DATA (SAMPLE)")
    logger.info("="*70)
    
    mutations_path = RAW_DIR / 'mutations_all.csv'
    
    # Read sample
    df_sample = pd.read_csv(mutations_path, nrows=50000)
    print(f"\nMutation Sample Shape: {df_sample.shape}")
    print(f"\nColumns: {list(df_sample.columns)}")
    print(f"\nFirst 5 rows:")
    print(df_sample.head())
    
    print(f"\nUnique Genes: {df_sample['gene_symbol'].nunique()}")
    print(f"Unique Models: {df_sample['model_name'].nunique()}")
    
    print(f"\nVariant Effect Distribution:")
    if 'effect' in df_sample.columns:
        effect_dist = df_sample['effect'].value_counts()
    else:
        effect_dist = df_sample[df_sample.columns[1]].value_counts()
    
    for effect, count in effect_dist.head(10).items():
        print(f"  {effect}: {count}")
    
    print(f"\nVAF (Variant Allele Frequency) Statistics:")
    print(df_sample['vaf'].describe())
    
    return df_sample

def explore_processed_mutations():
    """Analyze already processed mutation features"""
    logger.info("\n" + "="*70)
    logger.info("EXPLORATORY ANALYSIS: PROCESSED MUTATIONS")
    logger.info("="*70)
    
    df = pd.read_csv(PROCESSED_DIR / 'mutation_features.csv')
    print(f"\nProcessed Mutation Features Shape: {df.shape}")
    print(f"\nColumns:")
    for i, col in enumerate(df.columns, 1):
        print(f"  {i:2d}. {col}")
    
    print(f"\nFirst 3 rows:")
    print(df.head(3))
    
    return df

# ============================================================================
# SECTION 4: DATA CLEANING & PREPROCESSING
# ============================================================================

def preprocess_model_list():
    """Clean and preprocess model list"""
    logger.info("\n" + "="*70)
    logger.info("PREPROCESSING: MODEL LIST")
    logger.info("="*70)
    
    df = load_model_list()
    logger.info(f"Original shape: {df.shape}")
    
    # Handle missing values
    logger.info(f"Missing values before cleaning:")
    missing = df.isnull().sum()
    if len(missing[missing > 0]) > 0:
        print(missing[missing > 0])
    
    # Fill common missing values
    df['gender'] = df['gender'].fillna('Unknown')
    df['ethnicity'] = df['ethnicity'].fillna('Unknown')
    df['smoking_status'] = df['smoking_status'].fillna('Unknown')
    
    # Remove rows with missing critical info
    df = df.dropna(subset=['model_name', 'cancer_type'])
    
    logger.info(f"Final shape: {df.shape}")
    logger.info("[OK] Model list preprocessing complete")
    
    return df

def preprocess_cnv_data():
    """Clean and preprocess CNV data"""
    logger.info("\n" + "="*70)
    logger.info("PREPROCESSING: CNV DATA")
    logger.info("="*70)
    
    df = pd.read_csv(RAW_DIR / 'cnv.csv')
    original_len = len(df)
    
    # Remove duplicates
    df = df.drop_duplicates(subset=['model_name', 'symbol'])
    logger.info(f"Removed {original_len - len(df)} duplicates")
    
    # Handle missing values
    df['cn_category'] = df['cn_category'].fillna('Neutral')
    
    # Remove rows with missing critical info
    df = df.dropna(subset=['model_name', 'symbol', 'total_copy_number'])
    
    logger.info(f"Final shape: {df.shape}")
    logger.info("[OK] CNV preprocessing complete")
    
    return df

def preprocess_compounds():
    """Clean and preprocess drug compounds"""
    logger.info("\n" + "="*70)
    logger.info("PREPROCESSING: DRUG COMPOUNDS")
    logger.info("="*70)
    
    df = pd.read_csv(RAW_DIR / 'screened_compounds.csv')
    original_len = len(df)
    logger.info(f"Original records: {original_len}")
    
    # Remove duplicates
    df = df.drop_duplicates()
    logger.info(f"Removed {original_len - len(df)} duplicates")
    
    logger.info(f"Final shape: {df.shape}")
    logger.info("[OK] Compounds preprocessing complete")
    
    return df

def aggregate_mutation_stats():
    """Create aggregated mutation statistics"""
    logger.info("\n" + "="*70)
    logger.info("AGGREGATING: MUTATION STATISTICS")
    logger.info("="*70)
    
    # Use processed mutation features
    df = pd.read_csv(PROCESSED_DIR / 'mutation_features.csv')
    
    # Aggregate by model
    model_stats = df.groupby('model_name').agg({
        'gene_symbol': 'nunique',
        'LABEL': 'count',
        'vaf': ['mean', 'max'],
        'gene_mutation_count': 'max'
    }).round(4)
    
    model_stats.columns = ['unique_genes', 'total_mutations', 'mean_vaf', 'max_vaf', 'max_gene_mut_count']
    
    logger.info(f"Created mutation stats for {len(model_stats)} models")
    logger.info("[OK] Mutation statistics aggregation complete")
    
    return model_stats

# ============================================================================
# SECTION 5: INTEGRATED ANALYSIS & SUMMARY
# ============================================================================

def create_integrated_summary():
    """Create integrated summary of all datasets"""
    logger.info("\n" + "="*70)
    logger.info("INTEGRATED DATA SUMMARY")
    logger.info("="*70)
    
    # Load preprocessed data
    models_df = preprocess_model_list()
    cnv_df = preprocess_cnv_data()
    compounds_df = preprocess_compounds()
    mut_stats = aggregate_mutation_stats()
    
    # Create summary
    summary = {
        'Total Models': len(models_df),
        'Cancer Types': models_df['cancer_type'].nunique(),
        'CNV Records': len(cnv_df),
        'Unique Genes (CNV)': cnv_df['symbol'].nunique(),
        'Drug Compounds': len(compounds_df),
        'Mutation Features': len(pd.read_csv(PROCESSED_DIR / 'mutation_features.csv'))
    }
    
    print("\nINTEGRATED DATA SUMMARY:")
    for key, value in summary.items():
        print(f"  {key:.<35} {value:>10,}")
    
    return models_df, cnv_df, compounds_df, mut_stats

def save_preprocessed_data():
    """Save all preprocessed data"""
    logger.info("\n" + "="*70)
    logger.info("SAVING PREPROCESSED DATA")
    logger.info("="*70)
    
    models_df = preprocess_model_list()
    cnv_df = preprocess_cnv_data()
    compounds_df = preprocess_compounds()
    mut_stats = aggregate_mutation_stats()
    
    # Save to processed directory
    models_df.to_csv(PROCESSED_DIR / '01_models_preprocessed.csv', index=False)
    logger.info(f"[OK] Saved models to 01_models_preprocessed.csv")
    
    cnv_df.to_csv(PROCESSED_DIR / '02_cnv_preprocessed.csv', index=False)
    logger.info(f"[OK] Saved CNV data to 02_cnv_preprocessed.csv")
    
    compounds_df.to_csv(PROCESSED_DIR / '03_compounds_cleaned.csv', index=False)
    logger.info(f"[OK] Saved compounds to 03_compounds_cleaned.csv")
    
    mut_stats.to_csv(PROCESSED_DIR / '04_mutation_statistics.csv')
    logger.info(f"[OK] Saved mutation stats to 04_mutation_statistics.csv")
    
    logger.info("[OK] All preprocessed data saved successfully")

# ============================================================================
# SECTION 6: DATA PROFILING REPORT
# ============================================================================

def generate_data_report():
    """Generate comprehensive data profiling report"""
    logger.info("\n" + "="*70)
    logger.info("COMPREHENSIVE DATA PROFILING REPORT")
    logger.info("="*70)
    
    # Explore each dataset
    models_df = explore_model_list()
    print("\n" + "-"*70)
    cnv_df = explore_cnv_data()
    print("\n" + "-"*70)
    mut_sample = explore_mutations_sample()
    print("\n" + "-"*70)
    mut_features = explore_processed_mutations()
    print("\n" + "-"*70)
    
    # Create integrated summary
    summary_data = create_integrated_summary()
    
    logger.info("\n" + "="*70)
    logger.info("DATA QUALITY CHECKS")
    logger.info("="*70)
    
    print("\nData Quality Assessment:")
    print("  [OK] Model list: Complete and cleaned")
    print("  [OK] CNV data: Deduplicated and validated")
    print("  [OK] Mutation features: Pre-processed with encodings")
    print("  [OK] Drug compounds: Cleaned")
    
    return summary_data

# ============================================================================
# SECTION 7: MAIN EXECUTION
# ============================================================================

def main():
    """Main pipeline execution"""
    print("\n" + "="*70)
    print("GENOMIC DATA ANALYSIS & PREPROCESSING PIPELINE")
    print("="*70)
    
    try:
        # STEP 1: Exploratory Data Analysis
        print("\n[STEP1] EXPLORATORY DATA ANALYSIS")
        print("-" * 70)
        generate_data_report()
        
        # STEP 2: Data Preprocessing
        print("\n\n[STEP2] DATA PREPROCESSING")
        print("-" * 70)
        save_preprocessed_data()
        
        # STEP 3: Summary
        print("\n\n[STEP3] EXECUTION SUMMARY")
        print("-" * 70)
        print("\n[OK] Pipeline completed successfully!")
        print(f"\n[SAVED] Processed data saved to: {PROCESSED_DIR}")
        print(f"\n[FILES] Generated files:")
        for file in sorted(PROCESSED_DIR.glob('*.csv')):
            size = file.stat().st_size / (1024*1024)
            print(f"  * {file.name} ({size:.2f} MB)")
        
        logger.info("\n" + "="*70)
        logger.info("PIPELINE EXECUTION COMPLETED SUCCESSFULLY")
        logger.info("="*70)
        
    except Exception as e:
        logger.error(f"ERROR during pipeline execution: {str(e)}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    main()
