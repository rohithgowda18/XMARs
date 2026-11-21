"""
SHAP Explainability Module
============================
Uses SHAP (SHapley Additive exPlanations) to explain ML model predictions.
Provides per-feature importance for individual patient mutation profiles.

Supports all 3 trained models:
  - RandomForest  (TreeExplainer)
  - GradientBoosting (TreeExplainer)
  - AdaBoost (KernelExplainer — AdaBoost lacks native tree SHAP support)
"""

import numpy as np
import pandas as pd
import joblib
import shap
import logging
import base64
import io
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Scikit-learn backwards compatibility shim for unpickling models
try:
    import sklearn._loss._loss as _loss
    sys.modules['_loss'] = _loss
except Exception:
    pass

logger = logging.getLogger(__name__)

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
MODEL_DIR = PROJECT_ROOT / 'models'
DATA_DIR = PROJECT_ROOT / 'data' / 'processed'


class SHAPExplainer:
    """
    Explains ML model predictions using SHAP values.
    Loads the trained models and provides feature-level explanations.
    """

    def __init__(self):
        self.models = {}
        self.scaler = None
        self.feature_names = []
        self.explainers = {}
        self.background_data = None
        self._loaded = False

    def load(self):
        """Load models, scaler, and prepare SHAP explainers."""
        logger.info("Loading models for SHAP explanation...")

        # Load scaler
        scaler_path = MODEL_DIR / 'scaler_pipeline.pkl'
        if scaler_path.exists():
            self.scaler = joblib.load(scaler_path)
            logger.info("Loaded scaler")
        else:
            logger.warning("Scaler not found, will skip scaling")

        # Load models
        model_files = {
            'random_forest': 'random_forest_pipeline.pkl',
            'gradient_boosting': 'gradient_boosting_pipeline.pkl',
            'adaboost': 'adaboost_pipeline.pkl',
        }

        for name, filename in model_files.items():
            path = MODEL_DIR / filename
            if path.exists():
                try:
                    self.models[name] = joblib.load(path)
                    logger.info(f"Loaded model: {name}")
                except Exception as e:
                    logger.warning(f"Could not load model {name}: {e}")
            else:
                logger.warning(f"Model not found: {path}")

        # Load feature names from mutation_features.csv
        features_path = DATA_DIR / 'mutation_features.csv'
        if features_path.exists():
            df = pd.read_csv(features_path, nrows=5)
            feature_cols = [col for col in df.columns if col.startswith('ohe_')]
            feature_cols.extend(['vaf', 'vaf_high', 'vaf_low', 'coding',
                                 'cancer_predisposition_variant', 'gene_mutation_count'])
            self.feature_names = [col for col in feature_cols if col in df.columns]
            logger.info(f"Feature names loaded: {len(self.feature_names)} features")

        # Prepare background data (small sample for SHAP)
        self._prepare_background_data()

        # Initialize SHAP explainers
        self._init_explainers()

        self._loaded = True
        logger.info("SHAP explainer ready")
        return self

    def _prepare_background_data(self):
        """Load a small sample of training data as SHAP background."""
        features_path = DATA_DIR / 'mutation_features.csv'
        if not features_path.exists():
            logger.warning("Cannot prepare background data: mutation_features.csv not found")
            return

        df = pd.read_csv(features_path)
        feature_cols = [c for c in self.feature_names if c in df.columns]

        X = df[feature_cols].fillna(0)

        # Sample 100 rows for background (SHAP recommends ~100)
        sample_size = min(100, len(X))
        X_sample = X.sample(n=sample_size, random_state=42)

        if self.scaler is not None:
            self.background_data = self.scaler.transform(X_sample)
        else:
            self.background_data = X_sample.values

        logger.info(f"Background data prepared: {self.background_data.shape}")

    def _init_explainers(self):
        """Initialize SHAP explainers for each model."""
        if self.background_data is None:
            logger.warning("Cannot init explainers: no background data")
            return

        for name, model in self.models.items():
            try:
                if name in ('random_forest', 'gradient_boosting'):
                    # TreeExplainer is exact and fast for tree models
                    self.explainers[name] = shap.TreeExplainer(model)
                    logger.info(f"TreeExplainer initialized for {name}")
                elif name == 'adaboost':
                    # AdaBoost: use TreeExplainer on the base estimators
                    # shap.TreeExplainer supports AdaBoost in recent versions
                    try:
                        self.explainers[name] = shap.TreeExplainer(model)
                        logger.info(f"TreeExplainer initialized for {name}")
                    except Exception:
                        # Fallback: use KernelExplainer with a small background
                        bg = shap.sample(self.background_data, min(50, len(self.background_data)))
                        self.explainers[name] = shap.KernelExplainer(model.predict_proba, bg)
                        logger.info(f"KernelExplainer (fallback) initialized for {name}")
            except Exception as e:
                logger.error(f"Failed to init explainer for {name}: {e}")

    def explain(self, features_df: pd.DataFrame, model_name: str = 'gradient_boosting') -> Dict:
        """
        Explain predictions for given features using SHAP.

        Args:
            features_df: DataFrame with feature columns matching training features
            model_name: Which model to explain ('random_forest', 'gradient_boosting', 'adaboost')

        Returns:
            Dict with SHAP values, top features, and explanation data
        """
        if not self._loaded:
            self.load()

        if model_name not in self.explainers:
            available = list(self.explainers.keys())
            if available:
                model_name = available[0]
                logger.warning(f"Requested model not available, using {model_name}")
            else:
                return {'error': 'No SHAP explainers available'}

        # Ensure features match
        feature_cols = [c for c in self.feature_names if c in features_df.columns]
        X = features_df[feature_cols].fillna(0)

        # Scale features
        if self.scaler is not None:
            X_scaled = self.scaler.transform(X)
        else:
            X_scaled = X.values

        # Get SHAP values
        explainer = self.explainers[model_name]
        try:
            shap_values = explainer.shap_values(X_scaled, check_additivity=False)
        except TypeError:
            shap_values = explainer.shap_values(X_scaled)

        # Handle multi-class / 3D arrays:
        # shap_values can be: list of arrays, 3D ndarray (samples, features, classes), or 2D ndarray
        model = self.models[model_name]
        predictions = model.predict(X_scaled)

        if isinstance(shap_values, list):
            shap_abs = np.mean([np.abs(sv) for sv in shap_values], axis=0)
        elif hasattr(shap_values, 'ndim') and shap_values.ndim == 3:
            shap_abs = np.mean(np.abs(shap_values), axis=2)
        else:
            shap_abs = np.abs(shap_values)

        # Build per-sample explanations
        sample_explanations = []
        for i in range(len(X)):
            # Top features for this sample
            importance = shap_abs[i]
            top_indices = np.argsort(importance)[::-1][:15]

            top_features = []
            for idx in top_indices:
                if idx < len(feature_cols):
                    feat_name = feature_cols[idx]
                    feat_value = float(X.iloc[i, idx])
                    shap_importance = float(importance[idx])

                    # Get directional SHAP (positive = pushes toward higher class)
                    pred_class = int(predictions[i])
                    if isinstance(shap_values, list):
                        if pred_class < len(shap_values):
                            direction = float(shap_values[pred_class][i][idx])
                        else:
                            direction = 0.0
                    elif hasattr(shap_values, 'ndim') and shap_values.ndim == 3:
                        if pred_class < shap_values.shape[2]:
                            direction = float(shap_values[i, idx, pred_class])
                        else:
                            direction = float(shap_values[i, idx, -1])
                    else:
                        direction = float(shap_values[i][idx])

                    top_features.append({
                        'feature': feat_name,
                        'value': feat_value,
                        'shap_importance': round(shap_importance, 6),
                        'direction': 'positive' if direction > 0 else 'negative',
                        'direction_value': round(direction, 6),
                    })

            sample_explanations.append({
                'prediction': int(predictions[i]),
                'top_features': top_features,
                'total_features_used': int(np.sum(importance > 0.001)),
            })

        # Global feature importance across all samples
        global_importance = np.mean(shap_abs, axis=0)
        global_top_indices = np.argsort(global_importance)[::-1][:20]
        global_top_features = []
        for idx in global_top_indices:
            if idx < len(feature_cols):
                global_top_features.append({
                    'feature': feature_cols[idx],
                    'mean_shap': round(float(global_importance[idx]), 6),
                })

        return {
            'model_name': model_name,
            'num_samples': len(X),
            'num_features': len(feature_cols),
            'sample_explanations': sample_explanations,
            'global_top_features': global_top_features,
        }

    def explain_all_models(self, features_df: pd.DataFrame) -> Dict:
        """
        Run SHAP explanation on ALL 3 models and return combined results.
        """
        results = {}
        for model_name in self.explainers:
            try:
                results[model_name] = self.explain(features_df, model_name)
            except Exception as e:
                logger.error(f"SHAP failed for {model_name}: {e}")
                results[model_name] = {'error': str(e)}

        # Consensus: features that are important across all models
        all_features = {}
        for model_name, result in results.items():
            if 'error' in result:
                continue
            for feat in result.get('global_top_features', []):
                name = feat['feature']
                if name not in all_features:
                    all_features[name] = {'feature': name, 'models': {}}
                all_features[name]['models'][model_name] = feat['mean_shap']

        # Sort by average importance across models
        consensus = sorted(
            all_features.values(),
            key=lambda x: np.mean(list(x['models'].values())),
            reverse=True
        )[:15]

        results['consensus_features'] = consensus
        return results

    def generate_shap_chart_data(self, features_df: pd.DataFrame,
                                  model_name: str = 'gradient_boosting') -> Dict:
        """
        Generate chart-ready data for the frontend to render SHAP visualizations.
        Returns bar chart data (top features + importance values).
        """
        explanation = self.explain(features_df, model_name)
        if 'error' in explanation:
            return explanation

        # Bar chart data: global top features
        chart_data = {
            'model': model_name,
            'bar_chart': {
                'labels': [f['feature'].replace('ohe_', '').replace('_', ' ')
                          for f in explanation['global_top_features'][:10]],
                'values': [f['mean_shap'] for f in explanation['global_top_features'][:10]],
            },
        }

        # Per-sample waterfall data (for first sample)
        if explanation['sample_explanations']:
            sample = explanation['sample_explanations'][0]
            chart_data['waterfall'] = {
                'labels': [f['feature'].replace('ohe_', '').replace('_', ' ')
                          for f in sample['top_features'][:10]],
                'values': [f['direction_value'] for f in sample['top_features'][:10]],
                'colors': ['#22c55e' if f['direction'] == 'positive' else '#ef4444'
                          for f in sample['top_features'][:10]],
            }

        return chart_data


# Module-level singleton
_explainer_instance = None


def get_shap_explainer() -> SHAPExplainer:
    """Get or create the singleton SHAP explainer."""
    global _explainer_instance
    if _explainer_instance is None:
        _explainer_instance = SHAPExplainer()
        _explainer_instance.load()
    return _explainer_instance


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

    # Test: explain a few samples from the dataset
    df = pd.read_csv(DATA_DIR / 'mutation_features.csv')
    feature_cols = [col for col in df.columns if col.startswith('ohe_')]
    feature_cols.extend(['vaf', 'vaf_high', 'vaf_low', 'coding',
                         'cancer_predisposition_variant', 'gene_mutation_count'])
    feature_cols = [col for col in feature_cols if col in df.columns]

    # Take first 5 samples
    X_test = df[feature_cols].head(5).fillna(0)

    explainer = get_shap_explainer()
    results = explainer.explain_all_models(X_test)

    print("\n" + "=" * 70)
    print("SHAP EXPLAINABILITY TEST")
    print("=" * 70)

    for model_name, result in results.items():
        if model_name == 'consensus_features':
            continue
        if 'error' in result:
            print(f"\n{model_name}: ERROR - {result['error']}")
            continue
        print(f"\n{model_name.upper()}:")
        print(f"  Samples explained: {result['num_samples']}")
        print(f"  Top 5 global features:")
        for feat in result['global_top_features'][:5]:
            print(f"    {feat['feature']:35s} SHAP={feat['mean_shap']:.6f}")

    print(f"\nConsensus features (important across all models):")
    for feat in results.get('consensus_features', [])[:5]:
        models = ', '.join(f"{k}={v:.4f}" for k, v in feat['models'].items())
        print(f"  {feat['feature']:35s} [{models}]")
