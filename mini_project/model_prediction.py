"""
Model Deployment & Prediction Script
Use trained models to make predictions on new genomic data
"""

import joblib
import pandas as pd
import numpy as np
import json
from pathlib import Path
import warnings

warnings.filterwarnings('ignore')

# ============================================================================
# SECTION 1: SETUP
# ============================================================================

MODEL_DIR = Path(__file__).parent / 'models'
DATA_DIR = Path(__file__).parent / 'data'

class ModelPredictor:
    """Wrapper class for loading and using trained models"""
    
    def __init__(self, model_name='random_forest'):
        """
        Initialize predictor with a trained model
        
        Args:
            model_name: 'random_forest', 'gradient_boosting', or 'logistic_regression'
        """
        self.model_name = model_name
        self.model_path = MODEL_DIR / f'{model_name}.pkl'
        self.scaler_path = MODEL_DIR / 'scaler.pkl'
        self.encoder_path = MODEL_DIR / 'label_encoder.json'
        self.metadata_path = MODEL_DIR / 'metadata.json'
        
        # Load components
        self._load_model()
        self._load_scaler()
        self._load_encoder()
        self._load_metadata()
        
        print(f"[OK] Loaded {model_name} predictor")
    
    def _load_model(self):
        """Load trained model"""
        self.model = joblib.load(self.model_path)
        print(f"    Model: {self.model_path.name}")
    
    def _load_scaler(self):
        """Load feature scaler"""
        self.scaler = joblib.load(self.scaler_path)
        print(f"    Scaler: {self.scaler_path.name}")
    
    def _load_encoder(self):
        """Load label encoder"""
        with open(self.encoder_path) as f:
            self.encoder = json.load(f)
        print(f"    Classes: {len(self.encoder['classes'])} cancer types")
    
    def _load_metadata(self):
        """Load training metadata"""
        with open(self.metadata_path) as f:
            self.metadata = json.load(f)
        self.features = self.metadata['features']
    
    def predict(self, X):
        """
        Make predictions
        
        Args:
            X: DataFrame with required features
            
        Returns:
            predictions: Predicted class indices
            probabilities: Prediction probabilities
        """
        # Validate features
        if not all(f in X.columns for f in self.features):
            missing = [f for f in self.features if f not in X.columns]
            raise ValueError(f"Missing features: {missing}")
        
        # Select and order features
        X_selected = X[self.features]
        
        # Scale features if using logistic regression
        if self.model_name == 'logistic_regression':
            X_scaled = self.scaler.transform(X_selected)
        else:
            X_scaled = X_selected
        
        # Get predictions
        predictions = self.model.predict(X_scaled)
        probabilities = self.model.predict_proba(X_scaled)
        
        return predictions, probabilities
    
    def predict_cancer_type(self, X):
        """
        Predict cancer types with human-readable output
        
        Args:
            X: DataFrame with patient/model data
            
        Returns:
            DataFrame with predictions and confidence
        """
        predictions, probabilities = self.predict(X)
        
        # Decode predictions
        results = []
        for pred_idx, probs in zip(predictions, probabilities):
            cancer_type = self.encoder['classes'][pred_idx]
            confidence = probs[pred_idx]
            
            results.append({
                'predicted_cancer_type': cancer_type,
                'confidence': f"{confidence:.2%}",
                'class_probability': confidence
            })
        
        return pd.DataFrame(results)
    
    def get_feature_importances(self):
        """Get feature importance scores"""
        if hasattr(self.model, 'feature_importances_'):
            importances = self.model.feature_importances_
            
            importance_df = pd.DataFrame({
                'feature': self.features,
                'importance': importances
            }).sort_values('importance', ascending=False)
            
            return importance_df
        else:
            return None

# ============================================================================
# SECTION 2: PREDICTION EXAMPLES
# ============================================================================

def example_single_prediction():
    """Example: Predict cancer type for a single sample"""
    print("\n" + "="*70)
    print("EXAMPLE 1: Single Sample Prediction")
    print("="*70)
    
    # Initialize predictor
    predictor = ModelPredictor('random_forest')
    
    # Create sample data
    sample = pd.DataFrame({
        'unique_genes': [120],
        'avg_vaf': [0.52],
        'max_vaf': [0.91],
        'coding_mutations': [38],
        'total_mutations': [950],
        'cnv_mean': [2.3],
        'cnv_max': [6.1],
        'cnv_std': [1.5],
        'cnv_count': [745]
    })
    
    print("\nInput Features:")
    print(sample)
    
    # Make prediction
    result = predictor.predict_cancer_type(sample)
    
    print("\nPrediction Result:")
    print(result)
    
    return predictor

def example_batch_prediction(predictor):
    """Example: Batch predictions on multiple samples"""
    print("\n" + "="*70)
    print("EXAMPLE 2: Batch Prediction (10 samples)")
    print("="*70)
    
    # Generate random samples
    np.random.seed(42)
    batch = pd.DataFrame({
        'unique_genes': np.random.randint(80, 200, 10),
        'avg_vaf': np.random.uniform(0.3, 0.8, 10),
        'max_vaf': np.random.uniform(0.7, 1.0, 10),
        'coding_mutations': np.random.randint(20, 100, 10),
        'total_mutations': np.random.randint(500, 2000, 10),
        'cnv_mean': np.random.uniform(1.8, 3.5, 10),
        'cnv_max': np.random.uniform(3.0, 10.0, 10),
        'cnv_std': np.random.uniform(0.5, 3.0, 10),
        'cnv_count': np.random.randint(400, 1200, 10)
    })
    
    # Make predictions
    results = predictor.predict_cancer_type(batch)
    
    print("\nBatch Prediction Results (Top 5):")
    print(results.head())
    
    # Summary
    print("\nPrediction Summary:")
    print(results['predicted_cancer_type'].value_counts())

def example_model_comparison():
    """Example: Compare predictions from all three models"""
    print("\n" + "="*70)
    print("EXAMPLE 3: Model Comparison")
    print("="*70)
    
    sample = pd.DataFrame({
        'unique_genes': [150],
        'avg_vaf': [0.45],
        'max_vaf': [0.85],
        'coding_mutations': [45],
        'total_mutations': [1200],
        'cnv_mean': [2.1],
        'cnv_max': [5.2],
        'cnv_std': [1.8],
        'cnv_count': [850]
    })
    
    models = ['random_forest', 'gradient_boosting', 'logistic_regression']
    
    print("\nComparing all 3 models on same sample:")
    print("-" * 70)
    
    for model_name in models:
        predictor = ModelPredictor(model_name)
        result = predictor.predict_cancer_type(sample)
        
        print(f"\n{model_name.upper()}:")
        print(f"  Predicted: {result['predicted_cancer_type'][0]}")
        print(f"  Confidence: {result['confidence'][0]}")

def example_feature_importance():
    """Example: Display feature importance"""
    print("\n" + "="*70)
    print("EXAMPLE 4: Feature Importance Analysis")
    print("="*70)
    
    predictor = ModelPredictor('random_forest')
    
    importances = predictor.get_feature_importances()
    
    print("\nFeature Importance (Random Forest):")
    print("-" * 50)
    print(importances.to_string(index=False))
    
    # Visualization text
    print("\nImportance Distribution:")
    for idx, row in importances.head(5).iterrows():
        bar = "*" * int(row['importance'] * 100)
        print(f"  {row['feature']:<20} {bar}")

# ============================================================================
# SECTION 3: REAL DATA PREDICTION
# ============================================================================

def predict_from_preprocessed_data():
    """Predict on actual preprocessed data"""
    print("\n" + "="*70)
    print("EXAMPLE 5: Predictions on Real Data")
    print("="*70)
    
    # Load real data
    mutations = pd.read_csv(DATA_DIR / 'processed' / 'mutation_features.csv')
    cnv = pd.read_csv(DATA_DIR / 'processed' / '02_cnv_preprocessed.csv')
    
    # Aggregate features (same as training)
    mut_agg = mutations.groupby('model_name').agg({
        'gene_symbol': 'nunique',
        'vaf': ['mean', 'max'],
        'coding': 'sum',
        'LABEL': 'count'
    })
    mut_agg.columns = ['unique_genes', 'avg_vaf', 'max_vaf', 'coding_mutations', 'total_mutations']
    
    cnv_agg = cnv.groupby('model_name').agg({
        'total_copy_number': ['mean', 'max', 'std'],
        'cn_category': 'count'
    })
    cnv_agg.columns = ['cnv_mean', 'cnv_max', 'cnv_std', 'cnv_count']
    
    # Merge
    features = mut_agg.merge(cnv_agg, left_index=True, right_index=True, how='inner')
    features = features.fillna(0)
    
    # Make predictions
    predictor = ModelPredictor('random_forest')
    results = predictor.predict_cancer_type(features.head(10))
    
    # Add model names
    results['model_name'] = features.head(10).index
    
    print("\nTop 10 Predictions:")
    print("-" * 70)
    print(results[['model_name', 'predicted_cancer_type', 'confidence']].to_string(index=False))
    
    # Summary stats
    print("\nPrediction Summary (10 samples):")
    print(f"  Unique cancer types predicted: {results['predicted_cancer_type'].nunique()}")
    print(f"  Average confidence: {results['class_probability'].mean():.2%}")

# ============================================================================
# SECTION 4: MAIN
# ============================================================================

def main():
    """Run all prediction examples"""
    print("\n" + "="*70)
    print("TRAINED MODEL DEPLOYMENT & PREDICTION EXAMPLES")
    print("="*70)
    print(f"Model Directory: {MODEL_DIR}")
    print(f"Data Directory: {DATA_DIR}")
    
    try:
        # Example 1: Single prediction
        predictor = example_single_prediction()
        
        # Example 2: Batch prediction
        example_batch_prediction(predictor)
        
        # Example 3: Model comparison
        example_model_comparison()
        
        # Example 4: Feature importance
        example_feature_importance()
        
        # Example 5: Real data
        predict_from_preprocessed_data()
        
        print("\n" + "="*70)
        print("[OK] ALL EXAMPLES COMPLETED SUCCESSFULLY")
        print("="*70)
        
    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    main()
