# 🥇 Soft Voting Ensemble: Production Pipeline Specification

## 📌 Document Metadata
*   **Model Name**: Soft Voting Ensemble Classifier (`ensemble_pipeline.pkl`)
*   **Role**: Primary production model of XMARs, achieving peak predictive performance and minimal decision variance.
*   **Code Implementation**: [ml_pipeline.py](file:///c:/Users/rohit/Desktop/study/AI_ML/mini%20project-XMARs/mini_project/ml_pipeline.py#L178-L189)
*   **Reference Document**: [xmarreasearchpaper.docx](file:///c:/Users/rohit/Desktop/study/AI_ML/mini%20project-XMARs/mini_project/xmarreasearchpaper.docx)

---

## 🔬 Model Overview & Architecture
Ensemble learning consolidates multiple classifiers to construct a superior meta-model. In a **Soft Voting Classifier**, each base estimator outputs a probability score for each target label. The ensemble then computes the average probability across all base estimators:

$$\hat{y} = \arg\max_i \sum_{j=1}^{M} w_j P(y = i \mid M_j)$$

*Where $M_j$ is the $j$-th classifier, $w_j$ represents its weight (even weighting by default), and $P(y = i \mid M_j)$ is the predicted probability for label $i$.*

By averaging predicted probabilities, soft voting leverages the confidence scores of the strongest classifiers, smoothing out individual model errors and providing higher accuracy than any single model alone.

```
       ┌──────────────────────── Patient Mutation Profile ────────────────────────┐
       │                                                                          │
       ▼                                  ▼                                       ▼
 [Random Forest]                  [Gradient Boosting]                       [AdaBoost]
  - Probability: 92% Driver        - Probability: 96% Driver                 - Probability: 94% Driver
       │                                  │                                       │
       └─────────────────────────┬────────┴───────────────────────────────────────┘
                                 ▼
                         [Average Probabilities]
                                 │
                                 ▼
                     [Soft Voting Ensemble Decision]
                      - Consensus: 94% Driver Pathogenicity
```

---

## 📈 Performance Summary

### 1. Variant Pathogenicity Classifier (`ml_pipeline.py`)
The soft-voting ensemble represents the peak production model of the XMARs variant pathogenicity pipeline, yielding the highest metrics across the board:
*   **Accuracy**: **98.14%** ⭐ (Production Choice)
*   **Precision**: **98.16%**
*   **Recall**: **98.14%**
*   **F1-Score**: **0.9814**
*   **File Size**: 16.3 MB

### 2. Drug Resistance Classifier (Research Paper - Table 1)
In the RIT study, the ensemble pipeline combined the Random Forest and XGBoost predictions, achieving outstanding accuracy:
*   **Accuracy**: **85.1%** ⭐ (Best in Paper)
*   **Precision**: **0.84**
*   **Recall**: **0.83**
*   **F1-Score**: **0.83**
*   **AUC Score**: **0.82**

---

## ⚙️ Hyperparameters & Configuration
The training configuration utilized for the Ensemble Classifier in `ml_pipeline.py` is outlined below:

*   **Estimators**:
    1.  `rf`: RandomForestClassifier (200 estimators, max depth 20)
    2.  `gb`: GradientBoostingClassifier (200 estimators, learning rate 0.1, max depth 7)
    3.  `ada`: AdaBoostClassifier (100 estimators, learning rate 1.0)
*   **Voting Mechanics**: `voting='soft'` to enable probability averaging rather than hard majority counts.
*   **Execution**: Model is trained on scaled feature inputs using the RobustScaler (`scaler_pipeline.pkl`) to guarantee feature boundaries are mathematically consistent across all sub-estimators.
