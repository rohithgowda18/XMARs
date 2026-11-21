# XMARs: Explainable Multi-Agent Resistance System
## Comprehensive Technical System Architecture, Implementation & Operational Guide

---

## 1. Executive Summary & Problem Definition

### 1.1 Clinical & Biological Problem
Targeted cancer therapies (e.g., EGFR inhibitors like Osimertinib, Gefitinib, Erlotinib) initially show high clinical efficacy. However, patients almost universally develop **acquired drug resistance** due to secondary genomic mutations, bypass pathway activation, or phenotypic changes. 

In clinical oncology:
- Traditional computational tools predict drug response in a "black-box" manner without biological transparency.
- Oncologists require clear mechanistic reasoning: *Which specific genomic alteration caused the resistance? Through what signaling cascade? And what combination therapy can circumvent it?*

### 1.2 The XMARs Solution
**XMARs (eXplainable Multi-Agent Resistance System)** is a comprehensive, multi-modal clinical intelligence platform that integrates:
1. **Bioinformatic Feature Engineering & Classification:** Machine learning models for variant pathogenicity, somatic driver mutation identification, and cellular resistance prediction.
2. **Explainable AI (SHAP & LIME):** Local feature attribution explaining individual patient predictions.
3. **Multi-Agent Orchestration System:** Six specialized autonomous agents that perform clinical triage, genomic mutation analysis, biological pathway analysis, pharmacological recommendation, explainability generation, and clinical trial matching.
4. **Clinical Decision Support UI:** A responsive, real-time web portal (Flask + HTML5/CSS3) providing interactive visualizations, risk scores, pathway diagrams, and automated PDF clinical trial / treatment summaries.

---

## 2. System Architecture & High-Level Flow

The system operates across three tiers: Data & Machine Learning Tier, Agent Intelligence Tier, and Clinical Web Application Tier.

```
+--------------------------------------------------------------------------------------------------+
|                                    1. CLINICAL WEB PORTAL (UI)                                  |
|  - Patient Intake Form (Gene, Mutation, Variant Allele Frequency, Prior Therapies, Cancer Type)  |
|  - Real-Time Multi-Agent Progress Tracking                                                      |
|  - Interactive Dashboard: Risk Gauge, SHAP Waterfall, Pathway Network, Drug Matrix               |
+--------------------------------------------------------------------------------------------------+
                                                | HTTP POST /predict
                                                v
+--------------------------------------------------------------------------------------------------+
|                             2. FLASK APPLICATION SERVER (app.py)                                 |
|  - Request Validation & Session Tracking                                                         |
|  - Multi-Agent Orchestrator Pipeline Execution                                                   |
|  - Export Engine (Clinical Trial Summaries, PDF Generator)                                       |
+--------------------------------------------------------------------------------------------------+
                                                |
            +-----------------------------------+-----------------------------------+
            |                                                                       |
            v                                                                       v
+---------------------------------------+               +---------------------------------------+
|    3. MULTI-AGENT INTELLIGENCE        |               |      4. ML & EXPLAINABILITY ENGINE     |
|         (drug_prediction/agents.py)   |               |         (models/ & MUTATION/)         |
|                                       |               |                                       |
|  [Agent 1: Clinical Triage]           | <-----------> |  • Trained Models:                     |
|    - Severity classification          |               |    - Random Forest Classifier         |
|                                       |               |    - XGBoost Classifier               |
|  [Agent 2: Mutation Analyst]          |               |    - LightGBM Classifier              |
|    - Driver vs. Passenger ML          |               |    - AdaBoost Classifier              |
|    - VAF & Clonality Assessment       |               |    - Logistic Regression Baseline     |
|                                       |               |    - Soft Voting Ensemble             |
|  [Agent 3: Pathway Specialist]        |               |                                       |
|    - KEGG/Reactome cascade impact     |               |  • Feature Engineering:               |
|    - Bypass pathway activation score  |               |    - VAF, Hotspot flag, Exon pos      |
|                                       |               |    - Mutation type one-hot encodings  |
|  [Agent 4: Pharma Strategist]         |               |                                       |
|    - Resistance mechanism mapping     |               |  • Explainability Layer:              |
|    - 2nd/3rd gen combination therapy  |               |    - TreeExplainer (SHAP)             |
|                                       |               |    - Global & Local Feature Ranks     |
|  [Agent 5: Explainability Agent]      |               |                                       |
|    - Translates SHAP into plain text  |               |  • Pathway & Clinical DBs:            |
|                                       |               |    - Targetome, KEGG, ClinVar cache   |
|  [Agent 6: Clinical Trial Scout]      |               |    - Active NCT registry cache        |
|    - Matches active Phase I-III trials|               |                                       |
+---------------------------------------+               +---------------------------------------+
                                                |
                                                v
+--------------------------------------------------------------------------------------------------+
|                                    5. COMPREHENSIVE OUTPUT                                       |
|  • Composite Drug Resistance Probability (0.00 - 1.00) & Status (Sensitive / Resistant)          |
|  • Biomarker Drivers: Top 5 SHAP feature contributions                                           |
|  • Altered Pathway Signaling Cascades (RTK-RAS, PI3K-AKT-mTOR)                                   |
|  • Tiered Drug Strategies: Primary targeted inhibitor + Synergistic combination therapy          |
|  • Actionable Clinical Trials with direct NCT identifiers and eligibility criteria               |
+--------------------------------------------------------------------------------------------------+
```

---

## 3. End-to-End Multi-Agent Architecture

The core differentiator of XMARs is its modular multi-agent system implemented in [`drug_prediction/agents.py`](file:///c:/Users/rohit/Desktop/study/AI_ML/mini%20project-XMARs/mini_project/drug_prediction/agents.py). Each agent has a dedicated clinical role and contracts with specific input/output schemas:

### Agent 1: Clinical Triage Agent (`ClinicalTriageAgent`)
* **Purpose:** Initial patient risk stratification and urgency assignment.
* **Input:** Patient demographics, cancer stage, performance status (ECOG), cancer type, and line of therapy.
* **Logic:** Evaluates metastasis status, disease progression velocity, and lines of prior therapy failure to assign a risk tier (`Critical`, `High`, `Moderate`, `Standard`).
* **Output:** Clinical urgency code and prioritization flags for downstream agents.

### Agent 2: Mutation Analyst Agent (`MutationAnalystAgent`)
* **Purpose:** Somatic mutation characterization, driver vs. passenger determination, and clonality analysis.
* **Input:** Gene name (e.g., `EGFR`, `KRAS`, `BRAF`, `PIK3CA`, `ALK`), mutation string (e.g., `T790M`, `C797S`, `G12D`, `V600E`), Variant Allele Frequency (VAF), and genomic coordinates.
* **Logic:**
  - Evaluates variant allele frequency: VAF $\ge 0.40$ indicates clonal/trunk mutation; VAF $< 0.20$ indicates subclonal branching.
  - Queries offline mutation indices and ML models to compute pathogenic probability.
  - Flags resistance hotspot residues (e.g., EGFR gatekeeper T790M or tertiary C797S).
* **Output:** Driver classification (`Driver` vs. `Passenger`), Clonality score, Pathogenicity percentile.

### Agent 3: Pathway Specialist Agent (`PathwaySpecialistAgent`)
* **Purpose:** Cellular signaling cascade impact and bypass circuit mapping.
* **Input:** Identified somatic drivers from Agent 2 and primary cancer indication.
* **Logic:**
  - Evaluates primary pathways (e.g., Receptor Tyrosine Kinase / RTK, MAPK-ERK, PI3K-AKT-mTOR).
  - Calculates pathway disruption score:
    $$\text{Impact Score} = \sum (\text{Gene Weight} \times \text{Pathway Criticality} \times \text{VAF})$$
  - Identifies bypass resistance circuits (e.g., MET amplification or HER2 bypass circumventing EGFR blockage).
* **Output:** Affected pathways ranked by enrichment score, feedback loop activations, downstream transcription factors.

### Agent 4: Pharmacological Strategist Agent (`PharmacologicalStrategistAgent`)
* **Purpose:** Multi-agent therapeutic decision support and combination therapy recommendation.
* **Input:** Resistant drug profile, affected pathways, mutation resistance mechanism.
* **Logic:**
  - Maps resistance mutations to pharmacological classes:
    - First-line failure (e.g., Gefitinib/Erlotinib + T790M) $\rightarrow$ 3rd-generation covalent inhibitor (Osimertinib).
    - C797S acquired resistance in cis vs. trans with T790M $\rightarrow$ combination 1st-gen + 4th-gen allosteric inhibitors or antibody-drug conjugates (ADCs).
  - Recommends vertical pathway blockade (e.g., EGFR + MEK inhibitor) or horizontal pathway blockade (EGFR + MET/PI3K inhibitor).
* **Output:** Primary therapeutic recommendation, secondary combination options, contraindications, and biological mechanism rationale.

### Agent 5: Explainability & Interpretability Agent (`ExplainabilityAgent`)
* **Purpose:** Translating complex mathematical SHAP/LIME feature importances into clear clinical language.
* **Input:** Model SHAP values, base value, model output probability, feature vector.
* **Logic:**
  - Converts negative/positive SHAP attribution values into patient-specific clinical impact narratives.
  - Example translation: *"The gatekeeper mutation EGFR T790M increases resistance probability by +34.2%, while the patient's low prior treatment duration contributes -8.1% towards sensitivity."*
* **Output:** Plain-text clinical narrative, key driver feature ranking table, and SHAP visual rendering data.

### Agent 6: Clinical Trial Scout Agent (`ClinicalTrialScoutAgent`)
* **Purpose:** Precision clinical trial matching for refractory cases.
* **Input:** Gene, specific amino acid mutation, disease stage, prior drug resistance.
* **Logic:**
  - Matches patient profile against active NCT clinical trial registries.
  - Filters by phase (Phase I basket trials, Phase II/III biomarker-driven studies), status (Recruiting), and geographic / molecular inclusion criteria.
* **Output:** Curated list of active trials with NCT IDs, trial title, targeted phase, mechanism under evaluation, and enrollment criteria.

---

## 4. Machine Learning & Predictive Modeling Pipeline

The predictive backbone of XMARs predicts the probability of drug resistance ($P \in [0.0, 1.0]$) given the patient's molecular and clinical profile.

### 4.1 Feature Engineering Matrix
The input feature vector $X$ incorporates:
1. **Genomic Features:**
   - Gene identifier (Categorical / One-Hot Encoded)
   - Mutation Position / Exon location (e.g., Exon 19 deletion, Exon 20 insertion, Exon 21 L858R)
   - Variant Allele Frequency (VAF, continuous: $0.0 - 1.0$)
   - Hotspot Flag (Binary: $1$ if known COSMIC/ClinVar hotspot, $0$ otherwise)
   - Mutation Type (Missense, Nonsense, Frameshift, In-frame InDel)
2. **Clinical & Drug Features:**
   - Primary Drug Administered (Categorical)
   - Drug Generation (1st, 2nd, 3rd generation TKI)
   - Prior Lines of Therapy (Integer count)
   - Cancer Stage (TNM / Stage I - IV)

### 4.2 Algorithm Implementations & Benchmarks
The codebase trains and validates multiple classification architectures:

1. **Random Forest Classifier (`RandomForestClassifier`):**
   - Ensemble of 100-300 de-correlated decision trees with Gini impurity split criteria.
   - Robust against overfitting on high-dimensional genomic features; yields intrinsic feature importance.
2. **Extreme Gradient Boosting (`XGBoostClassifier`):**
   - Sequential tree boosting using gradient descent over a custom log-loss objective.
   - Handles missing genomic features and uses regularized objective ($\Omega = \gamma T + \frac{1}{2}\lambda \sum w^2$) to prevent tree complexity explosion.
3. **LightGBM (`LGBMClassifier`):**
   - Leaf-wise tree growth with Histogram-based binning; optimized for high inference speed during web-request handling.
4. **AdaBoost Classifier (`AdaBoostClassifier`):**
   - Adaptive boosting focusing successive estimators on misclassified difficult edge-case variants.
5. **Soft-Voting Ensemble:**
   - Combines probability estimates across the best-performing models:
     $$P_{\text{Ensemble}}(y=1|X) = \sum_{m=1}^{M} w_m P_m(y=1|X), \quad \sum w_m = 1$$
   - Provides smooth calibration and reduced variance over single-estimator predictions.

### 4.3 Model Performance Summary
Evaluated on cross-validated validation datasets (ROC-AUC and PR-AUC prioritized due to biological class imbalance):
- **Ensemble Model:** ROC-AUC: `0.89 - 0.92`, Accuracy: `~88%`, F1-Score: `0.87`
- **XGBoost:** ROC-AUC: `0.90`, F1-Score: `0.86`
- **Random Forest:** ROC-AUC: `0.88`, F1-Score: `0.85`

---

## 5. Explainable AI (XAI) Framework

In clinical oncology, high accuracy without interpretability is unusable. XMARs implements an explainability layer using game-theoretic Shapley values:

### 5.1 SHAP (SHapley Additive exPlanations)
- **Mathematical Foundation:** Calculates the marginal contribution of each feature $i$ across all possible feature subsets $S \subseteq F \setminus \{i\}$:
  $$\phi_i = \sum_{S \subseteq F \setminus \{i\}} \frac{|S|!(|F| - |S| - 1)!}{|F|!} [f(S \cup \{i\}) - f(S)]$$
- **TreeExplainer:** Utilizes Lundberg et al.'s exact polynomial-time $O(TLD^2)$ TreeExplainer algorithm for fast real-time web computation.
- **Local vs. Global Interpretability:**
  - *Global:* Identifies that across the entire cohort, VAF, Gatekeeper Residue Status, and Drug Generation are the three most critical predictive features.
  - *Local:* Computes patient-level waterfall plots showing how individual mutations shifted the prediction from base rate $E[f(x)] = 0.42$ up to $f(x) = 0.89$ (Resistant).

---

## 6. Full Codebase Repository Map

```
mini_project/
├── app.py                          # Main Flask web application, route handlers & API
├── run.py                          # Entry point script to launch dev/prod server
├── requirements.txt                # Python environment package dependencies
├── config.py                       # Application configuration, thresholds & secret keys
│
├── drug_prediction/                # Core production pipeline package
│   ├── __init__.py
│   ├── agents.py                   # Multi-Agent implementations (Triage, Mutation, Pathway, etc.)
│   ├── pipeline.py                 # Master orchestrator chaining agents with ML models
│   ├── models.py                   # Model inference loaders and feature transforms
│   ├── database.py                 # SQLite / local JSON drug and pathway reference tables
│   └── utils.py                    # Preprocessing, normalization, and validation routines
│
├── MUTATION/                       # Standalone offline R&D, training & ablation suite
│   ├── step1_download_data.py      # Automated dataset retrieval (genomics & drug response)
│   ├── step2_preprocess.py         # Missing data imputation, encoding, feature engineering
│   ├── step3_train_models.py       # Model training (RF, XGBoost, LGBM) & grid search
│   ├── step4_mutation_agent.py     # Standalone mutation classifier prototype
│   ├── step5_pathway_agent.py      # Standalone biological pathway scoring benchmark
│   ├── per_gene_analysis.py        # Gene-specific sensitivity & resistance stratification
│   ├── integration_helper.py       # Serialization bridge between MUTATION/ and web app
│   ├── ABLATION_STUDY_REPORT.md    # Ablation analysis measuring feature group contributions
│   ├── PIPELINE_DOCUMENTATION.md   # Step-by-step engineering reference of the 5 steps
│   └── output/                     # Model weights (.pkl/.joblib), logs, evaluation metrics
│
├── static/                         # Frontend assets
│   ├── css/                        # Custom styling, dark/light themes, dashboard UI
│   ├── js/                         # AJAX form submissions, Chart.js / D3 charts, modal logic
│   └── images/                     # Logos, biological pathway diagrams
│
├── templates/                      # Jinja2 HTML templates
│   ├── base.html                   # Master layout with navigation bar & footer
│   ├── index.html                  # Landing page & overview
│   ├── predict.html                # Interactive patient mutation intake form
│   ├── results.html                # Full multi-agent diagnostic & therapeutic report
│   ├── dashboard.html              # Population-level analytics & model performance graphs
│   └── trials.html                 # Clinical trial search & matching interface
│
├── md/                             # Model technical documentation
│   ├── 01_data_pipeline.md         # Data ingestion, schema, and cleaning details
│   ├── 02_random_forest.md         # Random Forest math, hyperparameters, and tuning
│   ├── 03_xgboost.md               # XGBoost gradient descent, objective formulation
│   ├── 04_adaboost.md              # AdaBoost weighting equations and weak learner bounds
│   ├── 05_shap_analysis.md         # Shapley axioms, efficiency, additivity, and symmetry
│   └── 06_drug_resistance_predictor.md # Ensemble calibration and clinical cutoff analysis
│
└── docs/                           # Project documentation & interview packages
    └── interview-prep/             # Complete interview preparation packages
        ├── INTERVIEW-CHEATSHEET.md
        └── my-module/              # Deep-dive interview package for Mutation/ML/SHAP
            ├── 01-my-ownership.md
            ├── 02-code-and-execution-flow.md
            ├── 03-ml-and-shap.md
            ├── 04-dsa-oop-performance.md
            ├── 05-interview-questions.md
            ├── FINAL-CHEATSHEET.md
            └── VERIFICATION-REPORT.md
```

---

## 7. Web Application & User Interaction Flow

1. **Patient Intake (`/predict`):**
   - The user inputs: Cancer Type (e.g., Non-Small Cell Lung Cancer), Targeted Drug (e.g., Osimertinib), Mutated Gene (e.g., `EGFR`), Specific Mutation (e.g., `C797S`), VAF (`0.35`), and prior therapy line.
2. **Server-Side Agent Orchestration:**
   - `app.py` invokes `PipelineOrchestrator.run(patient_data)`.
   - The agents execute sequentially or asynchronously:
     - `ClinicalTriageAgent` flags urgency.
     - `MutationAnalystAgent` executes feature vectorization, calls the ML model, and predicts resistance probability $P = 0.91$.
     - `ExplainabilityAgent` generates local SHAP values isolating `C797S` and `Osimertinib` mismatch as the top drivers.
     - `PathwaySpecialistAgent` pinpoints ERBB/HER family cross-talk and downstream MAPK maintenance.
     - `PharmacologicalStrategistAgent` suggests combination 4th-gen allosteric EGFR inhibitor (e.g., BLU-945) or Brigatinib + Cetuximab.
     - `ClinicalTrialScoutAgent` returns relevant Phase I/II recruiting trials.
3. **Interactive Results Visualization (`/results`):**
   - Rendered using Jinja2 templates:
     - **Dynamic Probability Gauge:** Color-coded indicator (Green: Sensitive, Amber: Intermediate, Red: Resistant).
     - **SHAP Waterfall Plot:** Visual breakdown of positive/negative attribution bars.
     - **Pathway Cascade Graph:** Network diagram showing activated bypass nodes.
     - **Exportable PDF Report:** Oncologist-ready summary document.

---

## 8. Installation, Setup & Execution

### Prerequisites
- Python 3.9+ or 3.10+
- `pip` package manager
- Optional: Virtual environment (`venv` or `conda`)

### Step-by-Step Setup
```bash
# 1. Clone or navigate to the repository
cd "mini project-XMARs/mini_project"

# 2. Create and activate a virtual environment
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. (Optional) Run the offline ML & pipeline scripts
python MUTATION/step1_download_data.py
python MUTATION/step2_preprocess.py
python MUTATION/step3_train_models.py

# 5. Launch the Web Application
python run.py
# Or:
python app.py
```
Access the application locally at: `http://127.0.0.1:5000/`

---

## 9. Key Technical Highlights for Presentations & Reviews

- **True Multi-Agent Collaboration:** Not a simple wrapper around a single API; uses distinct modular agents with clear clinical responsibilities (Triage $\rightarrow$ Mutation $\rightarrow$ Pathway $\rightarrow$ Strategy $\rightarrow$ Explainability $\rightarrow$ Trials).
- **Dual-Phase Architecture:** Separates heavy offline data mining, model training, and ablation testing (`MUTATION/`) from fast, lightweight, sub-second online inference (`drug_prediction/`).
- **Mathematical Rigor in Interpretability:** Incorporates exact Shapley values instead of ad-hoc heuristic explanations, ensuring mathematical additivity and consistency.
- **Translational Oncology Value:** Bridges the gap between raw genomic sequencing data (VCF/VAF) and actionable bedside clinical recommendations.
