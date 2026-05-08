"""
Model Fine-Tuning and Hyperparameter Optimization
Improves model accuracy through systematic hyperparameter tuning
"""

import pandas as pd
import numpy as np
from sklearn.model_selection import (
    GridSearchCV, RandomizedSearchCV, cross_val_score, 
    StratifiedKFold, train_test_split
)
from sklearn.preprocessing import StandardScaler, RobustScaler
from sklearn.ensemble import (
    RandomForestClassifier, GradientBoostingClassifier,
    AdaBoostClassifier, ExtraTreesClassifier, VotingClassifier
)
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, 
    roc_auc_score, confusion_matrix, classification_report
)
import joblib
import logging
import warnings
from pathlib import Path

warnings.filterwarnings('ignore')

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
DATA_DIR = Path(__file__).parent / 'data' / 'processed'
MODEL_DIR = Path(__file__).parent / 'models'
MODEL_DIR.mkdir(exist_ok=True)

# ============================================================================
# SECTION 1: DATA LOADING AND PREPARATION
# ============================================================================

def load_and_prepare_data():
    """Load and prepare data for model training"""
    logger.info("\n" + "="*70)
    logger.info("DATA LOADING AND PREPARATION")
    logger.info("="*70)
    
    # Load mutation features
    df = pd.read_csv(DATA_DIR / 'mutation_features.csv')
    
    logger.info(f"Original dataset: {df.shape}")
    print(f"\nDataset shape: {df.shape}")
    print(f"Columns: {df.columns.tolist()[:10]}... ({len(df.columns)} total)")
    
    # Identify features and target
    feature_cols = [col for col in df.columns if col.startswith('ohe_')]
    feature_cols.extend(['vaf', 'vaf_high', 'vaf_low', 'coding', 
                         'cancer_predisposition_variant', 'gene_mutation_count'])
    
    # Remove NaN columns and keep valid features
    feature_cols = [col for col in feature_cols if col in df.columns]
    
    # Ensure target exists
    if 'LABEL' not in df.columns:
        logger.warning("LABEL column not found. Using gene_symbol prediction.")
        df['LABEL'] = pd.factorize(df['gene_symbol'])[0]
    
    X = df[feature_cols].fillna(0)
    y = df['LABEL']
    
    logger.info(f"Features: {X.shape[1]}")
    logger.info(f"Samples: {X.shape[0]}")
    logger.info(f"Target classes: {y.nunique()}")
    print(f"\nFeature matrix: {X.shape}")
    print(f"Target distribution: {y.value_counts().to_dict()}")
    
    # Balance dataset
    from collections import Counter
    class_counts = Counter(y)
    min_class = min(class_counts.values())
    
    # Take balanced sample
    indices_to_keep = []
    for class_label in y.unique():
        class_indices = np.where(y == class_label)[0]
        # Sample without replacement
        sampled = np.random.choice(class_indices, min(min_class * 5, len(class_indices)), 
                                   replace=False)
        indices_to_keep.extend(sampled)
    
    indices_to_keep = np.array(indices_to_keep)
    X = X.iloc[indices_to_keep].reset_index(drop=True)
    y = y.iloc[indices_to_keep].reset_index(drop=True)
    
    logger.info(f"Balanced dataset: {X.shape}")
    print(f"Balanced dataset shape: {X.shape}")
    print(f"New target distribution: {y.value_counts().to_dict()}")
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    logger.info(f"Train: {X_train.shape}, Test: {X_test.shape}")
    
    return X_train, X_test, y_train, y_test

# ============================================================================
# SECTION 2: FEATURE SCALING
# ============================================================================

def scale_features(X_train, X_test):
    """Scale features for better model performance"""
    logger.info("\n" + "="*70)
    logger.info("FEATURE SCALING")
    logger.info("="*70)
    
    scaler = RobustScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    logger.info("Features scaled using RobustScaler")
    
    return X_train_scaled, X_test_scaled, scaler

# ============================================================================
# SECTION 3: HYPERPARAMETER TUNING
# ============================================================================

def tune_random_forest(X_train, y_train):
    """Fine-tune Random Forest with GridSearchCV"""
    logger.info("\n" + "="*70)
    logger.info("TUNING: RANDOM FOREST")
    logger.info("="*70)
    
    param_grid = {
        'n_estimators': [100, 200, 300],
        'max_depth': [10, 15, 20, None],
        'min_samples_split': [2, 5, 10],
        'min_samples_leaf': [1, 2, 4],
        'max_features': ['sqrt', 'log2'],
        'class_weight': ['balanced', 'balanced_subsample']
    }
    
    rf = RandomForestClassifier(random_state=42, n_jobs=-1)
    
    grid_search = GridSearchCV(
        rf, param_grid, cv=5, scoring='f1_weighted', 
        n_jobs=-1, verbose=1
    )
    
    print("\nSearching Random Forest parameters...")
    grid_search.fit(X_train, y_train)
    
    logger.info(f"Best RF params: {grid_search.best_params_}")
    logger.info(f"Best RF CV score: {grid_search.best_score_:.4f}")
    print(f"Best Random Forest CV score: {grid_search.best_score_:.4f}")
    
    return grid_search.best_estimator_

def tune_gradient_boosting(X_train, y_train):
    """Fine-tune Gradient Boosting"""
    logger.info("\nTUNING: GRADIENT BOOSTING")
    
    param_grid = {
        'n_estimators': [100, 200, 300],
        'learning_rate': [0.001, 0.01, 0.1],
        'max_depth': [3, 5, 7],
        'min_samples_split': [2, 5],
        'subsample': [0.7, 0.9, 1.0]
    }
    
    gb = GradientBoostingClassifier(random_state=42)
    
    grid_search = GridSearchCV(
        gb, param_grid, cv=5, scoring='f1_weighted', 
        n_jobs=-1, verbose=1
    )
    
    print("\nSearching Gradient Boosting parameters...")
    grid_search.fit(X_train, y_train)
    
    logger.info(f"Best GB params: {grid_search.best_params_}")
    logger.info(f"Best GB CV score: {grid_search.best_score_:.4f}")
    print(f"Best Gradient Boosting CV score: {grid_search.best_score_:.4f}")
    
    return grid_search.best_estimator_

def tune_adaboost(X_train, y_train):
    """Fine-tune AdaBoost"""
    logger.info("\nTUNING: ADABOOST")
    
    param_grid = {
        'n_estimators': [50, 100, 200],
        'learning_rate': [0.5, 1.0, 1.5]
    }
    
    ada = AdaBoostClassifier(random_state=42)
    
    grid_search = GridSearchCV(
        ada, param_grid, cv=5, scoring='f1_weighted', 
        n_jobs=-1, verbose=1
    )
    
    print("\nSearching AdaBoost parameters...")
    grid_search.fit(X_train, y_train)
    
    logger.info(f"Best ADA params: {grid_search.best_params_}")
    logger.info(f"Best ADA CV score: {grid_search.best_score_:.4f}")
    print(f"Best AdaBoost CV score: {grid_search.best_score_:.4f}")
    
    return grid_search.best_estimator_

def tune_svm(X_train, y_train):
    """Fine-tune SVM"""
    logger.info("\nTUNING: SVM")
    
    param_grid = {
        'C': [0.1, 1, 10],
        'kernel': ['rbf', 'poly'],
        'class_weight': ['balanced']
    }
    
    svm = SVC(random_state=42, probability=True)
    
    grid_search = GridSearchCV(
        svm, param_grid, cv=5, scoring='f1_weighted', 
        n_jobs=-1, verbose=1
    )
    
    print("\nSearching SVM parameters...")
    grid_search.fit(X_train, y_train)
    
    logger.info(f"Best SVM params: {grid_search.best_params_}")
    logger.info(f"Best SVM CV score: {grid_search.best_score_:.4f}")
    print(f"Best SVM CV score: {grid_search.best_score_:.4f}")
    
    return grid_search.best_estimator_

# ============================================================================
# SECTION 4: MODEL EVALUATION
# ============================================================================

def evaluate_model(model, X_test, y_test, model_name):
    """Evaluate model performance"""
    y_pred = model.predict(X_test)
    
    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred, average='weighted', zero_division=0)
    recall = recall_score(y_test, y_pred, average='weighted', zero_division=0)
    f1 = f1_score(y_test, y_pred, average='weighted', zero_division=0)
    
    try:
        roc_auc = roc_auc_score(y_test, y_pred, average='weighted', multi_class='ovr')
    except:
        roc_auc = 0.0
    
    logger.info(f"\n{model_name} Performance:")
    logger.info(f"  Accuracy:  {accuracy:.4f}")
    logger.info(f"  Precision: {precision:.4f}")
    logger.info(f"  Recall:    {recall:.4f}")
    logger.info(f"  F1-Score:  {f1:.4f}")
    logger.info(f"  ROC-AUC:   {roc_auc:.4f}")
    
    print(f"\n{model_name} Metrics:")
    print(f"  Accuracy:  {accuracy:.4f}")
    print(f"  Precision: {precision:.4f}")
    print(f"  Recall:    {recall:.4f}")
    print(f"  F1-Score:  {f1:.4f}")
    
    return {
        'model_name': model_name,
        'accuracy': accuracy,
        'precision': precision,
        'recall': recall,
        'f1_score': f1,
        'roc_auc': roc_auc
    }

# ============================================================================
# SECTION 5: ENSEMBLE MODEL
# ============================================================================

def create_ensemble_model(models):
    """Create voting ensemble from best models"""
    logger.info("\n" + "="*70)
    logger.info("CREATING ENSEMBLE MODEL")
    logger.info("="*70)
    
    voting_clf = VotingClassifier(
        estimators=[
            ('rf', models['rf']),
            ('gb', models['gb']),
            ('ada', models['ada'])
        ],
        voting='soft'
    )
    
    logger.info("Ensemble created with RF, GB, and AdaBoost")
    return voting_clf

# ============================================================================
# SECTION 6: MAIN TRAINING PIPELINE
# ============================================================================

def main():
    """Main fine-tuning pipeline"""
    print("\n" + "="*70)
    print("MODEL FINE-TUNING AND OPTIMIZATION PIPELINE")
    print("="*70)
    
    try:
        # Step 1: Load and prepare data
        logger.info("\nSTEP 1: Loading data...")
        X_train, X_test, y_train, y_test = load_and_prepare_data()
        
        # Step 2: Scale features
        logger.info("\nSTEP 2: Scaling features...")
        X_train_scaled, X_test_scaled, scaler = scale_features(X_train, X_test)
        
        # Save scaler
        joblib.dump(scaler, MODEL_DIR / 'feature_scaler.pkl')
        logger.info("[OK] Scaler saved")
        
        # Step 3: Tune models
        logger.info("\nSTEP 3: Tuning models...")
        print("\n" + "-"*70)
        models = {}
        
        models['rf'] = tune_random_forest(X_train_scaled, y_train)
        models['gb'] = tune_gradient_boosting(X_train_scaled, y_train)
        models['ada'] = tune_adaboost(X_train_scaled, y_train)
        models['svm'] = tune_svm(X_train_scaled, y_train)
        
        # Step 4: Evaluate models
        logger.info("\nSTEP 4: Evaluating tuned models...")
        print("\n" + "="*70)
        print("TUNED MODEL PERFORMANCE")
        print("="*70)
        
        results = []
        for model_name, model in models.items():
            result = evaluate_model(model, X_test_scaled, y_test, model_name.upper())
            results.append(result)
        
        # Step 5: Create ensemble
        logger.info("\nSTEP 5: Creating ensemble...")
        ensemble = create_ensemble_model(models)
        ensemble.fit(X_train_scaled, y_train)
        result = evaluate_model(ensemble, X_test_scaled, y_test, "ENSEMBLE")
        results.append(result)
        
        # Step 6: Save all models
        logger.info("\nSTEP 6: Saving models...")
        print("\n" + "-"*70)
        print("SAVING MODELS")
        print("-" * 70)
        
        for model_name, model in models.items():
            joblib.dump(model, MODEL_DIR / f'{model_name}_tuned.pkl')
            logger.info(f"[OK] Saved {model_name}_tuned.pkl")
            print(f"[OK] {model_name}_tuned.pkl")
        
        joblib.dump(ensemble, MODEL_DIR / 'ensemble_model.pkl')
        logger.info("[OK] Saved ensemble_model.pkl")
        print("[OK] ensemble_model.pkl")
        
        # Save results summary
        results_df = pd.DataFrame(results)
        results_df.to_csv(MODEL_DIR / 'fine_tuned_results.csv', index=False)
        logger.info("[OK] Saved fine_tuned_results.csv")
        print("[OK] fine_tuned_results.csv")
        
        # Step 7: Summary
        print("\n" + "="*70)
        print("FINE-TUNING SUMMARY")
        print("="*70)
        print(results_df.to_string())
        
        best_model = results_df.loc[results_df['f1_score'].idxmax()]
        print(f"\nBest Model: {best_model['model_name']}")
        print(f"Best F1-Score: {best_model['f1_score']:.4f}")
        print(f"Best Accuracy: {best_model['accuracy']:.4f}")
        
        logger.info("\n[OK] FINE-TUNING PIPELINE COMPLETED SUCCESSFULLY")
        
    except Exception as e:
        logger.error(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    main()
