# 🏎️ AdaBoost Classifier: Adaptive Boosting Specifications

## 📌 Document Metadata
*   **Model Name**: AdaBoost Classifier (`adaboost_pipeline.pkl`)
*   **Role**: Highly efficient, lightweight adaptive booster providing model diversity within the ensemble pipeline.
*   **Code Implementation**: [ml_pipeline.py](file:///c:/Users/rohit/Desktop/study/AI_ML/mini%20project-XMARs/mini_project/ml_pipeline.py#L170-L176)
*   **Reference Document**: [xmarreasearchpaper.docx](file:///c:/Users/rohit/Desktop/study/AI_ML/mini%20project-XMARs/mini_project/xmarreasearchpaper.docx)

---

## 🔬 Model Overview & Architecture
AdaBoost (Adaptive Boosting) is a sequential boosting algorithm that fits an initial weak classifier (typically a single-level decision tree or "decision stump") on the training data. In subsequent rounds, the algorithm adaptively adjusts the weights of the training instances:
*   Instances that were incorrectly classified in the previous stage are assigned **higher weights**, forcing the next estimator to focus on hard-to-classify samples.
*   Instances that were correctly classified are assigned **lower weights**.

The final prediction is a weighted majority vote of all the weak estimators. In the XMARs system, AdaBoost provides a fast, memory-efficient predictive model that complements the deep splits of Random Forest and Gradient Boosting.

---

## 📈 Performance Summary

### 1. Variant Pathogenicity Classifier (`ml_pipeline.py`)
In the production pipeline, AdaBoost displays outstanding performance and speed:
*   **Accuracy**: **96.78%**
*   **Precision**: **96.94%**
*   **Recall**: **96.78%**
*   **F1-Score**: **0.9682**
*   **File Size**: **65 KB** ⭐ (Extremely lightweight, making it optimal for resource-constrained edge deployments).

---

## ⚙️ Hyperparameters & Configuration
The training configuration utilized for the AdaBoost model in `ml_pipeline.py` is outlined below:

*   `n_estimators=100`: Fits 100 weak classifiers sequentially.
*   `learning_rate=1.0`: Determines the scale of weight adjustments at each step. A learning rate of 1.0 provides a fast, full adaptation step, balancing speed and classification boundary convergence.
*   `random_state=42`: Seeds the random state to ensure exact replication of the training splits and tree selections.

---

## 📊 Genomic Classification Implications
AdaBoost's reliance on weighted instances makes it particularly sensitive to noisy genomic features or mislabeled outliers (e.g. questionable variants in raw somatic datasets). To mitigate this sensitivity, the XMARs pipeline applies a robust preprocessing layer before feeding features to the model:
*   **Downstream Alignment**: In the final `VotingClassifier` ensemble, AdaBoost acts as a strong regularizer. Because AdaBoost utilizes shallow stumps, it focuses primarily on the most critical linear features (such as `Coding Status` and primary `Gene Identity`).
*   **Interoperability**: When combined with the high-variance trees of Random Forest and the deep gradients of Gradient Boosting, AdaBoost helps stabilize the final soft-voting ensemble boundaries, ensuring high precision when clinical profiles contain incomplete information.
