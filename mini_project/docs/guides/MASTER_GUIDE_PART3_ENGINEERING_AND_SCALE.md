# Part 3: Engineering, Backend, Storage & Scaling
## Data Structures, In-Memory Storage, API Architecture, Security & Production Scale

---

## 1. Data Structures & Algorithm Complexities

The runtime inference engine in XMARs is designed for sub-second, deterministic response times. The system minimizes overhead by using specialized data structures:

| Operation | Data Structure Used | Location | Time Complexity | Space Complexity | Engineering Rationale |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Drug-by-Target Lookup** | `defaultdict(list)` | `drug_knowledge_base.py` | $\mathcal{O}(1)$ average | $\mathcal{O}(D)$ where $D=621$ | Immediate retrieval of all inhibitors targeting a specific gene without database joins. |
| **Gene-by-Pathway Mapping** | `dict[str, set]` | `drug_knowledge_base.py` | $\mathcal{O}(1)$ average | $\mathcal{O}(G \cdot P)$ | Set intersection ($\mathcal{O}(\min(|A|, |B|))$) to find overlapping genes across disrupted signaling pathways. |
| **Variant Deduplication** | Python `set` + length sort | `mutation_extractor.py` | $\mathcal{O}(K \log K)$ | $\mathcal{O}(K)$ candidates | Merges partial and complete HGVS variant strings (e.g., `p.R331f` into `p.R331fs`). |
| **Feature Vector Construction**| `np.ndarray` (1D, float64) | `agents.py` | $\mathcal{O}(F)$ ($F=14$) | $\mathcal{O}(F)$ | Low-overhead memory-contiguous vector for direct Scikit-Learn `.predict_proba()` calls. |
| **Pathway Disruption Score** | Set traversal & counter | `agents.py` | $\mathcal{O}(M)$ mutations | $\mathcal{O}(1)$ | Single linear pass computing compromised pathway fractions. |

---

## 2. In-Memory Knowledge Base vs. Traditional RDBMS

In XMARs, an **In-Memory Analytical Architecture** was selected over a traditional Relational Database Management System (RDBMS) like MySQL or PostgreSQL:

### Architectural Justifications:
1. **Deterministic Read-Heavy Pattern**:
   - The reference knowledge base (621 oncology drugs, their protein targets, and 8 canonical biological pathways) represents curated scientific knowledge.
   - It is static during clinical inference sessions (zero concurrent write transactions required).
2. **Elimination of Multi-Table Join Overhead**:
   - Correlating `Patient Mutations` $\to$ `Driver Genes` $\to$ `Canonical Pathways` $\to$ `Target Compounds` requires a 4-table SQL JOIN.
   - In Python memory, dual-indexed hash tables resolve this in **$< 1\text{ millisecond}$** with zero network latency or connection-pool starvation.
3. **Reproducibility & Zero External Infrastructure**:
   - The processed files (`data/processed/03_compounds_cleaned.csv`, `data/processed/pathway_reference.json`) are version-controlled with git alongside the code.
   - Deploying the app requires no external database provisioning (Docker or AWS RDS setup).

---

## 3. Backend Architecture & REST API Specification

The web application backend is built on **Flask 3.0+** running in `drug_prediction/app.py`.

### 3.1 Primary API Endpoints

#### 1. `GET /`
- **Purpose**: Serves the primary clinical dashboard, interactive mutation intake form, and PDF drag-and-drop zone.
- **Template Rendered**: `templates/index.html`

#### 2. `POST /predict-ai`
- **Purpose**: Primary multi-agent execution pipeline.
- **Request Headers**: `Content-Type: application/json`
- **Request Body Payload**:
  ```json
  {
    "mutations": [
      {"gene": "EGFR", "vaf": 0.45},
      {"gene": "TP53", "vaf": 0.82}
    ]
  }
  ```
- **Response**: Returns a comprehensive JSON package containing:
  - `driver_analysis`: Driver vs. passenger labels, confidence scores, VAFs.
  - `pathway_analysis`: Compromised pathways with percentage scores and cross-talk warnings.
  - `drug_recommendations`: Ranked drugs grouped by `sensitive`, `resistant`, and `intermediate`.
  - `shap_explanations`: Top 5 feature contributions and consensus rankings across models.
  - `clinical_narrative`: Synthesized oncological report (from Gemini or deterministic fallback).

#### 3. `POST /parse-pdf`
- **Purpose**: Receives an uploaded clinical molecular PDF report and extracts sanitized mutations.
- **Request**: `multipart/form-data` with file payload `file`.
- **Response**:
  ```json
  {
    "success": true,
    "mutations": [
      {"gene": "EGFR", "protein_change": "p.L858R", "vaf": 0.38},
      {"gene": "BRAF", "protein_change": "p.V600E", "vaf": 0.12}
    ],
    "extraction_layer": "layer_1_regex"
  }
  ```

---

## 4. Security, Compliance & Error Handling

### 4.1 Healthcare Data Privacy & HIPAA Considerations
1. **Zero Patient Health Information (PHI) Persistence**:
   - The application does NOT store patient names, medical record numbers (MRNs), or demographic data in databases or server disk logs.
   - Uploaded PDF files are processed in-memory via file streams and immediately garbage collected.
2. **API Key Security**:
   - Secrets (`GEMINI_API_KEY`, `GROQ_API_KEY`, `SECRET_KEY`) are managed exclusively via environment variables using `python-dotenv`.
   - Keys are never committed to version control (`.gitignore` enforces exclusions).

### 4.2 Robust Exception Handling & Resilience Patterns
1. **Exponential Backoff on LLM Calls**:
   - Implements a retry loop with exponential jitter for remote LLM calls to handle rate limits (**HTTP 429**).
   - If 3 successive attempts fail, the system falls back to the deterministic local markdown generator.
2. **Strict Input Sanitization**:
   - Gene names are validated against an authorized cancer gene whitelist (`GENE_WHITELIST`).
   - VAF values are bounds-checked to the range $[0.0, 1.0]$.
   - File uploads are validated by MIME type (enforcing `application/pdf`) and maximum payload sizes ($16\text{MB}$).

---

## 5. Production Scalability & High-Concurrency Architecture

### Current Setup vs. Enterprise Hospital Deployment

```mermaid
flowchart TD
    Clients["Hospital Clients / UI"] --> ALB["AWS Application Load Balancer"]
    ALB --> Gunicorn["Gunicorn WSGI Workers (4 per CPU Core)"]
    Gunicorn --> FastAPI["Flask / FastAPI Services"]
    FastAPI --> RedisCache{Redis Cache Hit?<br/>Hash(Genomic Profile)}
    RedisCache -- Cache Hit --> ReturnCache["Return Cached SHAP & PGx (< 10ms)"]
    RedisCache -- Cache Miss --> CeleryQueue["Celery Task Queue (RabbitMQ)"]
    CeleryQueue --> MLWorkers["Celery Worker Pool (CPU/GPU)<br/>Runs SHAP & Ensemble Inference"]
    MLWorkers --> WriteCache["Save Result to Redis"]
    WriteCache --> ReturnClient["Stream to Client via SSE / WebSockets"]
```

When explaining scalability in technical interviews:
1. **WSGI / ASGI Transition**:
   - Replace Flask development server (`app.run(debug=True)`) with **Gunicorn** or **Uvicorn** utilizing `gevent` or asynchronous worker processes behind an **Nginx** reverse proxy.
2. **Genomic Profile Memoization (Redis)**:
   - Recurrent hotspot mutations (e.g., `EGFR L858R` or `KRAS G12C`) frequently recur across oncology cohorts.
   - Results are keyed by a hash of the mutation profile: `hash(EGFR_0.45_TP53_0.80)`.
   - Cache hits serve results in **$< 10\text{ms}$**, eliminating redundant SHAP evaluations.
3. **Asynchronous Background Processing**:
   - Decouple PDF OCR and heavy SHAP calculations from the HTTP request-response cycle using **Celery** with **RabbitMQ** or **AWS SQS**.
   - Front-end receives immediate tracking IDs and listens for results via **Server-Sent Events (SSE)**.
