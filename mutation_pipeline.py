"""Mutation analysis ML pipeline for lung cancer genomic MAF datasets.

This script builds an end-to-end training workflow to predict whether a mutation
is likely to be biologically important (driver-like) using TCGA/cBioPortal-style
mutation annotation files.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List, Optional, Tuple

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

try:
    from xgboost import XGBClassifier
except Exception:  # xgboost is optional in some environments
    XGBClassifier = None


DEFAULT_DRIVER_GENES = {
    "TP53",
    "KRAS",
    "EGFR",
    "STK11",
    "KEAP1",
    "NF1",
    "BRAF",
    "PIK3CA",
    "RB1",
    "MET",
    "ERBB2",
    "ALK",
    "ROS1",
    "RET",
    "NTRK1",
    "SMARCA4",
    "ARID1A",
    "CDKN2A",
    "PTEN",
    "MAP2K1",
}

HIGH_IMPACT_VARIANTS = {
    "Nonsense_Mutation",
    "Frame_Shift_Del",
    "Frame_Shift_Ins",
    "Splice_Site",
    "Translation_Start_Site",
    "Nonstop_Mutation",
}


RECOMMENDED_COLUMNS = [
    "Tumor_Sample_Barcode",
    "Hugo_Symbol",
    "Variant_Classification",
    "Variant_Type",
    "Chromosome",
    "Start_Position",
    "End_Position",
    "Reference_Allele",
    "Tumor_Seq_Allele2",
]


COLUMN_ALIASES = {
    "Patient_ID": "Tumor_Sample_Barcode",
    "Gene": "Hugo_Symbol",
    "Tumor_Seq_Allele": "Tumor_Seq_Allele2",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train lung mutation importance classifier")
    parser.add_argument(
        "--input-files",
        nargs="+",
        required=True,
        help="Path(s) to mutation files (.maf, .csv, .tsv) from TCGA/cBioPortal.",
    )
    parser.add_argument(
        "--label-column",
        default=None,
        help="Optional existing label column (1=important, 0=not). If missing, heuristic labels are created.",
    )
    parser.add_argument(
        "--model",
        choices=["random_forest", "gradient_boosting", "xgboost"],
        default="random_forest",
        help="Classifier to train.",
    )
    parser.add_argument(
        "--output-model",
        default="mutation_model.pkl",
        help="Output path for trained model pipeline.",
    )
    parser.add_argument(
        "--output-metrics",
        default="metrics.json",
        help="Output path for evaluation metrics JSON.",
    )
    parser.add_argument(
        "--output-confusion",
        default="confusion_matrix.png",
        help="Output path for confusion matrix image.",
    )
    parser.add_argument(
        "--output-shap",
        default="shap_feature_importance.png",
        help="Output path for optional SHAP summary image.",
    )
    parser.add_argument(
        "--test-size",
        type=float,
        default=0.2,
        help="Test split size (default: 0.2).",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="Random seed for reproducibility.",
    )
    return parser.parse_args()


def _read_single_dataset(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".maf":
        return pd.read_csv(path, sep="\t", comment="#", low_memory=False)
    if suffix in {".tsv", ".txt"}:
        return pd.read_csv(path, sep="\t", low_memory=False)
    if suffix == ".csv":
        return pd.read_csv(path, low_memory=False)
    raise ValueError(f"Unsupported file extension for {path}")


def load_datasets(paths: List[str]) -> pd.DataFrame:
    """Load and concatenate multiple mutation datasets."""
    frames = []
    for p in paths:
        path = Path(p)
        if not path.exists():
            raise FileNotFoundError(f"Input file not found: {path}")
        frame = _read_single_dataset(path)
        frame["_source_file"] = path.name
        frames.append(frame)

    if not frames:
        raise ValueError("No datasets loaded.")

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.rename(columns=COLUMN_ALIASES)
    return combined


def select_relevant_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Keep high-value columns for mutation-level modeling."""
    available = [c for c in RECOMMENDED_COLUMNS if c in df.columns]
    if not available:
        raise ValueError("No expected MAF columns were found in dataset.")

    selected = df[available].copy()
    selected = selected.rename(
        columns={
            "Tumor_Sample_Barcode": "Patient_ID",
            "Hugo_Symbol": "Gene",
            "Tumor_Seq_Allele2": "Tumor_Seq_Allele",
        }
    )
    return selected


def create_features(df: pd.DataFrame) -> pd.DataFrame:
    """Create biologically relevant engineered features."""
    out = df.copy()

    out["Gene"] = out["Gene"].fillna("UNKNOWN")
    out["Variant_Classification"] = out["Variant_Classification"].fillna("Unknown")
    out["Variant_Type"] = out["Variant_Type"].fillna("Unknown")

    gene_freq = out["Gene"].value_counts(normalize=True)
    gene_count = out["Gene"].value_counts()
    out["Gene_Mutation_Frequency"] = out["Gene"].map(gene_freq).astype(float)
    out["Gene_Mutation_Count"] = out["Gene"].map(gene_count).astype(float)

    out["Variant_Impact"] = np.where(
        out["Variant_Classification"].isin(HIGH_IMPACT_VARIANTS),
        "High",
        "Moderate_or_Low",
    )

    # mutation length can capture insertion/deletion behavior
    if "Start_Position" in out.columns and "End_Position" in out.columns:
        out["Mutation_Length"] = (
            pd.to_numeric(out["End_Position"], errors="coerce")
            - pd.to_numeric(out["Start_Position"], errors="coerce")
            + 1
        )

    return out


def build_target(df: pd.DataFrame, label_column: Optional[str]) -> pd.Series:
    """Create binary label for mutation importance.

    Priority:
    1) user-provided label column (already 0/1 or castable)
    2) heuristic label from known driver genes + high-impact variant classes
    """
    if label_column:
        if label_column not in df.columns:
            raise ValueError(f"Label column '{label_column}' was not found in data")
        y = pd.to_numeric(df[label_column], errors="coerce")
        if y.isna().all():
            raise ValueError("Provided label column cannot be converted to numeric values")
        return y.fillna(0).astype(int)

    heuristic = (
        df["Gene"].isin(DEFAULT_DRIVER_GENES)
        | df["Variant_Classification"].isin(HIGH_IMPACT_VARIANTS)
    )
    return heuristic.astype(int)


def make_model(name: str, random_state: int):
    if name == "random_forest":
        return RandomForestClassifier(
            n_estimators=400,
            random_state=random_state,
            class_weight="balanced",
            n_jobs=-1,
        )
    if name == "gradient_boosting":
        return GradientBoostingClassifier(random_state=random_state)
    if name == "xgboost":
        if XGBClassifier is None:
            raise ImportError("xgboost is not installed but model='xgboost' was requested")
        return XGBClassifier(
            n_estimators=400,
            learning_rate=0.05,
            max_depth=6,
            subsample=0.85,
            colsample_bytree=0.85,
            random_state=random_state,
            eval_metric="logloss",
        )
    raise ValueError(f"Unknown model '{name}'")


def build_pipeline(feature_df: pd.DataFrame, model_name: str, random_state: int) -> Pipeline:
    categorical_features = [
        c
        for c in [
            "Gene",
            "Variant_Classification",
            "Variant_Type",
            "Variant_Impact",
            "Chromosome",
            "Reference_Allele",
            "Tumor_Seq_Allele",
            "Patient_ID",
        ]
        if c in feature_df.columns
    ]
    numeric_features = [
        c
        for c in ["Start_Position", "End_Position", "Gene_Mutation_Frequency", "Gene_Mutation_Count", "Mutation_Length"]
        if c in feature_df.columns
    ]

    preprocessor = ColumnTransformer(
        transformers=[
            (
                "categorical",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("encoder", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                categorical_features,
            ),
            (
                "numeric",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scaler", StandardScaler()),
                    ]
                ),
                numeric_features,
            ),
        ],
        remainder="drop",
    )

    model = make_model(model_name, random_state)

    return Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("classifier", model),
        ]
    )


def evaluate_model(model: Pipeline, x_test: pd.DataFrame, y_test: pd.Series) -> Tuple[dict, np.ndarray]:
    y_pred = model.predict(x_test)

    if hasattr(model, "predict_proba"):
        y_score = model.predict_proba(x_test)[:, 1]
    elif hasattr(model, "decision_function"):
        y_score = model.decision_function(x_test)
    else:
        y_score = y_pred

    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision": float(precision_score(y_test, y_pred, zero_division=0)),
        "recall": float(recall_score(y_test, y_pred, zero_division=0)),
        "f1": float(f1_score(y_test, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_test, y_score)),
    }

    print("\nClassification Report:\n")
    print(classification_report(y_test, y_pred, zero_division=0))

    cm = confusion_matrix(y_test, y_pred)
    return metrics, cm


def save_confusion_matrix(cm: np.ndarray, path: str) -> None:
    plt.figure(figsize=(6, 5))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", cbar=False)
    plt.title("Confusion Matrix")
    plt.xlabel("Predicted")
    plt.ylabel("Actual")
    plt.tight_layout()
    plt.savefig(path, dpi=200)
    plt.close()


def try_generate_shap(model: Pipeline, x_train: pd.DataFrame, output_path: str) -> Optional[str]:
    """Generate optional SHAP summary plot when SHAP is available."""
    try:
        import shap
    except Exception:
        return None

    try:
        # Use a small sample for efficiency.
        sample_size = min(500, len(x_train))
        x_sample = x_train.sample(sample_size, random_state=42)

        transformed = model.named_steps["preprocessor"].transform(x_sample)
        clf = model.named_steps["classifier"]

        explainer = shap.Explainer(clf)
        shap_values = explainer(transformed)

        plt.figure()
        shap.summary_plot(shap_values, transformed, show=False)
        plt.tight_layout()
        plt.savefig(output_path, dpi=200)
        plt.close()
        return output_path
    except Exception:
        return None


def main() -> None:
    args = parse_args()

    raw = load_datasets(args.input_files)
    if raw.empty:
        raise ValueError("Loaded dataset is empty.")

    selected = select_relevant_columns(raw)
    data = create_features(selected)
    target = build_target(data, args.label_column)

    # Keep only features for modeling
    x = data.copy()
    y = target

    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=args.test_size,
        random_state=args.random_state,
        stratify=y if y.nunique() > 1 else None,
    )

    pipeline = build_pipeline(x_train, args.model, args.random_state)
    pipeline.fit(x_train, y_train)

    metrics, cm = evaluate_model(pipeline, x_test, y_test)
    save_confusion_matrix(cm, args.output_confusion)

    joblib.dump(pipeline, args.output_model)

    with open(args.output_metrics, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    shap_path = try_generate_shap(pipeline, x_train, args.output_shap)

    print("\nTraining completed successfully.")
    print(f"Saved model: {args.output_model}")
    print(f"Saved metrics: {args.output_metrics}")
    print(f"Saved confusion matrix: {args.output_confusion}")
    if shap_path:
        print(f"Saved SHAP summary: {shap_path}")


if __name__ == "__main__":
    main()
