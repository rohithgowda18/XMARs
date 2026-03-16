# XMARs
Lung cancer drug resistance project.

## Mutation analysis ML pipeline

This repository now includes a full end-to-end mutation classification pipeline for TCGA/cBioPortal lung cancer mutation data:

- Data loading from MAF/CSV/TSV files.
- Preprocessing (column selection, missing-value handling, categorical encoding, scaling).
- Biologically informed feature engineering (gene mutation frequency/count, variant impact, mutation length).
- Model training (Random Forest, Gradient Boosting, or XGBoost).
- Evaluation (accuracy, precision, recall, F1, ROC-AUC, classification report, confusion matrix).
- Model persistence using `joblib`.
- Optional SHAP explainability output.

### Input datasets
Use public lung cancer mutation files, e.g.:

- TCGA-LUAD and TCGA-LUSC MAF files from GDC.
- cBioPortal lung cancer mutation exports.

### Quick start

```bash
python mutation_pipeline.py \
  --input-files data/luad.maf data/lusc.maf \
  --model random_forest \
  --output-model mutation_model.pkl \
  --output-metrics metrics.json \
  --output-confusion confusion_matrix.png
```

### Optional arguments

- `--label-column`: Use an existing binary label column (1=important mutation, 0=not).
- If omitted, the script builds a heuristic target from known lung driver genes + high-impact variant classes.
- `--model`: `random_forest`, `gradient_boosting`, or `xgboost`.
- `--test-size`: Default is `0.2` (80/20 train-test split).
- `--output-shap`: Path to save optional SHAP summary figure.

### Outputs

- `mutation_model.pkl` (trained sklearn pipeline)
- `metrics.json`
- `confusion_matrix.png`
- `shap_feature_importance.png` (optional if SHAP works)
