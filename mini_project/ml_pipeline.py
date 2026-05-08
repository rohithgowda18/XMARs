"""
Production ML Pipeline: End-to-End Model Training and Prediction
Integrates data preprocessing, model training, and predictions
"""

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import RobustScaler
from sklearn.ensemble import (
    RandomForestClassifier, GradientBoostingClassifier,
    AdaBoostClassifier, VotingClassifier
)
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    classification_report, confusion_matrix
)
import joblib
import logging
from pathlib import Path
from datetime import datetime
import json

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
# SECTION 1: PIPELINE STAGE 1 - DATA PREPARATION
# ============================================================================

class DataPreparationStage:
    """Stage 1: Load and prepare data"""
    
    def __init__(self):
        logger.info("Initializing Data Preparation Stage")
        self.X_train = None
        self.X_test = None
        self.y_train = None
        self.y_test = None
        
    def load_and_prepare(self):
        """Load and prepare data"""
        logger.info("\n[STAGE 1] DATA PREPARATION")
        logger.info("="*70)
        
        print("\n[STAGE 1] DATA PREPARATION")
        print("-" * 70)
        
        # Load mutation features
        df = pd.read_csv(DATA_DIR / 'mutation_features.csv')
        logger.info(f"Loaded dataset: {df.shape}")
        print(f"Loaded dataset: {df.shape}")
        
        # Feature engineering
        feature_cols = [col for col in df.columns if col.startswith('ohe_')]
        feature_cols.extend(['vaf', 'vaf_high', 'vaf_low', 'coding', 
                             'cancer_predisposition_variant', 'gene_mutation_count'])
        feature_cols = [col for col in feature_cols if col in df.columns]
        
        # Prepare X and y
        if 'LABEL' not in df.columns:
            df['LABEL'] = pd.factorize(df['gene_symbol'])[0]
        
        X = df[feature_cols].fillna(0)
        y = df['LABEL']
        
        # Balance dataset
        from collections import Counter
        class_counts = Counter(y)
        min_class = min(class_counts.values())
        
        indices_to_keep = []
        for class_label in y.unique():
            class_indices = np.where(y == class_label)[0]
            sampled = np.random.choice(
                class_indices, 
                min(min_class * 3, len(class_indices)), 
                replace=False
            )
            indices_to_keep.extend(sampled)
        
        X = X.iloc[indices_to_keep].reset_index(drop=True)
        y = y.iloc[indices_to_keep].reset_index(drop=True)
        
        logger.info(f"Balanced dataset: {X.shape}")
        print(f"Balanced dataset: {X.shape}")
        
        # Split data
        self.X_train, self.X_test, self.y_train, self.y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        logger.info(f"Train: {self.X_train.shape}, Test: {self.X_test.shape}")
        print(f"Train/Test Split: {self.X_train.shape} / {self.X_test.shape}")
        
        return self.X_train, self.X_test, self.y_train, self.y_test

# ============================================================================
# SECTION 2: PIPELINE STAGE 2 - FEATURE SCALING
# ============================================================================

class FeatureScalingStage:
    """Stage 2: Scale features"""
    
    def __init__(self):
        logger.info("Initializing Feature Scaling Stage")
        self.scaler = RobustScaler()
        
    def scale(self, X_train, X_test):
        """Scale features"""
        logger.info("\n[STAGE 2] FEATURE SCALING")
        logger.info("="*70)
        
        print("\n[STAGE 2] FEATURE SCALING")
        print("-" * 70)
        
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        logger.info(f"Features scaled: Train {X_train_scaled.shape}, Test {X_test_scaled.shape}")
        print(f"Features scaled successfully")
        
        return X_train_scaled, X_test_scaled

# ============================================================================
# SECTION 3: PIPELINE STAGE 3 - MODEL TRAINING
# ============================================================================

class ModelTrainingStage:
    """Stage 3: Train models"""
    
    def __init__(self):
        logger.info("Initializing Model Training Stage")
        self.models = {}
        
    def train(self, X_train, y_train):
        """Train multiple models"""
        logger.info("\n[STAGE 3] MODEL TRAINING")
        logger.info("="*70)
        
        print("\n[STAGE 3] MODEL TRAINING")
        print("-" * 70)
        
        # Random Forest
        print("\nTraining Random Forest...")
        self.models['random_forest'] = RandomForestClassifier(
            n_estimators=200, max_depth=20, min_samples_split=5,
            min_samples_leaf=2, max_features='sqrt', 
            class_weight='balanced_subsample', random_state=42, n_jobs=-1
        ).fit(X_train, y_train)
        print("[OK] Random Forest trained")
        
        # Gradient Boosting
        print("Training Gradient Boosting...")
        self.models['gradient_boosting'] = GradientBoostingClassifier(
            n_estimators=200, learning_rate=0.1, max_depth=7,
            min_samples_split=5, subsample=0.9, random_state=42
        ).fit(X_train, y_train)
        print("[OK] Gradient Boosting trained")
        
        # AdaBoost
        print("Training AdaBoost...")
        self.models['adaboost'] = AdaBoostClassifier(
            n_estimators=100, learning_rate=1.0,
            random_state=42
        ).fit(X_train, y_train)
        print("[OK] AdaBoost trained")
        
        # Ensemble
        print("Creating Ensemble...")
        self.models['ensemble'] = VotingClassifier(
            estimators=[
                ('rf', self.models['random_forest']),
                ('gb', self.models['gradient_boosting']),
                ('ada', self.models['adaboost'])
            ],
            voting='soft'
        ).fit(X_train, y_train)
        print("[OK] Ensemble created and trained")
        
        logger.info(f"Models trained: {list(self.models.keys())}")
        
        return self.models

# ============================================================================
# SECTION 4: PIPELINE STAGE 4 - MODEL EVALUATION
# ============================================================================

class ModelEvaluationStage:
    """Stage 4: Evaluate models"""
    
    def evaluate(self, models, X_test, y_test):
        """Evaluate all models"""
        logger.info("\n[STAGE 4] MODEL EVALUATION")
        logger.info("="*70)
        
        print("\n[STAGE 4] MODEL EVALUATION")
        print("-" * 70)
        
        results = []
        
        for model_name, model in models.items():
            y_pred = model.predict(X_test)
            
            accuracy = accuracy_score(y_test, y_pred)
            precision = precision_score(y_test, y_pred, average='weighted', zero_division=0)
            recall = recall_score(y_test, y_pred, average='weighted', zero_division=0)
            f1 = f1_score(y_test, y_pred, average='weighted', zero_division=0)
            
            results.append({
                'model': model_name,
                'accuracy': accuracy,
                'precision': precision,
                'recall': recall,
                'f1_score': f1
            })
            
            logger.info(f"\n{model_name.upper()}:")
            logger.info(f"  Accuracy:  {accuracy:.4f}")
            logger.info(f"  Precision: {precision:.4f}")
            logger.info(f"  Recall:    {recall:.4f}")
            logger.info(f"  F1-Score:  {f1:.4f}")
            
            print(f"\n{model_name.upper()}")
            print(f"  Accuracy:  {accuracy:.4f}")
            print(f"  Precision: {precision:.4f}")
            print(f"  Recall:    {recall:.4f}")
            print(f"  F1-Score:  {f1:.4f}")
        
        results_df = pd.DataFrame(results)
        return results_df

# ============================================================================
# SECTION 5: PIPELINE STAGE 5 - MODEL PERSISTENCE
# ============================================================================

class ModelPersistenceStage:
    """Stage 5: Save models and artifacts"""
    
    def save(self, models, scaler, results_df):
        """Save models and artifacts"""
        logger.info("\n[STAGE 5] MODEL PERSISTENCE")
        logger.info("="*70)
        
        print("\n[STAGE 5] MODEL PERSISTENCE")
        print("-" * 70)
        
        # Save models
        for model_name, model in models.items():
            filepath = MODEL_DIR / f'{model_name}_pipeline.pkl'
            joblib.dump(model, filepath)
            logger.info(f"[OK] Saved {model_name}")
            print(f"[OK] {model_name}")
        
        # Save scaler
        joblib.dump(scaler, MODEL_DIR / 'scaler_pipeline.pkl')
        logger.info("[OK] Saved scaler")
        print("[OK] Scaler saved")
        
        # Save results
        results_df.to_csv(MODEL_DIR / 'pipeline_results.csv', index=False)
        logger.info("[OK] Saved results")
        print("[OK] Results saved")
        
        logger.info("All models and artifacts saved successfully")

# ============================================================================
# SECTION 6: PRODUCTION PIPELINE
# ============================================================================

class ProductionMLPipeline:
    """Complete production ML pipeline"""
    
    def __init__(self):
        self.stages = {
            'data_prep': DataPreparationStage(),
            'feature_scaling': FeatureScalingStage(),
            'model_training': ModelTrainingStage(),
            'model_evaluation': ModelEvaluationStage(),
            'model_persistence': ModelPersistenceStage()
        }
        
    def run(self):
        """Execute complete pipeline"""
        print("\n" + "="*70)
        print("PRODUCTION ML PIPELINE")
        print("="*70)
        
        try:
            # Stage 1: Data Preparation
            logger.info("Starting Production ML Pipeline...")
            X_train, X_test, y_train, y_test = self.stages['data_prep'].load_and_prepare()
            
            # Stage 2: Feature Scaling
            X_train_scaled, X_test_scaled = self.stages['feature_scaling'].scale(
                X_train, X_test
            )
            
            # Stage 3: Model Training
            models = self.stages['model_training'].train(X_train_scaled, y_train)
            
            # Stage 4: Model Evaluation
            results = self.stages['model_evaluation'].evaluate(
                models, X_test_scaled, y_test
            )
            
            # Stage 5: Model Persistence
            self.stages['model_persistence'].save(
                models, 
                self.stages['feature_scaling'].scaler,
                results
            )
            
            # Final Summary
            print("\n" + "="*70)
            print("PIPELINE EXECUTION SUMMARY")
            print("="*70)
            print(results.to_string())
            
            best_model = results.loc[results['f1_score'].idxmax()]
            print(f"\nBest Model: {best_model['model']}")
            print(f"Best F1-Score: {best_model['f1_score']:.4f}")
            print(f"Best Accuracy: {best_model['accuracy']:.4f}")
            
            logger.info("\n[OK] PIPELINE EXECUTION COMPLETED SUCCESSFULLY")
            print("\n[OK] PIPELINE COMPLETED SUCCESSFULLY")
            
        except Exception as e:
            logger.error(f"PIPELINE ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
            raise

# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    pipeline = ProductionMLPipeline()
    pipeline.run()
