"""
Machine Learning Model Training:
Drug Response Prediction from Genomic Data

This script trains predictive models using mutation and pathway data
to predict drug response and cancer outcomes.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import joblib
import json
from datetime import datetime
import warnings

warnings.filterwarnings('ignore')

# ML Libraries
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, confusion_matrix, classification_report
)
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# SECTION 1: SETUP
# ============================================================================

DATA_DIR = Path(__file__).parent / 'data'
PROCESSED_DIR = DATA_DIR / 'processed'
MODEL_DIR = Path(__file__).parent / 'models'
MODEL_DIR.mkdir(exist_ok=True, parents=True)

print(f"\nModel Directory: {MODEL_DIR}")

# ============================================================================
# SECTION 2: LOAD AND PREPARE DATA
# ============================================================================

def load_training_data():
    """Load and prepare data for model training"""
    logger.info("\n" + "="*70)
    logger.info("LOADING TRAINING DATA")
    logger.info("="*70)
    
    # Load preprocessed data
    mutations = pd.read_csv(PROCESSED_DIR / 'mutation_features.csv')
    models = pd.read_csv(PROCESSED_DIR / '01_models_preprocessed.csv')
    cnv = pd.read_csv(PROCESSED_DIR / '02_cnv_preprocessed.csv')
    
    logger.info(f"Loaded mutations: {mutations.shape}")
    logger.info(f"Loaded models: {models.shape}")
    logger.info(f"Loaded CNV: {cnv.shape}")
    
    # Aggregate CNV data by model
    cnv_summary = cnv.groupby('model_name').agg({
        'total_copy_number': ['mean', 'max', 'std'],
        'cn_category': 'count'
    }).round(3)
    cnv_summary.columns = ['cnv_mean', 'cnv_max', 'cnv_std', 'cnv_count']
    cnv_summary = cnv_summary.fillna(0)
    
    logger.info(f"CNV summary shape: {cnv_summary.shape}")
    
    return mutations, models, cnv_summary

def prepare_training_features(mutations, models, cnv_summary):
    """Prepare features for training"""
    logger.info("\n" + "="*70)
    logger.info("PREPARING FEATURES")
    logger.info("="*70)
    
    # Aggregate mutations by model
    mutation_features = mutations.groupby('model_name').agg({
        'gene_symbol': 'nunique',
        'vaf': ['mean', 'max'],
        'coding': 'sum',
        'LABEL': 'count'
    }).round(3)
    
    mutation_features.columns = ['unique_genes', 'avg_vaf', 'max_vaf', 'coding_mutations', 'total_mutations']
    mutation_features = mutation_features.fillna(0)
    
    logger.info(f"Mutation features shape: {mutation_features.shape}")
    
    # Merge with CNV data
    feature_matrix = mutation_features.merge(
        cnv_summary,
        left_index=True,
        right_index=True,
        how='inner'
    )
    
    logger.info(f"Combined features shape: {feature_matrix.shape}")
    logger.info(f"Features: {list(feature_matrix.columns)}")
    
    # Create binary target: Cancer Type (simplified)
    model_names = feature_matrix.index.tolist()
    model_data = models[models['model_name'].isin(model_names)]
    
    # Get cancer type labels
    cancer_types = {}
    for idx, row in model_data.iterrows():
        cancer_types[row['model_name']] = row['cancer_type']
    
    # Encode cancer types
    le = LabelEncoder()
    targets = []
    valid_models = []
    
    for model in feature_matrix.index:
        if model in cancer_types:
            targets.append(cancer_types[model])
            valid_models.append(model)
    
    # Filter to valid models only
    feature_matrix_valid = feature_matrix.loc[valid_models]
    
    y = le.fit_transform(targets)
    
    # Remove classes with only 1 sample for proper train-test split
    class_counts = np.bincount(y)
    valid_classes = np.where(class_counts >= 2)[0]
    
    if len(valid_classes) < len(le.classes_):
        mask = np.isin(y, valid_classes)
        feature_matrix_valid = feature_matrix_valid[mask]
        y = y[mask]
        
        # Re-encode to remove gaps in class indices
        le = LabelEncoder()
        y = le.fit_transform(feature_matrix_valid.index.map(lambda x: cancer_types[x]))
    
    logger.info(f"Final training set shape: {feature_matrix_valid.shape}")
    logger.info(f"Classes: {len(le.classes_)}")
    logger.info(f"Class distribution: {np.bincount(y)}")
    
    # Save label encoder
    with open(MODEL_DIR / 'label_encoder.json', 'w') as f:
        json.dump({
            'classes': le.classes_.tolist(),
            'target': 'cancer_type'
        }, f, indent=2)
    
    return feature_matrix_valid, y, le, targets

# ============================================================================
# SECTION 3: MODEL TRAINING
# ============================================================================

def train_models(X, y):
    """Train multiple classification models"""
    logger.info("\n" + "="*70)
    logger.info("TRAINING MODELS")
    logger.info("="*70)
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    logger.info(f"Training set: {X_train.shape}")
    logger.info(f"Test set: {X_test.shape}")
    
    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Save scaler
    joblib.dump(scaler, MODEL_DIR / 'scaler.pkl')
    logger.info("[OK] Scaler saved")
    
    models_dict = {}
    results = []
    
    # ========================================================================
    # Model 1: Random Forest
    # ========================================================================
    logger.info("\n[Training] Random Forest Classifier...")
    rf_model = RandomForestClassifier(
        n_estimators=100,
        max_depth=15,
        min_samples_split=5,
        random_state=42,
        n_jobs=-1
    )
    rf_model.fit(X_train, y_train)
    
    rf_pred = rf_model.predict(X_test)
    rf_accuracy = accuracy_score(y_test, rf_pred)
    rf_f1 = f1_score(y_test, rf_pred, average='weighted')
    
    logger.info(f"  Accuracy: {rf_accuracy:.4f}")
    logger.info(f"  F1-Score: {rf_f1:.4f}")
    
    models_dict['random_forest'] = rf_model
    results.append({
        'model': 'Random Forest',
        'accuracy': rf_accuracy,
        'f1_score': rf_f1,
        'cv_score': cross_val_score(rf_model, X_train, y_train, cv=5).mean()
    })
    
    # ========================================================================
    # Model 2: Gradient Boosting
    # ========================================================================
    logger.info("\n[Training] Gradient Boosting Classifier...")
    gb_model = GradientBoostingClassifier(
        n_estimators=100,
        learning_rate=0.1,
        max_depth=5,
        random_state=42
    )
    gb_model.fit(X_train, y_train)
    
    gb_pred = gb_model.predict(X_test)
    gb_accuracy = accuracy_score(y_test, gb_pred)
    gb_f1 = f1_score(y_test, gb_pred, average='weighted')
    
    logger.info(f"  Accuracy: {gb_accuracy:.4f}")
    logger.info(f"  F1-Score: {gb_f1:.4f}")
    
    models_dict['gradient_boosting'] = gb_model
    results.append({
        'model': 'Gradient Boosting',
        'accuracy': gb_accuracy,
        'f1_score': gb_f1,
        'cv_score': cross_val_score(gb_model, X_train, y_train, cv=5).mean()
    })
    
    # ========================================================================
    # Model 3: Logistic Regression
    # ========================================================================
    logger.info("\n[Training] Logistic Regression...")
    lr_model = LogisticRegression(
        max_iter=1000,
        random_state=42,
        n_jobs=-1
    )
    lr_model.fit(X_train_scaled, y_train)
    
    lr_pred = lr_model.predict(X_test_scaled)
    lr_accuracy = accuracy_score(y_test, lr_pred)
    lr_f1 = f1_score(y_test, lr_pred, average='weighted')
    
    logger.info(f"  Accuracy: {lr_accuracy:.4f}")
    logger.info(f"  F1-Score: {lr_f1:.4f}")
    
    models_dict['logistic_regression'] = lr_model
    results.append({
        'model': 'Logistic Regression',
        'accuracy': lr_accuracy,
        'f1_score': lr_f1,
        'cv_score': cross_val_score(lr_model, X_train_scaled, y_train, cv=5).mean()
    })
    
    return models_dict, results, (X_test, y_test), (X_test_scaled, y_test)

# ============================================================================
# SECTION 4: MODEL EVALUATION
# ============================================================================

def evaluate_models(models_dict, results, test_data):
    """Evaluate and compare all models"""
    logger.info("\n" + "="*70)
    logger.info("MODEL EVALUATION & COMPARISON")
    logger.info("="*70)
    
    X_test, y_test = test_data
    
    print("\nModel Performance Summary:")
    print("=" * 70)
    print(f"{'Model':<25} {'Accuracy':<12} {'F1-Score':<12} {'CV-Score':<12}")
    print("-" * 70)
    
    best_model_name = None
    best_accuracy = -1
    
    for result in results:
        model_name = result['model']
        accuracy = result['accuracy']
        f1 = result['f1_score']
        cv = result['cv_score']
        
        print(f"{model_name:<25} {accuracy:<12.4f} {f1:<12.4f} {cv:<12.4f}")
        
        if accuracy > best_accuracy:
            best_accuracy = accuracy
            best_model_name = model_name
    
    print("-" * 70)
    print(f"BEST MODEL: {best_model_name} (Accuracy: {best_accuracy:.4f})")
    print("=" * 70)
    
    return best_model_name

# ============================================================================
# SECTION 5: SAVE MODELS
# ============================================================================

def save_trained_models(models_dict, best_model_name):
    """Save all trained models"""
    logger.info("\n" + "="*70)
    logger.info("SAVING TRAINED MODELS")
    logger.info("="*70)
    
    for model_name, model in models_dict.items():
        filepath = MODEL_DIR / f'{model_name}.pkl'
        joblib.dump(model, filepath)
        logger.info(f"[OK] Saved {model_name} to {filepath}")
    
    # Save metadata
    metadata = {
        'trained_at': datetime.now().isoformat(),
        'best_model': best_model_name,
        'data_source': 'LUAD_TCGA cancer genomics dataset',
        'target': 'Cancer Type Classification',
        'features': [
            'unique_genes', 'avg_vaf', 'max_vaf', 'coding_mutations',
            'total_mutations', 'cnv_mean', 'cnv_max', 'cnv_std', 'cnv_count'
        ],
        'models': list(models_dict.keys())
    }
    
    with open(MODEL_DIR / 'metadata.json', 'w') as f:
        json.dump(metadata, f, indent=2)
    
    logger.info(f"[OK] Saved metadata")
    print(f"\nModels saved to: {MODEL_DIR}")
    
    return metadata

# ============================================================================
# SECTION 6: FEATURE IMPORTANCE
# ============================================================================

def analyze_feature_importance(models_dict, feature_names):
    """Analyze and display feature importance"""
    logger.info("\n" + "="*70)
    logger.info("FEATURE IMPORTANCE ANALYSIS")
    logger.info("="*70)
    
    # Random Forest feature importance
    rf_model = models_dict.get('random_forest')
    if rf_model:
        importances = rf_model.feature_importances_
        indices = np.argsort(importances)[::-1][:10]
        
        print("\nTop 10 Important Features (Random Forest):")
        print("-" * 50)
        for i, idx in enumerate(indices, 1):
            print(f"  {i:2d}. {feature_names[idx]:<20} {importances[idx]:.4f}")
    
    # Gradient Boosting feature importance
    gb_model = models_dict.get('gradient_boosting')
    if gb_model:
        importances = gb_model.feature_importances_
        indices = np.argsort(importances)[::-1][:10]
        
        print("\nTop 10 Important Features (Gradient Boosting):")
        print("-" * 50)
        for i, idx in enumerate(indices, 1):
            print(f"  {i:2d}. {feature_names[idx]:<20} {importances[idx]:.4f}")

# ============================================================================
# SECTION 7: MAIN EXECUTION
# ============================================================================

def main():
    """Main training pipeline"""
    print("\n" + "="*70)
    print("MACHINE LEARNING MODEL TRAINING PIPELINE")
    print("="*70)
    print(f"\nVirtual Environment: Venkatachala")
    print(f"Model Storage: {MODEL_DIR}")
    print(f"Data Input: {PROCESSED_DIR}")
    
    try:
        # Step 1: Load data
        mutations, models, cnv_summary = load_training_data()
        
        # Step 2: Prepare features
        X, y, label_encoder, targets = prepare_training_features(
            mutations, models, cnv_summary
        )
        
        # Step 3: Train models
        models_dict, results, test_data, test_data_scaled = train_models(X, y)
        
        # Step 4: Evaluate
        best_model = evaluate_models(models_dict, results, test_data)
        
        # Step 5: Save models
        metadata = save_trained_models(models_dict, best_model)
        
        # Step 6: Feature importance
        analyze_feature_importance(models_dict, X.columns.tolist())
        
        # Summary
        print("\n" + "="*70)
        print("TRAINING COMPLETE")
        print("="*70)
        print(f"\n[OK] Trained {len(models_dict)} models")
        print(f"[OK] Best Model: {best_model}")
        print(f"[SAVED] All models to {MODEL_DIR}")
        print(f"\nFiles generated:")
        for file in sorted(MODEL_DIR.glob('*')):
            print(f"  * {file.name}")
        
        logger.info("\n[OK] PIPELINE COMPLETED SUCCESSFULLY")
        
    except Exception as e:
        logger.error(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    main()
