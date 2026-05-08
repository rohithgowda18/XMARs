# PRACTICAL EXAMPLES - HOW TO USE THE SYSTEM

## Example 1: Load and Use the Best Model

```python
#!/usr/bin/env python3
"""
Load the trained ensemble model and make predictions on new samples.
"""

import joblib
import pandas as pd
import numpy as np
from pathlib import Path

# Load model and scaler
model_path = Path('models/ensemble_pipeline.pkl')
scaler_path = Path('models/scaler_pipeline.pkl')

if model_path.exists() and scaler_path.exists():
    model = joblib.load(model_path)
    scaler = joblib.load(scaler_path)
    print("[OK] Models loaded successfully")
else:
    print("[ERROR] Models not found. Run ml_pipeline.py first.")
    exit(1)

# Example: Create sample feature vector (21 features)
# These would come from your mutation analysis
sample_features = {
    'vaf': 0.45,                          # Variant allele frequency
    'coding': 1,                          # Is coding mutation
    'missense': 1,                        # Is missense
    'gene_mutation_count': 5,             # How many mutations in gene
    'pathway_count': 2,                   # How many pathways affected
    # ... (add remaining 16 features)
}

# Create DataFrame matching training features
X = pd.DataFrame([sample_features])

# Scale features
X_scaled = scaler.transform(X)

# Make prediction
prediction = model.predict(X_scaled)
confidence = model.predict_proba(X_scaled)

print(f"Predicted Cancer Type: {prediction[0]}")
print(f"Confidence: {confidence[0].max():.2%}")

# Get decision from each base model (if supported)
for pred in model.estimators_:
    base_pred = pred.predict(X_scaled)
    base_conf = pred.predict_proba(X_scaled)
    print(f"  - {pred.__class__.__name__}: {base_pred[0]} ({base_conf[0].max():.2%})")
```

---

## Example 2: Batch Predictions on Multiple Samples

```python
#!/usr/bin/env python3
"""
Make predictions on multiple samples in batch mode.
"""

import joblib
import pandas as pd
import json
from datetime import datetime

# Load models
model = joblib.load('models/ensemble_pipeline.pkl')
scaler = joblib.load('models/scaler_pipeline.pkl')

# Load preprocessed data
mutations = pd.read_csv('data/processed/mutation_features.csv')

# Take first 100 samples for batch prediction
X = mutations.iloc[:100, :-1]  # Exclude target column

# Scale and predict
X_scaled = scaler.transform(X)
predictions = model.predict(X_scaled)
confidences = model.predict_proba(X_scaled).max(axis=1)

# Create results
results = []
for i, (pred, conf) in enumerate(zip(predictions, confidences)):
    results.append({
        'sample_id': mutations.iloc[i].get('model_id', f'sample_{i}'),
        'predicted_cancer_type': pred,
        'confidence': float(conf),
        'timestamp': datetime.now().isoformat()
    })

# Save results
output_df = pd.DataFrame(results)
output_df.to_csv('predictions_batch.csv', index=False)

print(f"[OK] Predicted {len(results)} samples")
print(f"[OK] Average confidence: {output_df['confidence'].mean():.2%}")
print(f"[OK] Results saved to predictions_batch.csv")

# Show summary
print("\nCancer Type Distribution:")
print(output_df['predicted_cancer_type'].value_counts())
```

---

## Example 3: Compare All 4 Models on Same Data

```python
#!/usr/bin/env python3
"""
Compare predictions from all 4 trained models.
"""

import joblib
import pandas as pd
import numpy as np

# Load all models
models = {
    'Random Forest': joblib.load('models/random_forest_pipeline.pkl'),
    'Gradient Boosting': joblib.load('models/gradient_boosting_pipeline.pkl'),
    'AdaBoost': joblib.load('models/adaboost_pipeline.pkl'),
    'Ensemble': joblib.load('models/ensemble_pipeline.pkl')
}

scaler = joblib.load('models/scaler_pipeline.pkl')

# Load test data
mutations = pd.read_csv('data/processed/mutation_features.csv')
X_test = mutations.iloc[:50, :-1]
y_test = mutations.iloc[:50, -1]

X_scaled = scaler.transform(X_test)

# Get predictions from all models
results = []
for model_name, model in models.items():
    predictions = model.predict(X_scaled)
    probabilities = model.predict_proba(X_scaled)
    accuracy = (predictions == y_test).mean()
    
    results.append({
        'Model': model_name,
        'Accuracy': f"{accuracy:.2%}",
        'Avg Confidence': f"{probabilities.max(axis=1).mean():.2%}",
        'Predictions': predictions
    })
    
    print(f"{model_name}:")
    print(f"  Accuracy: {accuracy:.2%}")
    print(f"  Avg Confidence: {probabilities.max(axis=1).mean():.2%}")
    print()

# Show agreement statistics
ensemble_preds = models['Ensemble'].predict(X_scaled)
for model_name, model in models.items():
    if model_name != 'Ensemble':
        other_preds = model.predict(X_scaled)
        agreement = (ensemble_preds == other_preds).mean()
        print(f"Ensemble vs {model_name} agreement: {agreement:.2%}")
```

---

## Example 4: Analyze Model Feature Importance

```python
#!/usr/bin/env python3
"""
Extract and visualize feature importance from trained models.
"""

import joblib
import pandas as pd
import numpy as np

# Load Random Forest (has feature_importances_)
rf_model = joblib.load('models/random_forest_pipeline.pkl')
gb_model = joblib.load('models/gradient_boosting_pipeline.pkl')

# Get feature names from training data
mutations = pd.read_csv('data/processed/mutation_features.csv')
feature_names = mutations.columns[:-1]

# Extract importances
rf_importances = rf_model.feature_importances_
gb_importances = gb_model.feature_importances_

# Create DataFrame
importance_df = pd.DataFrame({
    'Feature': feature_names,
    'RF_Importance': rf_importances,
    'GB_Importance': gb_importances
})

# Sort by average importance
importance_df['Avg_Importance'] = (importance_df['RF_Importance'] + 
                                   importance_df['GB_Importance']) / 2
importance_df = importance_df.sort_values('Avg_Importance', ascending=False)

print("Top 10 Most Important Features:")
print(importance_df.head(10)[['Feature', 'RF_Importance', 'GB_Importance', 'Avg_Importance']])

# Save to CSV
importance_df.to_csv('feature_importance.csv', index=False)
print("\n[OK] Feature importance saved to feature_importance.csv")
```

---

## Example 5: Integrate with Pathway Agent

```python
#!/usr/bin/env python3
"""
Use mutation and pathway information with ML predictions.
"""

import joblib
import pandas as pd
import json

# Load pathway definitions
with open('data/processed/pathway_reference.json') as f:
    pathways = json.load(f)

# Load ML model
model = joblib.load('models/ensemble_pipeline.pkl')
scaler = joblib.load('models/scaler_pipeline.pkl')

# Load sample mutation data
mutations = pd.read_csv('data/processed/mutation_features.csv')
sample = mutations.iloc[0:1]

# Extract pathway information
sample_pathways = []
for pathway_name, pathway_info in pathways.items():
    genes_in_sample = [g for g in pathway_info['genes'] 
                       if sample[g].values[0] > 0]
    
    if genes_in_sample:
        sample_pathways.append({
            'pathway': pathway_name,
            'genes_affected': genes_in_sample,
            'count': len(genes_in_sample)
        })

print("Affected Pathways in Sample:")
for pathway in sample_pathways:
    print(f"  - {pathway['pathway']}: {', '.join(pathway['genes_affected'])}")

# Make ML prediction
X_scaled = scaler.transform(sample.iloc[:, :-1])
prediction = model.predict(X_scaled)[0]
confidence = model.predict_proba(X_scaled)[0].max()

print(f"\nPredicted Cancer Type: {prediction}")
print(f"Confidence: {confidence:.2%}")

# This can be passed to Drug Agent
result = {
    'cancer_type': prediction,
    'confidence': confidence,
    'affected_pathways': sample_pathways,
    'mutations': sample.columns[sample.iloc[0] > 0].tolist()
}

print("\nNext Step - Send to Drug Agent:")
print(json.dumps(result, indent=2, default=str))
```

---

## Example 6: Model Performance Analysis

```python
#!/usr/bin/env python3
"""
Analyze model performance metrics from pipeline results.
"""

import pandas as pd
import json

# Load results
results = pd.read_csv('models/pipeline_results.csv')

print("MODEL PERFORMANCE SUMMARY")
print("=" * 60)

for idx, row in results.iterrows():
    print(f"\n{row['model'].upper()}")
    print(f"  Accuracy:  {row['accuracy']:.4f} ({row['accuracy']*100:.2f}%)")
    print(f"  Precision: {row['precision']:.4f}")
    print(f"  Recall:    {row['recall']:.4f}")
    print(f"  F1-Score:  {row['f1_score']:.4f}")

# Calculate improvements
best_accuracy = results['accuracy'].max()
baseline = results['accuracy'].min()
improvement = (best_accuracy - baseline) / baseline * 100

print("\n" + "=" * 60)
print(f"Best Model Accuracy: {best_accuracy:.4f} ({best_accuracy*100:.2f}%)")
print(f"Improvement over worst model: {improvement:.2f}%")

# Identify best model
best_model = results.loc[results['accuracy'].idxmax(), 'model']
print(f"Recommended Model: {best_model.upper()}")
```

---

## Example 7: Real-time Prediction Pipeline

```python
#!/usr/bin/env python3
"""
Set up real-time prediction pipeline for continuous monitoring.
"""

import joblib
import pandas as pd
import json
from datetime import datetime
from pathlib import Path

class PredictionService:
    def __init__(self):
        self.model = joblib.load('models/ensemble_pipeline.pkl')
        self.scaler = joblib.load('models/scaler_pipeline.pkl')
        self.predictions_log = []
    
    def predict(self, features_dict):
        """
        Make a single prediction.
        
        Args:
            features_dict: Dictionary with 21 features
            
        Returns:
            dict with prediction and metadata
        """
        X = pd.DataFrame([features_dict])
        X_scaled = self.scaler.transform(X)
        
        pred = self.model.predict(X_scaled)[0]
        prob = self.model.predict_proba(X_scaled)[0].max()
        
        result = {
            'timestamp': datetime.now().isoformat(),
            'prediction': pred,
            'confidence': float(prob),
            'status': 'success'
        }
        
        self.predictions_log.append(result)
        return result
    
    def batch_predict(self, features_df):
        """
        Make batch predictions.
        
        Args:
            features_df: DataFrame with multiple samples
            
        Returns:
            list of predictions
        """
        X_scaled = self.scaler.transform(features_df)
        preds = self.model.predict(X_scaled)
        probs = self.model.predict_proba(X_scaled)
        
        results = []
        for pred, prob in zip(preds, probs):
            results.append({
                'prediction': pred,
                'confidence': float(prob.max()),
                'timestamp': datetime.now().isoformat()
            })
        
        self.predictions_log.extend(results)
        return results
    
    def save_log(self, filepath='predictions.jsonl'):
        """Save prediction log to file."""
        with open(filepath, 'w') as f:
            for entry in self.predictions_log:
                f.write(json.dumps(entry) + '\n')
        print(f"[OK] Saved {len(self.predictions_log)} predictions to {filepath}")

# Usage
if __name__ == '__main__':
    service = PredictionService()
    
    # Single prediction
    sample = {
        'vaf': 0.5,
        'coding': 1,
        'missense': 1,
        'gene_mutation_count': 3,
        # ... add remaining features
    }
    result = service.predict(sample)
    print(f"Prediction: {result['prediction']} (confidence: {result['confidence']:.2%})")
    
    # Save log for monitoring
    service.save_log('predictions.jsonl')
```

---

## Example 8: Model Retraining Pipeline

```python
#!/usr/bin/env python3
"""
Retrain models on new data or if performance degrades.
"""

import joblib
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, AdaBoostClassifier, VotingClassifier
from sklearn.preprocessing import RobustScaler

def retrain_models(X_new, y_new):
    """
    Retrain all models on new data.
    """
    print("[RETRAIN] Loading data...")
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X_new, y_new, test_size=0.2, stratify=y_new, random_state=42
    )
    
    # Scale
    print("[RETRAIN] Scaling features...")
    scaler = RobustScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Train models
    print("[RETRAIN] Training models...")
    models = {
        'rf': RandomForestClassifier(n_estimators=200, random_state=42),
        'gb': GradientBoostingClassifier(n_estimators=200, random_state=42),
        'ada': AdaBoostClassifier(n_estimators=50, random_state=42)
    }
    
    for name, model in models.items():
        model.fit(X_train_scaled, y_train)
        score = model.score(X_test_scaled, y_test)
        print(f"  {name}: {score:.4f}")
        joblib.dump(model, f'models/retrained_{name}.pkl')
    
    # Create new ensemble
    print("[RETRAIN] Creating ensemble...")
    ensemble = VotingClassifier(
        estimators=[('rf', models['rf']), ('gb', models['gb']), ('ada', models['ada'])],
        voting='soft'
    )
    ensemble.fit(X_train_scaled, y_train)
    ensemble_score = ensemble.score(X_test_scaled, y_test)
    print(f"  Ensemble: {ensemble_score:.4f}")
    
    # Save new models
    joblib.dump(scaler, 'models/retrained_scaler.pkl')
    joblib.dump(ensemble, 'models/retrained_ensemble.pkl')
    
    print("[OK] Retrained models saved with '_retrained' prefix")
    return ensemble, scaler

# Usage
if __name__ == '__main__':
    # Load new data
    new_mutations = pd.read_csv('data/new_mutations.csv')
    X = new_mutations.iloc[:, :-1]
    y = new_mutations.iloc[:, -1]
    
    # Retrain
    ensemble, scaler = retrain_models(X, y)
```

---

## Running These Examples

1. **Single Prediction**:
   ```bash
   python example1_load_model.py
   ```

2. **Batch Predictions**:
   ```bash
   python example2_batch_predict.py
   ```

3. **Model Comparison**:
   ```bash
   python example3_compare_models.py
   ```

4. **Feature Importance**:
   ```bash
   python example4_feature_importance.py
   ```

5. **With Pathways**:
   ```bash
   python example5_pathway_integration.py
   ```

6. **Performance Analysis**:
   ```bash
   python example6_performance_analysis.py
   ```

7. **Real-time Service**:
   ```bash
   python example7_prediction_service.py
   ```

8. **Retrain Models**:
   ```bash
   python example8_retrain.py
   ```

---

All examples assume models are already trained (run `python ml_pipeline.py` first).

---
