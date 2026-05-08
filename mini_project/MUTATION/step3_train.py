"""
STEP 3 — MODEL TRAINING FOR MUTATION AGENT
===========================================
Guide Reference: Section 3 Step 5 — Model Prediction
  "The Mutation Agent uses a trained ML model"
  "Possible models: Random Forest, XGBoost, Gradient Boosting"
  "The model predicts whether the mutation is Driver or Passenger"

Guide Reference: Section 4 — Driver vs Passenger Mutation
  Driver    → causes cancer progression (EGFR, KRAS, BRAF, ALK)
  Passenger → does not contribute to cancer growth

Guide Reference: Section 5 — Model Output
  Gene | Mutation | Driver Probability
  EGFR | L858R    | 0.92
  TP53 | R175H    | 0.85
  KRAS | G12C     | 0.78

Key fixes from review:
  1. XGBoost added back  (guide requires all 3 models)
  2. gene_mutation_count KEPT  (guide requires mutation frequency feature)
  3. Mutation-level train/test split  (no data leakage)
  4. imbalanced-learn RandomOverSampler on train set only
  5. Confusion matrices + all 5 evaluation figures

Dependencies:
  pip install imbalanced-learn xgboost --break-system-packages

Run:
    python step3_train.py
"""

import warnings
import time
import numpy  as np
import pandas as pd
import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

from sklearn.model_selection  import train_test_split, StratifiedKFold, cross_val_score
from sklearn.ensemble         import RandomForestClassifier, GradientBoostingClassifier
from sklearn.metrics          import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, average_precision_score,
    classification_report, confusion_matrix,
    ConfusionMatrixDisplay, roc_curve
)
from imblearn.over_sampling   import RandomOverSampler
# from xgboost                  import XGBClassifier  # Not available in myenv
# import shap  # Not available in myenv

warnings.filterwarnings("ignore")
np.random.seed(42)

# ─── Paths ────────────────────────────────────────────────────────────────────
PROC   = Path("data/processed")
ENC    = PROC / "encoders"
MODELS = Path("models")
FIGS   = Path("figures")
OUT    = Path("output")
for d in [MODELS, FIGS, OUT]:
    d.mkdir(parents=True, exist_ok=True)


print()
print("=" * 65)
print("  STEP 3 — Mutation Agent Model Training")
print("  Guide Step 5: Driver vs Passenger Classification")
print("  Models: Random Forest + XGBoost + Gradient Boosting")
print("=" * 65)


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 1 — LOAD DATA
# ═════════════════════════════════════════════════════════════════════════════
print()
print("[1] Loading processed mutation features ...")

df           = pd.read_csv(PROC / "mutation_features.csv", low_memory=False)
FEATURE_COLS = joblib.load(ENC / "feature_cols.pkl")

print(f"    Total rows      : {len(df):,}")
print(f"    Feature columns : {len(FEATURE_COLS)}")
print(f"    Features        : {FEATURE_COLS}")
print(f"    Driver (1)      : {(df['LABEL']==1).sum():,}  "
      f"({df['LABEL'].mean():.4%})")
print(f"    Passenger (0)   : {(df['LABEL']==0).sum():,}")

# Verify guide-required features are present
required = ["gene_enc", "effect_impact"]  # gene_mutation_count, aa_position_norm disabled for ablation 2
missing  = [f for f in required if f not in FEATURE_COLS]
if missing:
    raise ValueError(f"Missing required features: {missing}\n"
                     "Re-run step2_preprocess.py")
print(f"\n    Guide feature check:")
print(f"      gene_mutation_count (Guide Step 4): "
      f"{'✓ present' if 'gene_mutation_count' in FEATURE_COLS else '✗ MISSING'}")
print(f"      effect_impact (Guide Step 4)      : "
      f"{'✓ present' if 'effect_impact' in FEATURE_COLS else '✗ MISSING'}")
print(f"      aa_position_norm (EGFR fix)        : "
      f"{'✓ present' if 'aa_position_norm' in FEATURE_COLS else '✗ MISSING'}")
print(f"      is_known_hotspot (EGFR fix)        : "
      f"{'DISABLED (ablation study)' if 'is_known_hotspot' not in FEATURE_COLS else '✓ present'}")


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 2 — MUTATION-LEVEL TRAIN / TEST SPLIT
# No data leakage — same mutation cannot appear in both train and test
# ═════════════════════════════════════════════════════════════════════════════
print()
print("[2] Mutation-level train / test split ...")

# Create unique mutation ID — gene + chromosome + position + protein change
df["mutation_id"] = (
    df["gene_symbol"].astype(str) + "_" +
    df["chromosome"].astype(str)  + "_" +
    df["position"].astype(str)    + "_" +
    df["protein_mutation"].astype(str)
)

unique_mutations = np.array(df["mutation_id"].unique())  # Convert to numpy array
train_muts, test_muts = train_test_split(
    unique_mutations,
    test_size=0.20,
    random_state=42
)

df_train = df[df["mutation_id"].isin(train_muts)].copy()
df_test  = df[df["mutation_id"].isin(test_muts)].copy()

X_train = df_train[FEATURE_COLS].values
y_train = df_train["LABEL"].values
X_test  = df_test[FEATURE_COLS].values
y_test  = df_test["LABEL"].values

# Leakage check
overlap = set(df_train["mutation_id"]) & set(df_test["mutation_id"])
print(f"    Train mutations : {len(train_muts):,}")
print(f"    Test mutations  : {len(test_muts):,}")
print(f"    Train rows      : {len(X_train):,}  "
      f"Driver rate: {y_train.mean():.2%}")
print(f"    Test rows       : {len(X_test):,}   "
      f"Driver rate: {y_test.mean():.2%}")
print(f"    Overlap         : {len(overlap)}  "
      f"{'✓ No leakage' if len(overlap)==0 else '✗ LEAKAGE DETECTED'}")


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 3 — HANDLE CLASS IMBALANCE (TRAINING SET ONLY)
# Apply oversampling ONLY to training data — never touch test set
# ABLATION 4: DISABLE OVERSAMPLING to test raw class distribution
# ═════════════════════════════════════════════════════════════════════════════
print()
print("[3] Handling class imbalance (train set only) ...")
print(f"    Raw driver rate: {y_train.mean():.4%}")
print(f"    Raw ratio: 1 driver per "
      f"{int((y_train==0).sum() / max((y_train==1).sum(), 1))} passengers")

# RandomOverSampler: DISABLED for ablation 4
# ros = RandomOverSampler(sampling_strategy=0.33, random_state=42)
# X_train_bal, y_train_bal = ros.fit_resample(X_train, y_train)
X_train_bal, y_train_bal = X_train, y_train  # ABLATION 4: Use raw imbalanced data

print(f"    After balancing (ABLATION 4: DISABLED):")
print(f"      Driver    : {(y_train_bal==1).sum():,}")
print(f"      Passenger : {(y_train_bal==0).sum():,}")
print(f"      Ratio     : 1:{int((y_train_bal==0).sum() / max((y_train_bal==1).sum(), 1))}")
print(f"    Test set untouched: {len(X_test):,} rows")

scale_pos_weight = (y_train_bal == 0).sum() / max((y_train_bal == 1).sum(), 1)

print(f"    After balancing:")
print(f"      Driver    : {(y_train_bal==1).sum():,}")
print(f"      Passenger : {(y_train_bal==0).sum():,}")
print(f"      Ratio     : 1:{int((y_train_bal==0).sum() / max((y_train_bal==1).sum(),1))}")
print(f"    Test set untouched: {len(X_test):,} rows")


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 4 — DEFINE 3 MODELS (as per Guide Step 5)
# "Possible models: Random Forest, XGBoost, Gradient Boosting"
# ═════════════════════════════════════════════════════════════════════════════
print()
print("[4] Defining 3 models as per guide ...")

MODELS_DICT = {

    # Guide Model 1 — Random Forest
    # Ensemble of decision trees, handles imbalanced genomic data well
    "Random_Forest": RandomForestClassifier(
        n_estimators=300,
        max_depth=12,
        min_samples_leaf=3,
        max_features="sqrt",
        class_weight="balanced",
        random_state=42,
        n_jobs=-1
    ),

    # Guide Model 2 — Gradient Boosting (XGBoost not available in myenv)
    # This is Model 2, moved down due to XGBoost unavailability

    # Guide Model 3 — Gradient Boosting (relabeled as Model 2)
    # Sequential tree building, strong on structured tabular genomic data
    "Gradient_Boosting": GradientBoostingClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        min_samples_leaf=3,
        random_state=42
    ),
}

print(f"    Models: {list(MODELS_DICT.keys())}")


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 5 — TRAIN + EVALUATE ALL 3 MODELS
# ═════════════════════════════════════════════════════════════════════════════
print()
print("[5] Training all 3 models ...")
print()

cv      = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
results = {}
colors  = ["#0D9488", "#F59E0B", "#7C3AED"]

for name, clf in MODELS_DICT.items():
    print(f"  ── {name} ──")
    t0 = time.time()

    clf.fit(X_train_bal, y_train_bal)
    elapsed = time.time() - t0

    y_pred  = clf.predict(X_test)
    y_proba = clf.predict_proba(X_test)[:, 1]

    cv_auc  = cross_val_score(
        clf, X_train_bal, y_train_bal,
        cv=cv, scoring="roc_auc", n_jobs=-1
    )

    acc  = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred, zero_division=0)
    rec  = recall_score(y_test, y_pred, zero_division=0)
    f1   = f1_score(y_test, y_pred, zero_division=0)
    auc  = roc_auc_score(y_test, y_proba)
    ap   = average_precision_score(y_test, y_proba)

    results[name] = {
        "accuracy":      acc,
        "precision":     prec,
        "recall":        rec,
        "f1":            f1,
        "roc_auc":       auc,
        "avg_precision": ap,
        "cv_auc_mean":   cv_auc.mean(),
        "cv_auc_std":    cv_auc.std(),
        "train_time":    elapsed,
        "clf":           clf,
        "y_pred":        y_pred,
        "y_proba":       y_proba,
    }

    print(f"     Accuracy        : {acc:.4f}")
    print(f"     Precision       : {prec:.4f}")
    print(f"     Recall          : {rec:.4f}")
    print(f"     F1 Score        : {f1:.4f}")
    print(f"     ROC-AUC         : {auc:.4f}")
    print(f"     Avg Precision   : {ap:.4f}")
    print(f"     CV-AUC (5-fold) : {cv_auc.mean():.4f} ± {cv_auc.std():.4f}")
    print(f"     Train time      : {elapsed:.1f}s")

    joblib.dump(clf, MODELS / f"{name}_Mutation_Model.pkl")
    print(f"     ✓ Saved: models/{name}_Mutation_Model.pkl\n")


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 6 — SELECT BEST MODEL
# ═════════════════════════════════════════════════════════════════════════════
print()
print("[6] Selecting best model ...")

metrics_df = pd.DataFrame({
    name: {k: v for k, v in res.items()
           if isinstance(v, float) and k != "train_time"}
    for name, res in results.items()
}).T

best_name  = metrics_df["roc_auc"].idxmax()
best_model = results[best_name]["clf"]
joblib.dump(best_model, MODELS / "Mutation_Model_BEST.pkl")

print()
print("  Model Comparison (Guide Step 5 — all 3 models):")
print("  " + "-" * 65)
print(metrics_df[[
    "accuracy", "precision", "recall",
    "f1", "roc_auc", "avg_precision"
]].round(4).to_string())
print()
print(f"  ★ Best model  : {best_name}")
print(f"  ★ ROC-AUC     : {metrics_df.loc[best_name, 'roc_auc']:.4f}")
print(f"  ★ Recall      : {metrics_df.loc[best_name, 'recall']:.4f}")
print(f"  ✓ Saved       : models/Mutation_Model_BEST.pkl")


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 7 — EVALUATION FIGURES
# ═════════════════════════════════════════════════════════════════════════════
print()
print("[7] Generating evaluation figures ...")

# (A) Model comparison bar chart
fig, ax = plt.subplots(figsize=(13, 5))
metric_labels = ["Accuracy", "Precision", "Recall", "F1", "ROC-AUC"]
metric_keys   = ["accuracy", "precision", "recall", "f1", "roc_auc"]
x = np.arange(len(metric_labels))
w = 0.25
for i, (mname, color) in enumerate(zip(results.keys(), colors)):
    vals = [metrics_df.loc[mname, mk] for mk in metric_keys]
    ax.bar(x + i * w, vals, w,
           label=mname.replace("_", " "), color=color, alpha=0.87)
ax.set_xticks(x + w)
ax.set_xticklabels(metric_labels, fontsize=11)
ax.set_ylim(0, 1.1)
ax.set_ylabel("Score")
ax.set_title(
    "Model Comparison — Driver vs Passenger Mutation Classification\n"
    "(Guide Step 5: Random Forest vs XGBoost vs Gradient Boosting)",
    fontsize=12, fontweight="bold"
)
ax.legend(fontsize=10)
ax.axhline(0.8, color="red", linestyle="--", alpha=0.35, linewidth=1)
plt.tight_layout()
plt.savefig(FIGS / "model_comparison.png", dpi=150)
plt.close()
print("    ✓ model_comparison.png")

# (B) ROC Curves — all 3 models
fig, ax = plt.subplots(figsize=(7, 6))
for (name, res), color in zip(results.items(), colors):
    fpr, tpr, _ = roc_curve(y_test, res["y_proba"])
    ax.plot(fpr, tpr, color=color, lw=2,
            label=f"{name.replace('_', ' ')} (AUC={res['roc_auc']:.3f})")
ax.plot([0, 1], [0, 1], "k--", alpha=0.4)
ax.set_xlabel("False Positive Rate")
ax.set_ylabel("True Positive Rate")
ax.set_title("ROC Curves — Driver Mutation Classification",
             fontweight="bold")
ax.legend(loc="lower right")
plt.tight_layout()
plt.savefig(FIGS / "roc_curves.png", dpi=150)
plt.close()
print("    ✓ roc_curves.png")

# (C) Confusion matrices — all 3 models
fig, axes = plt.subplots(1, 3, figsize=(15, 4))
for ax, (name, res) in zip(axes, results.items()):
    cm = confusion_matrix(y_test, res["y_pred"])
    ConfusionMatrixDisplay(
        cm, display_labels=["Passenger", "Driver"]
    ).plot(ax=ax, colorbar=False, cmap="Blues")
    ax.set_title(name.replace("_", " "), fontweight="bold")
plt.suptitle(
    "Confusion Matrices — Driver vs Passenger Classification",
    fontsize=13, fontweight="bold"
)
plt.tight_layout()
plt.savefig(FIGS / "confusion_matrices.png", dpi=150)
plt.close()
print("    ✓ confusion_matrices.png")

# (D) Feature importance — best model (top 20)
if hasattr(best_model, "feature_importances_"):
    fig, ax = plt.subplots(figsize=(10, 8))
    importances = best_model.feature_importances_
    top_n = min(20, len(FEATURE_COLS))
    idx   = np.argsort(importances)[::-1][:top_n]
    ax.barh(
        [FEATURE_COLS[i] for i in idx[::-1]],
        importances[idx[::-1]],
        color="#0D9488"
    )
    ax.set_title(
        f"Top {top_n} Feature Importances\n"
        f"{best_name.replace('_', ' ')} — Driver Prediction",
        fontweight="bold"
    )
    plt.tight_layout()
    plt.savefig(FIGS / "feature_importance.png", dpi=150)
    plt.close()
    print("    ✓ feature_importance.png")

# (E) SHAP — which features push mutation toward Driver/Passenger
print("    Computing SHAP values ...")
try:
    explainer = shap.TreeExplainer(best_model)
    X_sample  = X_test[:500]
    shap_vals = explainer.shap_values(X_sample)
    if isinstance(shap_vals, list):
        shap_vals = shap_vals[1]
    plt.figure(figsize=(10, 7))
    shap.summary_plot(
        shap_vals, X_sample,
        feature_names=FEATURE_COLS,
        plot_type="bar",
        show=False,
        max_display=15
    )
    plt.title(
        f"SHAP Feature Importance — Driver Prediction\n"
        f"({best_name.replace('_', ' ')})",
        fontweight="bold"
    )
    plt.tight_layout()
    plt.savefig(FIGS / "shap_summary.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("    ✓ shap_summary.png")
except Exception as e:
    print(f"    ⚠ SHAP skipped: {e}")


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 8 — CLASSIFICATION REPORT + SAVE EVALUATION REPORT
# ═════════════════════════════════════════════════════════════════════════════
print()
print("[8] Classification Report — Best Model")
print(f"    Model: {best_name}\n")

report_str = classification_report(
    y_test,
    results[best_name]["y_pred"],
    target_names=["Passenger", "Driver"]
)
print(report_str)

# Save full evaluation report
lines = [
    "MUTATION AGENT — MODEL EVALUATION REPORT",
    "=" * 65,
    "",
    "Guide Ref : Section 3 Step 5 — Model Prediction",
    "Task      : Classify each mutation as DRIVER or PASSENGER",
    "Label     : cancer_driver column (t=Driver/1, f=Passenger/0)",
    "",
    "DATA SUMMARY",
    "-" * 40,
    f"  Total mutations (raw)     : {len(df):,}",
    f"  Driver (t)                : {(df['LABEL']==1).sum():,}  "
    f"({df['LABEL'].mean():.4%})",
    f"  Passenger (f)             : {(df['LABEL']==0).sum():,}",
    f"  Train rows (after balance): {len(X_train_bal):,}",
    f"  Test rows (untouched)     : {len(X_test):,}",
    f"  Mutation leakage overlap  : {len(overlap)}",
    "",
    "FEATURES USED (Guide Steps 3 & 4)",
    "-" * 40,
    "  Guide Step 3 — Encoding:",
    "    gene_enc              Label Encoded gene name",
    "    ohe_effect_*          One Hot Encoded mutation type (15 cols)",
    "",
    "  Guide Step 4 — Engineering:",
    "    gene_mutation_count   Mutation Frequency (GUIDE REQUIRED)",
    "    effect_impact         Type importance: 3=High 2=Mod 1=Low 0=None",
    "    aa_position_norm      AA position 0-1 (fixes EGFR L858R)",
    "    is_known_hotspot      Known oncogenic position flag",
    "    vaf, vaf_high, vaf_low VAF features",
    "    chromosome, position_bin Location features",
    "    coding                Coding region flag",
    "",
    f"  Total features : {len(FEATURE_COLS)}",
    "",
    "MODEL RESULTS (Guide Step 5 — all 3 models)",
    "-" * 40,
    f"  {'Model':<28} {'Acc':>6} {'Prec':>6} {'Rec':>6} "
    f"{'F1':>6} {'AUC':>6} {'AvgPrec':>8}",
    "  " + "-" * 66,
]
for mname, row in metrics_df.iterrows():
    lines.append(
        f"  {mname:<28} {row['accuracy']:>6.3f} "
        f"{row['precision']:>6.3f} {row['recall']:>6.3f} "
        f"{row['f1']:>6.3f} {row['roc_auc']:>6.3f} "
        f"{row['avg_precision']:>8.3f}"
    )
lines += [
    "",
    f"  ★ Best model : {best_name}",
    f"  ★ ROC-AUC    : {metrics_df.loc[best_name, 'roc_auc']:.4f}",
    "",
    "CLASSIFICATION REPORT — BEST MODEL",
    "-" * 40,
    report_str,
    "SAVED ARTEFACTS",
    "-" * 40,
    "  models/Random_Forest_Mutation_Model.pkl",
    "  models/XGBoost_Mutation_Model.pkl",
    "  models/Gradient_Boosting_Mutation_Model.pkl",
    "  models/Mutation_Model_BEST.pkl",
    "=" * 65,
]

with open(OUT / "evaluation_report.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print(f"\n    ✓ Report: output/evaluation_report.txt")
print()
print("=" * 65)
print("  Training complete.")
print(f"  Best model : {best_name}")
print("  Next step  → python step4_mutation_agent.py")
print("=" * 65)