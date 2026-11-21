# 🧬 XMARs: An Explainable Multi-Agent Reasoning System for Real-Time Drug Resistance Prediction in Non-Small Cell Lung Cancer

**Status**: 🟢 **PRODUCTION READY**  
**Variant Pathogenicity Accuracy**: **98.14% (Ensemble)** ⭐  
**Drug Resistance Prediction Accuracy**: **85.1% (Ensemble, AUC: 0.82)** 💊  
**Institution**: Ramaiah Institute of Technology, Bengaluru, India  
**Version**: 1.0 (March 2026)

---

## 📋 Project Overview

**XMARs** (Extended Mutation Analysis and Resistance Scoring) is a clinical decision-support framework designed to address the "black box" nature of AI in oncology. Specifically targeting Non-Small Cell Lung Cancer (NSCLC) — which represents approximately 85% of all lung cancer cases — XMARs combines high-performance machine learning models, SHAP explainability, biological pathway activation scoring, evidence-based pharmacogenomic rules, and a multi-agent LLM reasoning pipeline built using CrewAI.

### Key Capabilities
1. **Bioinformatics Processing**: Cleans and normalizes genomic features, Variant Allele Frequencies (VAFs), and Copy Number Variations (CNVs) across 1,984 cell lines.
2. **Variant Pathogenicity Classification**: Trains ensemble models to distinguish between pathogenic (driver) and benign (passenger) somatic mutations with **98.14% accuracy**.
3. **Drug Resistance Prediction**: Models target-specific TKI (Tyrosine Kinase Inhibitor) resistance levels on GDSC2 and TCGA datasets.
4. **Multi-Agent Orchestration**: Deploys a sequential team of 4 CrewAI agents to perform mutation analysis, pathway mapping, drug matching, and generate patient-specific clinical reports.
5. **Interactive Dashboard**: Features a web application (Flask) showcasing patient prediction, SHAP visual feature attributions, drug rankings, clinical transcripts, and a genomics chatbot.

---

## ⚙️ Core Technical Architecture

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
 [Variant Pathogenicity Models]                 [Real-Time Multi-Agent Dashboard]
  - Random Forest (96.97%)                       - Mutation Analyst (SHAP)
  - Gradient Boosting (98.09%)                   - Pathway Specialist (Activation)
  - AdaBoost (96.78%)                            - Drug Strategist (PGx Rules)
  - Soft Voting Ensemble (98.14%)                - Clinical Advisor (Gemini Synthesis)
```

---

## 🤖 The 4-Agent CrewAI Reasoning Pipeline

Decoupled from LLM hallucinations, all mathematical, database, and machine learning computations are performed by deterministic scikit-learn models and local knowledge bases. The Gemini LLM serves exclusively as an intelligent interpreter to translate the analytical evidence chain into human-readable clinician reports.

1. **Mutation Analyst Agent**: Identifies major somatic mutations in the patient's profile and extracts feature-level importances using SHAP values.
2. **Pathway Specialist Agent**: Maps driver mutations to 8 key cancer pathways (e.g., EGFR signaling, PI3K-AKT-mTOR, DNA Repair) and computes pathway activation metrics.
3. **Drug Strategist Agent**: Evaluates the mutations against a PGx rule-engine (sensitizing mutations, bypass mechanisms, synthetic lethality) and ranks targeted therapies.
4. **Clinical Advisor Agent**: Synthesizes the quantitative results into a detailed clinician-friendly report with clear biological reasoning.

---

## 📊 Model Performance

### Variant Pathogenicity Classifier (Driver vs. Passenger)
*Implementation: [ml_pipeline.py](file:///c:/Users/rohit/Desktop/study/AI_ML/mini%20project-XMARs/mini_project/ml_pipeline.py)*

| Model | Accuracy | Precision | Recall | F1-Score | Status |
|-------|----------|-----------|--------|----------|--------|
| Random Forest | 96.97% | 97.15% | 96.97% | 0.9701 | Verified |
| Gradient Boosting | 98.09% | 98.10% | 98.09% | 0.9809 | Verified |
| AdaBoost | 96.78% | 96.94% | 96.78% | 0.9682 | Verified |
| **Ensemble (Soft Voting)** ⭐ | **98.14%** | **98.16%** | **98.14%** | **0.9814** | **Best Model** |

### NSCLC Drug Resistance Classifier
*Implementation: [resistance_predictor.py](file:///c:/Users/rohit/Desktop/study/AI_ML/mini%20project-XMARs/mini_project/drug_prediction/resistance_predictor.py)*

| Model | Accuracy | Precision | Recall | F1-Score | AUC |
|-------|----------|-----------|--------|----------|-----|
| Random Forest | 81.60% | 0.80 | 0.79 | 0.79 | 0.81 |
| XGBoost | 84.20% | 0.83 | 0.82 | 0.82 | 0.84 |
| **Ensemble Pipeline** | **85.10%** | **0.84** | **0.83** | **0.83** | **0.82** |

---

## 📂 Project Structure & Script Directory

```
mini_project/
│
├── 📊 BIOINFORMATICS & ML SCRIPTS
│   ├── preprocess_data.py          ← Cleans raw genomic files, handles missing values/outliers
│   ├── advanced_analysis.py        ← Maps mutated genes to 8 biological pathways
│   ├── train_models.py             ← Script to train classifiers individually
│   ├── ml_pipeline.py              ← Runs the complete ML classification pipeline
│   ├── model_fine_tuning.py        ← Hyperparameter tuning via GridSearchCV
│   ├── model_report.py             ← Evaluates model metrics and outputs reports
│   └── model_prediction.py         ← Example inference code for new mutations
│
├── 🤖 DRUG PREDICTION & AGENT BACKEND (drug_prediction/)
│   ├── app.py                      ← Main Flask web server running the dashboard
│   ├── agents.py                   ← Defines the CrewAI multi-agent orchestration
│   ├── shap_explainer.py           ← Generates SHAP explanation metrics for variants
│   ├── resistance_predictor.py     ← Contains rule-based pharmacogenomic matching
│   ├── drug_knowledge_base.py      ← Curated database of drug targets, pathways, and mutations
│   ├── ai_tools.py                 ← Integration tools for CrewAI/LangChain
│   ├── templates/                  ← Dashboard UI HTML layouts
│   └── static/                     ← Tailwind CSS & JS UI styles
│
├── 📁 DATA & SERIALIZED MODELS
│   ├── data/                       ← Processed data CSVs and gene references
│   └── models/                     ← Serialized classifiers (.pkl) and metric outputs
│
└── 📖 DOCUMENTATION
    ├── README.md                   ← (This file) Overview and setup instructions
    ├── QUICKSTART.md               ← Fast-track user guide
    ├── SYSTEM_USAGE_GUIDE.md       ← Full pipeline runtime explanation
    └── md/                         ← Sub-component technical markdown breakdowns
```

---

## 🚀 Getting Started

### 1. Environment Setup

XMARs is tested on Windows environments with Python 3.10+.

```bash
# Create a virtual environment
python -m venv .venv

# Activate the virtual environment
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# Install required dependencies
pip install -r requirements.txt
```

### 2. Configure API Credentials
Create a `.env` file in the root directory and add your credentials:
```env
GEMINI_API_KEY=your_gemini_api_key_here
GROQ_API_KEY=your_groq_api_key_here
```

### 3. Run the ML Pipeline (Pathogenicity Classification)
To preprocess data and train the classifiers:
```bash
# Preprocess genomic features and map pathways
python preprocess_data.py
python advanced_analysis.py

# Train the ML models and generate the ensemble classifier
python ml_pipeline.py
```

### 4. Run the Multi-Agent Web Dashboard
To launch the interactive Flask web application:
```bash
python drug_prediction/app.py
```
Open [http://localhost:5000](http://localhost:5000) in your web browser. 

---

## 📚 Complete Documentation Index

For exhaustive breakdowns of specific system areas, refer to the following documents in [`docs/guides/`](docs/guides/):

| Topic | Document Path |
|-------|---------------|
| **System Overview & Multi-Agent Architecture** | [MASTER_GUIDE_PART1_ARCHITECTURE.md](docs/guides/MASTER_GUIDE_PART1_ARCHITECTURE.md) |
| **Machine Learning, SHAP & Genomics** | [MASTER_GUIDE_PART2_ML_AND_SHAP.md](docs/guides/MASTER_GUIDE_PART2_ML_AND_SHAP.md) |
| **Engineering, Backend & Production Scale** | [MASTER_GUIDE_PART3_ENGINEERING_AND_SCALE.md](docs/guides/MASTER_GUIDE_PART3_ENGINEERING_AND_SCALE.md) |
| **Technical Interview Defense & Questions** | [MASTER_GUIDE_PART4_INTERVIEW_DEFENSE.md](docs/guides/MASTER_GUIDE_PART4_INTERVIEW_DEFENSE.md) |
| **All-in-One Comprehensive Guide** | [COMPLETE_PROJECT_GUIDE.md](docs/guides/COMPLETE_PROJECT_GUIDE.md) |
| **Quickstart Guide** | [QUICKSTART.md](docs/guides/QUICKSTART.md) |
| **System Usage Guide** | [SYSTEM_USAGE_GUIDE.md](docs/guides/SYSTEM_USAGE_GUIDE.md) |
| **Gemini Tool-Calling Upgrade** | [TOOL_CALLING_UPGRADE.md](docs/guides/TOOL_CALLING_UPGRADE.md) |

---

## 🎓 Citation

If you reference this work in your research, please cite:
```text
Dr. S. Seema, Rohith Gowda K, Venkatachala V, Vijay Patil, and Vijay Veerabhadra Patil,
“XMARs: An Explainable Multi-Agent Reasoning System for Real-Time Drug Resistance Prediction in Non-Small Cell Lung Cancer,”
Department of Computer Science and Engineering, Ramaiah Institute of Technology, 2026.
```
