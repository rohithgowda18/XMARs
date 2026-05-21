# 🌲 Random Forest Classifier: Model Specification

## 📌 Document Metadata
*   **Model Name**: Random Forest Classifier (`random_forest_pipeline.pkl`)
*   **Role**: Primary baseline model for variant classification and genomic feature validation.
*   **Code Implementation**: [ml_pipeline.py](file:///c:/Users/rohit/Desktop/study/AI_ML/mini%20project-XMARs/mini_project/ml_pipeline.py#L153-L161)
*   **Reference Document**: [xmarreasearchpaper.docx](file:///c:/Users/rohit/Desktop/study/AI_ML/mini%20project-XMARs/mini_project/xmarreasearchpaper.docx)

---

## 🔬 Model Overview & Architecture
The Random Forest model is an ensemble meta-estimator that fits a multitude of decision trees on various sub-samples of the dataset. It leverages averaging (bagging) to control over-fitting, improve predictive accuracy, and compute stable feature attributions.

Within the XMARs ecosystem, Random Forest plays a dual role:
1.  **Variant Pathogenicity Classifier**: Predicting whether somatic variants function as drivers vs. passengers based on engineered feature vectors.
2.  **Drug Resistance Classifier (Research Paper Baseline)**: Predicting resistance probabilities directly across cell lines from the GDSC2 and cBioPortal databases.

---

## 📈 Performance Summary

### 1. Variant Pathogenicity Classifier (`ml_pipeline.py`)
In the production pipeline, the Random Forest model trained on balanced somatic mutation features achieves excellent classification metrics:
*   **Accuracy**: **96.97%**
*   **Precision**: **97.15%**
*   **Recall**: **96.97%**
*   **F1-Score**: **0.9701**
*   **File Size**: 6.2 MB

### 2. Drug Resistance Classifier (Research Paper - Table 1)
As presented in the Ramaiah Institute of Technology study, the baseline Random Forest classifier trained directly on drug response outcomes achieved:
*   **Accuracy**: **81.6%**
*   **Precision**: **0.80**
*   **Recall**: **0.79**
*   **F1-Score**: **0.79**
*   **AUC Score**: **0.81**

---

## ⚙️ Hyperparameters & Configuration
The training configurations utilized for the Random Forest model are detailed below:

*   **Production Pipeline Pathogenicity Model (`ml_pipeline.py`)**:
    *   `n_estimators=200`: Fits 200 decision trees to ensure variance reduction.
    *   `max_depth=20`: Limits individual tree expansion to prevent over-fitting.
    *   `min_samples_split=5`: Minimum samples required to split an internal node.
    *   `min_samples_leaf=2`: Minimum samples required to be at a leaf node.
    *   `max_features='sqrt'`: Evaluates $\sqrt{\text{features}}$ variables during node splits.
    *   `class_weight='balanced_subsample'`: Dynamically calculates class weights on the bootstrap sample of each tree to correct target label imbalances.
    *   `random_state=42`: Seeds the random state to ensure exact training reproducibility.
    *   `n_jobs=-1`: Utilizes all available CPU cores to execute training in parallel.
*   **Research Paper Drug Resistance Model**:
    *   `n_estimators=200`: Fits 200 estimators.
    *   `max_depth=10`: Shorter tree depth to restrict complexity on noisier cell line drug labels.
    *   `validation`: Evaluated using a **Stratified 5-fold cross-validation** scheme.

---

## 📊 SHAP Explainability & Key Features
The Random Forest model was evaluated using SHAP (SHapley Additive exPlanations) via `shap.TreeExplainer` in `shap_explainer.py`. 

The explainability module determined that feature importance was dominated by:
1.  **Coding Status** (SHAP Importance: **0.57**): Dictates whether a variant is coding or non-coding.
2.  **Gene Identity** (SHAP Importance: **0.14**): Reflects mutation status across highly specific driver genes (`EGFR`, `KRAS`, `ALK`, `MET`).
3.  **Variant Allele Frequency (VAF)** (SHAP Importance: **0.10**): Ranging from `0.0` to `1.0`. Higher VAFs strongly drive positive Shapley values, shifting predictions toward pathogenicity/resistance.
4.  **Mutation Type** (SHAP Importance: **0.08**): Frameshift and nonsense mutations consistently yielded larger SHAP values compared to missense and silent mutations.
