# 🧬 XMARs: Project Overview & System Architecture

## 📌 Document Metadata
*   **Study Title**: XMARs: An Explainable Multi-Agent Reasoning System for Real-Time Drug Resistance Prediction in Non-Small Cell Lung Cancer
*   **Affiliation**: Ramaiah Institute of Technology, Department of Computer Science and Engineering, Bengaluru, Karnataka, India
*   **Authors**: Dr. S. Seema, Rohith Gowda K., Venkatachala V., Vijay Patil, and Vijay Veerabhadra Patil
*   **Reference Path**: [xmarreasearchpaper.docx](file:///c:/Users/rohit/Desktop/study/AI_ML/mini%20project-XMARs/mini_project/xmarreasearchpaper.docx)

---

## 📋 Executive Summary & Clinical Context
Non-Small Cell Lung Cancer (NSCLC) represents approximately **85% of all lung cancer cases** globally and remains a primary cause of cancer-related mortality. While targeted therapies (specifically tyrosine kinase inhibitors targeting EGFR, ALK, and MET) have significantly improved survival rates, the inevitable emergence of **acquired drug resistance** due to complex, evolving mutation profiles remains a bottleneck in clinical oncology.

Traditional machine learning systems for predicting drug sensitivity/resistance operate as black boxes. They output a classification or probability but fail to provide the:
1. Somatic variant significance (pathogenicity classification).
2. Biological pathways disrupted.
3. Quantifiable feature-level contributions.
4. Clinically understandable explanations.

**XMARs (Explainable Multi-Agent Reasoning System)** solves these challenges by combining:
*   High-accuracy machine learning classifiers (Random Forest, Gradient Boosting, XGBoost, AdaBoost).
*   Rigorous feature attribution (SHAP explainability via TreeExplainer).
*   Deterministic biological pathway enrichment scoring (hypergeometric distribution).
*   Evidence-based pharmacogenomics rules (sensitizing, bypass resistance, and synthetic lethality).
*   A collaborative **4-Agent CrewAI & LangChain** sequential reasoning framework.

---

## ⚙️ Core Technical Architecture
The XMARs project is divided into three major functional layers, described in detail across the accompanying model files:

```
                  [Raw High-Throughput Genomic Data]
                                  │
                                  ▼
                    [preprocess_data.py (Cleaning)]
                                  │
                                  ▼
                 [advanced_analysis.py (Pathway Mappings)]
                                  │
                                  ▼
           [ml_pipeline.py (Pathogenicity Classification)]
                                  │
      ┌───────────────────────────┴───────────────────────────┐
      ▼                                                       ▼
[Variant Pathogenicity Models]                 [Real-Time multi-agent Dashboard]
 - Random Forest (96.97%)                       - Mutation Analyst (SHAP)
 - Gradient Boosting (98.09%)                   - Pathway Specialist (Activation)
 - AdaBoost (96.78%)                            - Drug Strategist (PGx Rules)
 - Soft Voting Ensemble (98.14%)                - Clinical Advisor (Gemini Synthesis)
```

### 1. Preprocessing and Bioinformatic Layer
*   **GDSC2 (Genomics of Drug Sensitivity in Cancer)** & **TCGA-LUAD/LUSC (The Cancer Genome Atlas Lung Adenocarcinoma/Squamous Cell Carcinoma)** datasets are ingestion foundations.
*   Handles continuous data (e.g. Variant Allele Frequency - VAF) and maps categorical mutation effects (nonsense, frameshift, missense, silent) using one-hot encoding.
*   Outputs structured pathway JSON databases and clean meta-sheets representing 1,984 cell lines.

### 2. Machine Learning Pipeline (Variant-Level Pathogenicity & Drug Resistance)
*   **Variant Pathogenicity Task**: Classifies somatic variants into Pathogenic (Driver) vs. Benign (Passenger) with up to **98.14% Ensemble accuracy**.
*   **Drug Resistance Task (Research Paper)**: Baseline models predict drug resistance probabilities across targeted TKIs with **85.1% Ensemble accuracy** and a **0.82 AUC**.

### 3. Multi-Agent Reasoning Subsystem
*   Orchestrated sequentially using **CrewAI & LangChain**, distributing tasks to four specialized, localized agents.
*   Decoupled from LLM hallucinations: all computational, mathematical, and database lookups are strictly hardcoded in scikit-learn models and local knowledge bases. The Gemini LLM (`gemini-2.5-flash`, `2.0-flash`, `1.5-flash`) acts exclusively as an interpreter to translate the analytical evidence chains into clinician-friendly markdown.

---

## 📂 Document Navigation
To review individual model details, biological logic, and agent workflows, navigate to the following documents:
*   👉 [02_random_forest.md](file:///c:/Users/rohit/Desktop/study/AI_ML/mini%20project-XMARs/mini_project/md/02_random_forest.md) — The baseline classifier details.
*   👉 [03_xgboost_gradient_boosting.md](file:///c:/Users/rohit/Desktop/study/AI_ML/mini%20project-XMARs/mini_project/md/03_xgboost_gradient_boosting.md) — The boosting framework details.
*   👉 [04_adaboost.md](file:///c:/Users/rohit/Desktop/study/AI_ML/mini%20project-XMARs/mini_project/md/04_adaboost.md) — The lightweight, fast classifier details.
*   👉 [05_ensemble_pipeline.md](file:///c:/Users/rohit/Desktop/study/AI_ML/mini%20project-XMARs/mini_project/md/05_ensemble_pipeline.md) — The soft-voting production ensemble classifier details.
*   👉 [06_drug_resistance_predictor.md](file:///c:/Users/rohit/Desktop/study/AI_ML/mini%20project-XMARs/mini_project/md/06_drug_resistance_predictor.md) — The evidence-based pharmacogenomic rule engine.
*   👉 [07_multi_agent_system.md](file:///c:/Users/rohit/Desktop/study/AI_ML/mini%20project-XMARs/mini_project/md/07_multi_agent_system.md) — The CrewAI clinical reasoning and dashboard orchestration.
