# ⚡ Gradient Boosting & XGBoost Models: Boosting Specifications

## 📌 Document Metadata
*   **Model Names**: Gradient Boosting Classifier (`gradient_boosting_pipeline.pkl`) & XGBoost Classifier
*   **Role**: Primary high-performance single models inside XMARs, capturing complex non-linear somatic interactions.
*   **Code Implementation**: [ml_pipeline.py](file:///c:/Users/rohit/Desktop/study/AI_ML/mini%20project-XMARs/mini_project/ml_pipeline.py#L162-L168)
*   **Reference Document**: [xmarreasearchpaper.docx](file:///c:/Users/rohit/Desktop/study/AI_ML/mini%20project-XMARs/mini_project/xmarreasearchpaper.docx)

---

## 🔬 Model Overview & Architecture
Boosting classifiers are supervised learning algorithms that build an ensemble of weak decision trees sequentially. Each new tree corrects the residual errors of the preceding trees by minimizing a loss function (e.g. log-loss) via gradient descent.

In the XMARs platform, boosting is represented by:
1.  **Gradient Boosting Classifier (`gradient_boosting_pipeline.pkl`)**: Used in the production variant pathogenicity pipeline.
2.  **XGBoost (Extreme Gradient Boosting)**: Evaluated in the research paper's drug resistance prediction workflow, representing an optimized, regularized boosting implementation.

---

## 📈 Performance Summary

### 1. Gradient Boosting Classifier (`ml_pipeline.py`)
In the production pipeline, the Gradient Boosting model outperforms all other single models in variant pathogenicity classification:
*   **Accuracy**: **98.09%**
*   **Precision**: **98.10%**
*   **Recall**: **98.09%**
*   **F1-Score**: **0.9809**
*   **File Size**: 1.9 MB

### 2. XGBoost Drug Resistance Classifier (Research Paper - Table 1)
In the RIT research paper, the regularized XGBoost classifier outperformed the baseline Random Forest model in predicting targeted drug response across cell line populations:
*   **Accuracy**: **84.2%**
*   **Precision**: **0.83**
*   **Recall**: **0.82**
*   **F1-Score**: **0.82**
*   **AUC Score**: **0.84**

---

## ⚙️ Hyperparameters & Configuration

*   **Production Variant Pathogenicity Model (`ml_pipeline.py`)**:
    *   `n_estimators=200`: Sequentially fits 200 boosting stages.
    *   `learning_rate=0.1`: Steps the gradient descent updates to prevent overshooting.
    *   `max_depth=7`: Sets tree depth to 7 to allow interaction between up to 7 genomic features while maintaining generalization.
    *   `min_samples_split=5`: Minimum sample split parameter.
    *   `subsample=0.9`: Employs stochastic gradient boosting by training on 90% of the sample slice at each boosting iteration to reduce variance.
    *   `random_state=42`: Controls exact seed consistency.
*   **Research Paper Drug Resistance XGBoost Model**:
    *   Optimized with regularized parameters ($L_1$/$L_2$ regularization $\alpha$ and $\lambda$) to mitigate noises in experimental GDSC2 and cBioPortal datasets.
    *   Tested under a **Stratified 5-fold cross-validation** protocol.

---

## 📊 Feature Importance & Attributions
Gradient Boosting and XGBoost predictions are highly explainable via SHAP. The SHAP explainability analysis in Section 3.2 of the paper notes that mutations in the critical growth-receptive tyrosine kinases (`EGFR`, `KRAS`, `ALK`, `MET`) represent the primary nodes in the sequential decision splits. 

*   **Positive SHAP Impact**: Mutations located on activating positions in `EGFR` or `ALK` yield high feature importances, shifting the prediction toward specific treatment sensitivity.
*   **Negative SHAP Impact / Bypass Resistance**: Disruptive frameshift mutations in tumor suppressors like `PTEN` or `TP53` reverse the boosting direction, contributing strongly to drug resistance scores (log-odds boost).
