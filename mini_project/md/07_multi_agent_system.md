# 🤖 Collaborative Multi-Agent System & Real-Time Dashboard

## 📌 Document Metadata
*   **System Component**: Multi-Agent Orchestration & Web Dashboard (`agents.py`, `app.py`, `shap_explainer.py`)
*   **Role**: Coordinates four specialized computational agents sequentially to produce interpretable clinical reports and interactive user interfaces.
*   **Code Implementations**:
    *   [agents.py](file:///c:/Users/rohit/Desktop/study/AI_ML/mini%20project-XMARs/mini_project/drug_prediction/agents.py)
    *   [app.py](file:///c:/Users/rohit/Desktop/study/AI_ML/mini%20project-XMARs/mini_project/drug_prediction/app.py)
    *   [shap_explainer.py](file:///c:/Users/rohit/Desktop/study/AI_ML/mini%20project-XMARs/mini_project/drug_prediction/shap_explainer.py)
*   **Reference Document**: [xmarreasearchpaper.docx](file:///c:/Users/rohit/Desktop/study/AI_ML/mini%20project-XMARs/mini_project/xmarreasearchpaper.docx)

---

## 🔬 System Overview & Orchestration Philosophy

Traditional clinical prediction systems are monolithic, black-box pipelines. XMARs disrupts this paradigm by implementing a **decoupled, multi-agent collaborative reasoning architecture** built on top of **CrewAI & LangChain**.

### The Core Philosophy: Decoupled AI Reasoning
A primary risk in clinical LLM applications is **hallucination**—a generative model producing fabricated facts, statistics, or treatment parameters. XMARs completely eliminates this risk by segregating computation from interpretation:
1.  **Strict Computational Core (Deterministic)**: All mathematical modeling, machine learning predictions (Random Forest, Gradient Boosting, AdaBoost), SHAP feature attributions, pathway activation calculations, and pharmacogenomics rules are hardcoded in **pure Python and scikit-learn**.
2.  **Generative Interpretation Layer (LLM)**: Large Language Models (Gemini APIs like `gemini-2.5-flash`, `2.0-flash`, `1.5-flash`) are used **exclusively as translators**. The LLM never computes scores; it merely synthesizes structured JSON evidence outputs from the upstream computational agents into highly readable, professional clinical reports.
3.  **Fail-Safe Local Fallbacks**: If the Gemini API experiences network errors, quota exhaustion, or rate limits, the system seamlessly falls back to a **local rule-based clinical compiler** to prevent any downtime in clinical environments.

---

## ⚙️ The 4-Agent Sequential Workflow

The system coordinates four independent agents in a strict sequential pipeline, where each agent acts as a specialized specialist, consuming the output of the prior stage:

```
[Patient Mutations (Gene + VAF)]
              │
              ▼
   ┌────────────────────────────────────────┐
   │ 1. MUTATION ANALYST AGENT              │
   │  - Loads ML Models & SHAP Explainers   │
   │  - Classifies Driver vs Passenger      │
   │  - Calculates Shapley feature values   │
   └──────────────────┬─────────────────────┘
                      │ [Mutation Classifications + SHAP Data]
                      ▼
   ┌────────────────────────────────────────┐
   │ 2. PATHWAY SPECIALIST AGENT            │
   │  - Maps Genes to Signaling Pathways    │
   │  - Computes Pathway Activation Scores  │
   │  - Detects Gene-Pathway Cross-talk     │
   └──────────────────┬─────────────────────┘
                      │ [Pathway Activation & Disruption States]
                      ▼
   ┌────────────────────────────────────────┐
   │ 3. DRUG STRATEGIST AGENT               │
   │  - Evaluates Rule Engine PGx Rules     │
   │  - Ranks 10 TKIs by Sensitivity        │
   │  - Establishes detailed Evidence Chains│
   └──────────────────┬─────────────────────┘
                      │ [Ranked Drug Recommendations + Evidence]
                      ▼
   ┌────────────────────────────────────────┐
   │ 4. CLINICAL ADVISOR AGENT              │
   │  - Generates JSON structured synthesis │
   │  - Calls Gemini for clinician report   │
   │  - Handles offline fallback formatting │
   └──────────────────┬─────────────────────┘
                      │
                      ▼
[Personalized Oncology Decision Support Report]
```

### 1. Mutation Analyst Agent (`MutationAnalystAgent`)
*   **Role**: Genomic mutation classification and feature importance analysis.
*   **Methodology**:
    *   Ingests the patient’s mutation profile (e.g. `EGFR` with a Variant Allele Frequency of `0.45`).
    *   Loads `mutation_features.csv` to reconstruct the patient's feature vector, scale continuous attributes via `scaler_pipeline.pkl`, and scale VAF.
    *   Executes the `SHAPExplainer` across all three trained models (Random Forest, Gradient Boosting, AdaBoost) using Shapley values.
    *   Classifies variants based on clear biological threshold logic:
        *   **Likely Driver**: $\text{VAF} \ge 0.3$ and average SHAP feature importance $> 0.01$.
        *   **Possible Driver**: $\text{VAF} \ge 0.1$ and moderate average SHAP feature importance.
        *   **Likely Passenger**: $\text{VAF} < 0.1$.
*   **Output**: Unified per-gene analysis records containing driver/passenger classification, confidence levels, average SHAP values, and frontend-ready waterfall chart datasets.

### 2. Pathway Specialist Agent (`PathwaySpecialistAgent`)
*   **Role**: Cancer pathway mapping and disruption scoring.
*   **Methodology**:
    *   Receives the classified mutations and average SHAP importances from the Mutation Analyst.
    *   Queries `drug_knowledge_base.py` to map these genes onto their specific signaling pathways (e.g., MAPK, PI3K-AKT, JAK-STAT, Cell Cycle).
    *   Calculates a **Pathway Activation Score** ($\mathcal{A}$) representing the proportion and significance of disrupted genes:
        $$\mathcal{A} = \min\left(1.0, \frac{\text{Mutated Genes}}{\text{Total Genes}} \times \left(0.5 + 0.5 \times \text{Avg. VAF}\right) + \text{SHAP Boost} + 0.1 \times \text{Driver Count}\right)$$
        *   Where $\text{SHAP Boost} = \min(0.3, \text{Avg. SHAP} \times 50)$ acts as a model-driven weight boost.
    *   Flags **compromised drug targets** (wild-type genes in a pathway that cannot be targeted because their co-genes are mutated).
    *   Detects **cross-talk interactions** (single genes residing in multiple pathways, magnifying signaling cascade collapse).
*   **Output**: Sorted list of disrupted pathways, their activation percentages, and cross-talk impact summaries.

### 3. Drug Strategist Agent (`DrugStrategistAgent`)
*   **Role**: Drug resistance scoring and evidence-based ranking.
*   **Methodology**:
    *   Consumes the pathway and mutation logs.
    *   Calls the rule-based `ResistancePredictor` to compute clinical drug resistance scores ($\mathcal{R}$) and sensitivity percentages ($\mathcal{S}$) for all therapies in the system.
    *   Builds individual **evidence chains** for each drug by matching its targets and biological pathways to mutated genes and disrupted pathways:
        *   *SHAP Evidence*: Confirms a drug targets a gene labeled as a driver (Strong strength).
        *   *Pathway Evidence*: Confirms a drug acts on a highly activated/disrupted signaling cascade (Score $> 0.5$ = Strong, else Moderate).
        *   *Resistance/Bypass Evidence*: Captures markers for bypass resistance (e.g., KRAS mutations bypassing EGFR TKIs).
    *   Ranks drugs in ascending order of predicted resistance (most sensitive first).
*   **Output**: Ranked list of therapies, categorized into *Likely Sensitive*, *Potentially Sensitive*, *Uncertain*, or *Resistant*, alongside explicit evidence links.

### 4. Clinical Advisor Agent (`ClinicalAdvisorAgent`)
*   **Role**: Clinical synthesis and human-readable explanation.
*   **Methodology**:
    *   Compiles all upstream metrics into a structured JSON payload (`_build_structured_report`).
    *   Constructs a clinical prompt specifying:
        1.  No hallucination or fabrication.
        2.  Strict reliance on actual drug names, VAF values, and scores.
        3.  Target sections: *Patient Overview*, *Key Findings*, *Top Drug Recommendations* (with evidence), and *Treatment Considerations*.
    *   Iteratively calls the Google GenAI Client, auto-detecting the most compatible and available model:
        1.  `gemini-2.5-flash`
        2.  `gemini-2.0-flash`
        3.  `gemini-1.5-flash`
    *   If API keys are missing or all models rate-limit (429), it switches to `_generate_fallback_report`, rendering a structured text report containing all identical statistics.
*   **Output**: Final patient oncology dossier in clean, clinician-friendly markdown.

---

## 🔬 Core Explanatory Mechanics

### SHAP Explanations (`shap_explainer.py`)
SHAP (SHapley Additive exPlanations) values represent the average marginal contribution of a feature to the prediction score across all possible feature subsets. XMARs implements SHAP explanation via multiple backends depending on model capability:
*   **TreeExplainer**: Used for exact and rapid calculations on Random Forest and Gradient Boosting models, bypassing slow sampling times.
*   **AdaBoost Explainer Strategy**: Since AdaBoost lacks a native Tree SHAP formulation in older backends, XMARs tries `TreeExplainer` on base tree estimators, and falls back to a scaled `KernelExplainer` on a curated 50-sample subset of background data.
*   **Consensus Feature Analysis**: Computes consensus feature importance by averaging the mean absolute SHAP value across all three models to isolate features that are robustly important regardless of model architecture.

### Pathway Activation Mapping
By mapping mutated genes to pathways and weighting them by variant allele frequencies (VAFs) and SHAP values, XMARs mimics cellular-level signaling. This maps genetic data directly to physical receptor tyrosine kinase (RTK) behavior:
*   **MAPK Pathway**: Involves `EGFR`, `KRAS`, `BRAF`. High VAF drivers here predict strong resistance to first-generation EGFR inhibitors.
*   **PI3K-Akt Pathway**: Involves `PIK3CA`, `PTEN`, `AKT1`. Mutations bypass EGFR signaling entirely, driving cellular survival.

---

## 💻 Web Application & Dashboard Architecture (`app.py`)

XMARs provides a responsive, web-based dashboard allowing real-time clinical interaction. The application is written in Flask and integrates interactive frontends.

### 1. Flask API Backend Endpoints (`app.py`)
The Flask server manages data requests, model inference, and multi-agent coordination through structured JSON endpoints:
*   `GET /`: Serves the primary clinical dashboard UI.
*   `GET /api/genes`: Returns all available genes in the knowledge base, their pathway associations, and targeted drug counts.
*   `GET /api/pathways`: Returns detailed pathway schemas, descriptions, and clinical relevance.
*   `POST /predict`: Standard rule-based prediction engine providing fast scoring of drug sensitivity.
*   `POST /predict-ai`: Initiates the **real multi-agent reasoning pipeline**. Employs automatic backoff and retry logic (up to 3 attempts with exponential wait) to handle Gemini API rate limits (429 errors).
*   `POST /api/shap`: Computes and returns SHAP global values and waterfall visualization datasets for a specified mutation profile.
*   `POST /parse-pdf`: Processes uploaded clinical pathology reports (such as FoundationOne genomic reports) via a stabilized extraction pipeline:
    $$\text{Uploaded PDF} \rightarrow \text{Regex Parse} \rightarrow \text{Groq LLM} \rightarrow \text{Gemini Text} \rightarrow \text{Gemini Vision (OCR fallback)}$$
    Extracts high-fidelity gene symbols and VAFs.
*   `POST /chat`: Integrates an interactive genomics chatbot helper. Injects the active patient analysis context directly into the Gemini system instructions so clinicians can ask follow-up questions (e.g., *"Why did the system recommend Osimertinib over Gefitinib?"*).

### 2. Gradio Web Interface (Research Paper Integration)
Section 2.6 and 3.6 of the research paper document a Gradio-based interface integrated within the multi-agent system.
*   **Input Section**: Clinicians upload patient genomic mutation profiles in PDF or enter mutations manually.
*   **Real-time Progress Tracker**: Displays visual logs showing the live thinking process of the Mutation Analyst, Pathway Specialist, Drug Strategist, and Clinical Advisor.
*   **Visual Analytics Cards**:
    *   *SHAP Feature Importance Plot*: Visualizes the contribution of coding status, variant allele frequency, and gene identity.
    *   *Pathway Activation Map*: Displays bar charts of disrupted signaling pathways colored by activation severity.
    *   *Therapeutic Recommendation Rankings*: Renders comparative bar charts ranking suitable therapies (such as Alectinib, Osimertinib, and Crizotinib).
    *   *Synthesized Clinical dossier*: Presents the final, formatted markdown report ready for exporting or clinical peer review.

---

## 🔗 Document Navigation
Explore other segments of the XMARs machine learning and rule-based pipeline:
*   👉 [01_project_overview.md](file:///c:/Users/rohit/Desktop/study/AI_ML/mini%20project-XMARs/mini_project/md/01_project_overview.md) — Main system architecture and datasets.
*   👉 [02_random_forest.md](file:///c:/Users/rohit/Desktop/study/AI_ML/mini%20project-XMARs/mini_project/md/02_random_forest.md) — Pathogenicity classification details.
*   👉 [03_xgboost_gradient_boosting.md](file:///c:/Users/rohit/Desktop/study/AI_ML/mini%20project-XMARs/mini_project/md/03_xgboost_gradient_boosting.md) — Gradient boosting model configurations.
*   👉 [04_adaboost.md](file:///c:/Users/rohit/Desktop/study/AI_ML/mini%20project-XMARs/mini_project/md/04_adaboost.md) — Lightweight AdaBoost hyperparameters.
*   👉 [05_ensemble_pipeline.md](file:///c:/Users/rohit/Desktop/study/AI_ML/mini%20project-XMARs/mini_project/md/05_ensemble_pipeline.md) — Production Soft Voting Ensemble.
*   👉 [06_drug_resistance_predictor.md](file:///c:/Users/rohit/Desktop/study/AI_ML/mini%20project-XMARs/mini_project/md/06_drug_resistance_predictor.md) — Evidentiary pharmacogenomics rules.
