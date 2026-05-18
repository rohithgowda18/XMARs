import argparse
import json
import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib import pyplot as plt
from sklearn.metrics import confusion_matrix

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("generate-confusion-matrices")

MODEL_EXTENSIONS = {".pkl", ".joblib", ".sav", ".h5", ".pt"}


# -----------------------------------------------------------------------------
# Paths
# -----------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR_DEFAULT = PROJECT_ROOT / "data" / "processed"
MODELS_DIR_DEFAULT = PROJECT_ROOT / "models"
OUTPUT_DIR_DEFAULT = PROJECT_ROOT / "figures" / "confusion_matrices"


# -----------------------------------------------------------------------------
# Dataset reconstruction (mirrors mini_project/train_models.py)
# -----------------------------------------------------------------------------
FEATURE_COLUMNS = [
    "unique_genes",
    "avg_vaf",
    "max_vaf",
    "coding_mutations",
    "total_mutations",
    "cnv_mean",
    "cnv_max",
    "cnv_std",
    "cnv_count",
]


def reconstruct_X_y_test(
    *,
    data_dir: Path,
    test_size: float,
    random_state: int,
) -> Tuple[pd.DataFrame, np.ndarray, pd.DataFrame, np.ndarray, np.ndarray]:
    """
    Reconstruct X_test/y_test with the same data prep and split used in train_models.py.
    """
    from sklearn.model_selection import train_test_split

    mutations = pd.read_csv(data_dir / "mutation_features.csv")
    models = pd.read_csv(data_dir / "01_models_preprocessed.csv")
    cnv = pd.read_csv(data_dir / "02_cnv_preprocessed.csv")

    cnv_summary = cnv.groupby("model_name").agg(
        {"total_copy_number": ["mean", "max", "std"], "cn_category": "count"}
    ).round(3)
    cnv_summary.columns = ["cnv_mean", "cnv_max", "cnv_std", "cnv_count"]
    cnv_summary = cnv_summary.fillna(0)

    mutation_features = mutations.groupby("model_name").agg(
        {"gene_symbol": "nunique", "vaf": ["mean", "max"], "coding": "sum", "LABEL": "count"}
    ).round(3)
    mutation_features.columns = ["unique_genes", "avg_vaf", "max_vaf", "coding_mutations", "total_mutations"]
    mutation_features = mutation_features.fillna(0)

    feature_matrix = mutation_features.merge(cnv_summary, left_index=True, right_index=True, how="inner")

    cancer_types: Dict[str, Any] = {}
    for _, row in models.iterrows():
        cancer_types[row["model_name"]] = row["cancer_type"]

    model_names = feature_matrix.index.tolist()
    targets: List[Any] = []
    valid_models: List[str] = []
    for m in model_names:
        if m in cancer_types:
            targets.append(cancer_types[m])
            valid_models.append(m)

    feature_matrix_valid = feature_matrix.loc[valid_models]
    y_raw = np.array(targets, dtype=object)

    # LabelEncoder (replicate sklearn behavior)
    classes = np.unique(y_raw)
    class_to_idx = {c: i for i, c in enumerate(classes)}
    y = np.array([class_to_idx[v] for v in y_raw], dtype=int)

    # Remove classes with only 1 sample
    class_counts = np.bincount(y)
    valid_classes = np.where(class_counts >= 2)[0]
    if len(valid_classes) < len(classes):
        mask = np.isin(y, valid_classes)
        feature_matrix_valid = feature_matrix_valid.iloc[np.where(mask)[0]]
        y = y[mask]

        # Re-encode
        y_raw2 = np.array([classes[i] for i in y], dtype=object)
        classes2 = np.unique(y_raw2)
        class_to_idx2 = {c: i for i, c in enumerate(classes2)}
        y = np.array([class_to_idx2[v] for v in y_raw2], dtype=int)
        classes = classes2

    X = feature_matrix_valid.copy()
    X = X.reindex(columns=[c for c in FEATURE_COLUMNS if c in X.columns])

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )
    return X_train, y_train, X_test, y_test, classes


# -----------------------------------------------------------------------------
# Model scanning & loading
# -----------------------------------------------------------------------------
def scan_model_files(models_dir: Path) -> List[Path]:
    """
    Scan ONLY the provided directory for supported model files.
    No recursion by default (models are expected directly under /models).
    """
    files: List[Path] = []
    if not models_dir.exists():
        return files

    for p in models_dir.iterdir():
        if p.is_file() and p.suffix.lower() in MODEL_EXTENSIONS:
            files.append(p)

    return sorted(files, key=lambda x: x.name.lower())


def resolve_artifacts_near_model(model_path: Path, fallback_models_dir: Path) -> Tuple[Optional[Path], Optional[Path], Path]:
    """
    Return (scaler.pkl_path, metadata_or_label_encoder_json_path, models_dir_used_for_fallback).
    """
    # Prefer sibling to model if model is inside models/
    candidates = [
        (model_path.parent, model_path.parent / "scaler.pkl", model_path.parent / "metadata.json", model_path.parent / "label_encoder.json"),
        (fallback_models_dir, fallback_models_dir / "scaler.pkl", fallback_models_dir / "metadata.json", fallback_models_dir / "label_encoder.json"),
    ]

    for base, scaler_p, meta_p, le_p in candidates:
        if meta_p.exists() or le_p.exists() or scaler_p.exists():
            return (scaler_p if scaler_p.exists() else None, le_p if le_p.exists() else None, base)
    return (None, None, fallback_models_dir)


def try_load_model(model_path: Path) -> Any:
    suffix = model_path.suffix.lower()
    if suffix in {".pkl", ".joblib", ".sav"}:
        return joblib.load(model_path)
    # For .h5 / .pt we skip gracefully (without adding new heavy deps)
    raise RuntimeError(f"Unsupported model format for auto-loading in this script: {suffix}")


# -----------------------------------------------------------------------------
# Visualization
# -----------------------------------------------------------------------------
def plot_cm_heatmap(
    *,
    cm: np.ndarray,
    title: str,
    out_path: Path,
    normalize: bool,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if normalize:
        cm_plot = cm.astype(float)
        row_sums = cm_plot.sum(axis=1, keepdims=True)
        cm_plot = np.divide(cm_plot, row_sums, out=np.zeros_like(cm_plot), where=row_sums != 0)
        fmt = ".2f"
    else:
        cm_plot = cm
        fmt = "d"

    # Dynamically adjust figure size based on number of classes
    n_classes = cm.shape[0]
    if n_classes <= 10:
        figsize = (8, 6)
        fontsize = 10
    elif n_classes <= 20:
        figsize = (12, 10)
        fontsize = 9
    else:
        # For large matrices, scale appropriately
        min_size = max(10, n_classes * 0.25)
        figsize = (min_size, min_size)
        fontsize = 6 if n_classes > 30 else 8

    plt.figure(figsize=figsize, dpi=300)
    sns.set_theme(style="white")

    ax = sns.heatmap(
        cm_plot,
        annot=True,
        fmt=fmt,
        cmap="Blues",
        cbar=True,
        square=True,
        linewidths=0.3,
        linecolor="white",
        xticklabels=[str(i) for i in range(cm.shape[1])],
        yticklabels=[str(i) for i in range(cm.shape[0])],
        cbar_kws={"label": "Normalized Count"},
        annot_kws={"size": fontsize - 2} if fontsize > 6 else {"size": 5},
    )
    ax.set_xlabel("Predicted label", fontsize=fontsize)
    ax.set_ylabel("Actual label", fontsize=fontsize)
    ax.set_title(title, fontsize=fontsize + 2, pad=20)

    # Adjust tick label sizes
    ax.tick_params(axis='both', which='major', labelsize=fontsize - 1)
    
    plt.xticks(rotation=45, ha="right")
    plt.yticks(rotation=0)

    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close()


def sanitize_filename(stem: str) -> str:
    keep = []
    for ch in stem:
        if ch.isalnum() or ch in ("-", "_"):
            keep.append(ch)
        else:
            keep.append("_")
    # collapse repeats
    s = "".join(keep)
    while "__" in s:
        s = s.replace("__", "_")
    return s.strip("_").lower()


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
@dataclass
class ModelRun:
    model_path: Path
    model_name: str
    status: str  # success/failed
    reason: str = ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate normalized confusion matrices ONLY for models in mini_project/models/.")
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR_DEFAULT)
    parser.add_argument("--models-dir", type=Path, default=MODELS_DIR_DEFAULT)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR_DEFAULT)
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()

    data_dir: Path = args.data_dir
    models_dir: Path = args.models_dir
    output_dir: Path = args.output_dir

    if not data_dir.exists():
        raise FileNotFoundError(f"Data dir not found: {data_dir}")
    if not models_dir.exists():
        raise FileNotFoundError(f"Models dir not found: {models_dir}")

    model_files = scan_model_files(models_dir)
    print(f"Total models found: {len(model_files)}")
    if not model_files:
        return

    # Reconstruct test data once
    logger.info("Reconstructing X_test / y_test...")
    _, _, X_test, y_test, classes = reconstruct_X_y_test(
        data_dir=data_dir,
        test_size=args.test_size,
        random_state=args.random_state,
    )

    from sklearn.metrics import classification_report

    results: List[ModelRun] = []
    for model_path in model_files:
        model_name = model_path.stem
        try:
            scaler_path, _, _ = resolve_artifacts_near_model(model_path, models_dir)

            logger.info(f"Loading model: {model_path}")
            model = try_load_model(model_path)

            X_input = X_test
            if model_name.lower() == "logistic_regression" and scaler_path and scaler_path.exists():
                scaler = joblib.load(scaler_path)
                X_input = pd.DataFrame(
                    scaler.transform(X_test),
                    columns=X_test.columns,
                    index=X_test.index,
                )

            if not hasattr(model, "predict"):
                raise RuntimeError("Loaded object does not implement predict().")

            y_pred = model.predict(X_input)
            cm = confusion_matrix(y_test, y_pred)

            safe_stem = sanitize_filename(model_name)
            out_path = output_dir / f"{safe_stem}_cm.png"

            # Normalized confusion matrix
            plot_cm_heatmap(
                cm=cm,
                title=f"{model_name} Confusion Matrix",
                out_path=out_path,
                normalize=True,
            )

            # Classification report
            report_txt_path = output_dir / f"{safe_stem}_classification_report.txt"
            report_csv_path = output_dir / f"{safe_stem}_classification_report.csv"

            # Use compact encoded numeric labels for reports too (avoid long cancer names)
            encoded_labels = [str(i) for i in range(cm.shape[0])]
            report_text = classification_report(
                y_test, y_pred, target_names=encoded_labels, zero_division=0
            )
            with open(report_txt_path, "w", encoding="utf-8") as f:
                f.write(report_text)

            # Parse report into dataframe (sklearn format)
            # Example lines start with class label then metrics, plus accuracy/macro avg/weighted avg.
            report_dict = classification_report(
                y_test, y_pred, target_names=encoded_labels, output_dict=True, zero_division=0
            )
            df_report = pd.DataFrame(report_dict).transpose()
            df_report.to_csv(report_csv_path, index=True)

            results.append(ModelRun(model_path=model_path, model_name=model_name, status="success"))

        except Exception as e:
            reason = f"{type(e).__name__}: {e}"
            results.append(ModelRun(model_path=model_path, model_name=model_name, status="failed", reason=reason))

    success_count = sum(1 for r in results if r.status == "success")
    fail_count = sum(1 for r in results if r.status == "failed")
    print(f"Successfully processed models: {success_count}")
    print(f"Failed models with reasons: {fail_count}")

    failed = [r for r in results if r.status == "failed"]
    if failed:
        print("\nFailed models:")
        for r in failed:
            print(f"- {r.model_path} -> {r.reason}")


if __name__ == "__main__":
    main()
