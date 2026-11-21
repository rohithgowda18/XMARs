"""
PER-GENE PERFORMANCE ANALYSIS
===============================
Stratify test set by gene and calculate precision/recall for each.
Identifies which genes have reliable predictions vs which need more data.

Run:
    python per_gene_analysis.py
"""

import warnings
import pandas as pd
import numpy as np
import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
from sklearn.metrics import precision_score, recall_score, f1_score, accuracy_score

warnings.filterwarnings("ignore")

# ─── Paths ────────────────────────────────────────────────────────────────────
PROC   = Path("data/processed")
ENC    = PROC / "encoders"
MODELS = Path("models")
OUT    = Path("output")
FIGS   = Path("figures")
for d in [OUT, FIGS]:
    d.mkdir(parents=True, exist_ok=True)

print()
print("=" * 70)
print("  PER-GENE PERFORMANCE ANALYSIS")
print("=" * 70)

# ─── Load data ─────────────────────────────────────────────────────────────────
print("\n[1] Loading data and model ...")
df           = pd.read_csv(PROC / "mutation_features.csv", low_memory=False)
best_model   = joblib.load(MODELS / "Mutation_Model_BEST.pkl")
FEATURE_COLS = joblib.load(ENC / "feature_cols.pkl")
le_gene      = joblib.load(ENC / "le_gene.pkl")

print(f"    Loaded {len(df):,} mutations")
print(f"    Features: {len(FEATURE_COLS)}")
print(f"    Best model: {best_model.__class__.__name__}")

# ─── Create mutation ID for test set split ────────────────────────────────────
df["mutation_id"] = (
    df["gene_symbol"].astype(str) + "_" +
    df["chromosome"].astype(str)  + "_" +
    df["position"].astype(str)    + "_" +
    df["protein_mutation"].astype(str)
)

# Recreate the exact test set from step3_train.py
from sklearn.model_selection import train_test_split
unique_mutations = np.array(df["mutation_id"].unique())
train_muts, test_muts = train_test_split(
    unique_mutations,
    test_size=0.20,
    random_state=42
)

df_test = df[df["mutation_id"].isin(test_muts)].copy()
X_test  = df_test[FEATURE_COLS].values
y_test  = df_test["LABEL"].values

print(f"\n[2] Test set: {len(df_test):,} rows, {y_test.sum():,} drivers")

# ─── Make predictions ──────────────────────────────────────────────────────────
print("\n[3] Making predictions ...")
y_pred = best_model.predict(X_test)
y_pred_proba = best_model.predict_proba(X_test)[:, 1]

# ─── Per-gene analysis ─────────────────────────────────────────────────────────
print("\n[4] Stratifying by gene ...")

gene_results = []
for gene in sorted(df_test["gene_symbol"].unique()):
    mask = df_test["gene_symbol"] == gene
    
    if mask.sum() < 5:
        continue  # Skip genes with <5 test samples
    
    n_samples = mask.sum()
    n_drivers = y_test[mask].sum()
    
    y_pred_gene = y_pred[mask]
    y_test_gene = y_test[mask]
    
    # Calculate metrics
    accuracy   = accuracy_score(y_test_gene, y_pred_gene)
    precision  = precision_score(y_test_gene, y_pred_gene, zero_division=0)
    recall     = recall_score(y_test_gene, y_pred_gene, zero_division=0)
    f1         = f1_score(y_test_gene, y_pred_gene, zero_division=0)
    
    # Driver and passenger precision (TPR per class)
    n_pred_driver = y_pred_gene.sum()
    
    gene_results.append({
        'gene': gene,
        'n_test': n_samples,
        'n_drivers': n_drivers,
        'driver_rate': n_drivers / n_samples,
        'accuracy': accuracy,
        'precision': precision,
        'recall': recall,
        'f1': f1,
        'n_pred_driver': n_pred_driver
    })

gene_df = pd.DataFrame(gene_results).sort_values('n_test', ascending=False)

# ─── Print results ────────────────────────────────────────────────────────────
print("\n" + "=" * 90)
print("PER-GENE PERFORMANCE (Test Set)")
print("=" * 90)
print(gene_df.to_string(index=False))

# ─── Summary statistics ────────────────────────────────────────────────────────
print("\n" + "=" * 90)
print("PER-GENE SUMMARY")
print("=" * 90)
print(f"Number of genes    : {len(gene_df)}")
print(f"Average accuracy   : {gene_df['accuracy'].mean():.4f}")
print(f"Average precision  : {gene_df['precision'].mean():.4f}")
print(f"Average recall     : {gene_df['recall'].mean():.4f}")
print(f"Average F1         : {gene_df['f1'].mean():.4f}")
print()
print(f"Genes with accuracy >= 0.95: {(gene_df['accuracy'] >= 0.95).sum()}")
print(f"Genes with accuracy >= 0.90: {(gene_df['accuracy'] >= 0.90).sum()}")
print(f"Genes with accuracy >= 0.85: {(gene_df['accuracy'] >= 0.85).sum()}")
print()
print(f"Worst performing gene: {gene_df.loc[gene_df['accuracy'].idxmin(), 'gene']} "
      f"({gene_df['accuracy'].min():.4f})")
print(f"Best performing gene : {gene_df.loc[gene_df['accuracy'].idxmax(), 'gene']} "
      f"({gene_df['accuracy'].max():.4f})")

# ─── Visualization ────────────────────────────────────────────────────────────
print("\n[5] Generating visualization ...")

fig, axes = plt.subplots(2, 2, figsize=(14, 10))

# Accuracy by gene
ax = axes[0, 0]
gene_df_sorted = gene_df.sort_values('accuracy')
ax.barh(gene_df_sorted['gene'], gene_df_sorted['accuracy'], color='steelblue')
ax.axvline(0.95, color='red', linestyle='--', label='95% threshold')
ax.set_xlabel('Accuracy')
ax.set_title('Accuracy by Gene')
ax.legend()

# Precision vs Recall scatter
ax = axes[0, 1]
scatter = ax.scatter(gene_df['recall'], gene_df['precision'], 
                     s=gene_df['n_test']*2, alpha=0.6, c=gene_df['accuracy'],
                     cmap='RdYlGn', vmin=0.8, vmax=1.0)
for idx, row in gene_df.iterrows():
    ax.annotate(row['gene'], (row['recall'], row['precision']),
                fontsize=8, ha='center')
ax.set_xlabel('Recall')
ax.set_ylabel('Precision')
ax.set_title('Precision vs Recall by Gene (size=n_test)')
ax.grid(alpha=0.3)
plt.colorbar(scatter, ax=ax, label='Accuracy')

# F1 by gene
ax = axes[1, 0]
gene_df_sorted = gene_df.sort_values('f1')
ax.barh(gene_df_sorted['gene'], gene_df_sorted['f1'], color='mediumseagreen')
ax.set_xlabel('F1 Score')
ax.set_title('F1 Score by Gene')

# Driver rate vs accuracy
ax = axes[1, 1]
scatter = ax.scatter(gene_df['driver_rate'], gene_df['accuracy'],
                     s=gene_df['n_test']*2, alpha=0.6, c='purple')
for idx, row in gene_df.iterrows():
    ax.annotate(row['gene'], (row['driver_rate'], row['accuracy']),
                fontsize=8, ha='center')
ax.set_xlabel('Driver Rate (in test set)')
ax.set_ylabel('Accuracy')
ax.set_title('Accuracy vs Driver Rate (size=n_test)')
ax.grid(alpha=0.3)

plt.tight_layout()
plt.savefig(FIGS / "per_gene_performance.png", dpi=150, bbox_inches='tight')
print("    ✓ per_gene_performance.png")
plt.close()

# ─── Save results ──────────────────────────────────────────────────────────────
gene_df.to_csv(OUT / "per_gene_metrics.csv", index=False)
print(f"    ✓ per_gene_metrics.csv")

print("\n" + "=" * 90)
print("Per-gene analysis complete!")
print("=" * 90)
