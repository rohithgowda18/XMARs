# MUTATION TO PATHWAY ANALYSIS GUIDE
## Complete Integration of Mutation Agent with Pathway Enrichment

---

## Overview

This guide explains how to use the **Pathway Analysis Agent** with outputs from the **Mutation Agent** to perform comprehensive pathway enrichment analysis on cancer genomic data.

### Architecture
```
Patient Mutations (MAF/CSV format)
        ↓
[Mutation Agent] → Driver/Passenger Classification
        ↓
Driver Genes + Probabilities
        ↓
[Pathway Agent] → Gene-to-Pathway Mapping
        ↓
Pathway Enrichment Analysis + Visualizations
```

---

## Components

### 1. **Mutation Agent** (`step4_mutation_agent.py`)
**Status**: Pre-trained model included  
**Purpose**: Classify each mutation as driver or passenger  
**Input**: Patient mutations (gene, position, effect, VAF, etc.)  
**Output**: Driver probability scores per gene

```python
from step4_mutation_agent import MutationAgent

agent = MutationAgent()
result = agent.predict(mutations_list, patient_id="P001")
# Returns: {
#   "driver_mutations": [{"gene": "TP53", "score": 0.85}, ...],
#   "driver_mutations_detail": [...],
#   ...
# }
```

### 2. **Pathway Agent** (`step5_pathway_agent.py`)
**Status**: New - Ready to use  
**Purpose**: Map driver genes to biological pathways  
**Input**: Driver genes with confidence scores  
**Output**: Pathway enrichment analysis, visualizations

```python
from step5_pathway_agent import PathwayAgent

agent = PathwayAgent()
agent.load_mutation_output({"TP53": 0.85, "EGFR": 0.92, ...})
agent.analyze_pathways()
df = agent.export_results()
agent.visualize_pathway_heatmap()
```

---

## Available Pathways (15 total)

| Pathway | Category | Impact | Key Genes |
|---------|----------|--------|-----------|
| TP53_Pathway | Tumor Suppression | CRITICAL | TP53, MDM2, CDKN1A, BAX |
| RB1_Pathway | Cell Cycle | CRITICAL | RB1, E2F1, CDK4, CDK6 |
| MAPK_ERK_Pathway | Growth Signaling | CRITICAL | KRAS, BRAF, MEK, ERK |
| PI3K_AKT_Pathway | Growth Signaling | CRITICAL | PIK3CA, PTEN, AKT, mTOR |
| RTK_Signaling | Growth Signaling | CRITICAL | EGFR, ERBB2, MET, ALK |
| DNA_Repair | Genomic Stability | CRITICAL | BRCA1, BRCA2, MLH1, ATM |
| TGF_Beta_Pathway | Differentiation | HIGH | SMAD2, SMAD4 |
| Wnt_Pathway | Differentiation | HIGH | APC, CTNNB1, GSK3B |
| Chromatin_Remodeling | Epigenetic | HIGH | ARID1A, BAP1, SETD2 |
| Apoptosis | Cell Death | HIGH | BAX, BCL2, FAS, CASP9 |
| And 5 more... | | | |

---

## Quick Start

### Option 1: Simple Pathway Analysis (No Mutation Agent needed)

```bash
cd MUTATION
python pathway_quickstart.py
```

**Input**: Example driver genes  
**Output**: 
- `output/pathway_analysis.csv` - Pathway enrichment table
- `output/pathway_analysis.json` - Detailed results
- `figures/pathway_enrichment_heatmap.png` - Visualization
- `figures/pathway_gene_network.png` - Driver networks by pathway

### Option 2: Full Pipeline (Mutation Agent → Pathways)

```bash
cd MUTATION
python mutation_to_pathway_pipeline.py
```

**Inputs**: 
- Pre-trained mutation model (provided)
- Test patient mutations

**Outputs**:
- `output/patient_pathway_summary.csv` - Per-patient pathway analysis
- `output/pathway_analysis_aggregated.csv` - Aggregated across patients
- `output/mutation_pathway_report.json` - Detailed JSON report
- Visualizations

---

## Usage Examples

### Example 1: Load Mutation Agent Output

```python
from step4_mutation_agent import MutationAgent
from step5_pathway_agent import PathwayAgent

# Step 1: Get driver predictions
mutation_agent = MutationAgent()
mutations = [
    {"gene": "TP53", "effect": "missense", "protein_mutation": "R175H",
     "chromosome": 17, "position": 7674221, "vaf": 0.45, "coding": 1},
    {"gene": "EGFR", "effect": "missense", "protein_mutation": "L858R",
     "chromosome": 7, "position": 55086714, "vaf": 0.52, "coding": 1},
]

result = mutation_agent.predict(mutations)

# Step 2: Extract driver genes
driver_genes = {
    m["gene"]: m["score"]
    for m in result["driver_mutations"]
}
# Output: {"TP53": 0.85, "EGFR": 0.92, ...}

print(f"Drivers: {driver_genes}")
```

### Example 2: Perform Pathway Analysis

```python
from step5_pathway_agent import PathwayAgent

# Load driver genes from mutation agent
driver_genes = {"TP53": 0.85, "EGFR": 0.92, "KRAS": 0.78}

# Analyze pathways
agent = PathwayAgent()
agent.load_mutation_output(driver_genes)
agent.analyze_pathways()

# Get critical pathways
critical = agent.get_critical_pathways()
for pathway_name, data in critical:
    print(f"{pathway_name}")
    print(f"  Drivers: {data['drivers']}")
    print(f"  Score: {data['avg_driver_score']:.3f}")
```

### Example 3: Export and Visualize Results

```python
# Export to CSV
df = agent.export_results("pathway_results.csv")

# Export to JSON
agent.export_json("pathway_results.json")

# Generate visualizations
agent.visualize_pathway_heatmap()
agent.visualize_pathway_network()

# Get top pathways
top = agent.get_top_pathways(top_n=10)
for pathway_name, data in top:
    print(f"{pathway_name}: {data['avg_driver_score']:.3f}")
```

### Example 4: Category-Based Analysis

```python
# Get pathways by category
categories = {}
for pathway_name, data in agent.pathway_results.items():
    cat = data['category']
    if cat not in categories:
        categories[cat] = []
    if data['n_drivers'] > 0:
        categories[cat].append((pathway_name, data))

# Print by category
for category, pathways in categories.items():
    print(f"\n{category.upper()} ({len(pathways)} pathways with drivers)")
    for pathway_name, data in pathways:
        print(f"  {pathway_name}: {data['drivers']}")
```

---

## Output Files

### CSV Outputs

#### `pathway_analysis.csv`
Pathway-level enrichment analysis:
- `pathway`: Pathway name
- `description`: Biological description
- `category`: Functional category
- `impact`: Clinical impact level
- `n_genes_pathway`: Total genes in pathway
- `n_driver_genes`: Number of driver mutations
- `driver_rate`: %coverage (drivers/total)
- `avg_driver_score`: Average driver probability
- `p_value`: Hypergeometric enrichment p-value

#### `patient_pathway_summary.csv`
Per-patient pathway results:
- `patient_id`: Patient identifier
- `pathway`: Pathway name
- `n_driver_genes`: Drivers affecting pathway
- `avg_driver_score`: Average score
- `driver_genes`: List of genes and scores

### JSON Outputs

#### `pathway_analysis.json`
Detailed results for downstream processing:
```json
{
  "analysis_type": "pathway_enrichment",
  "n_driver_genes": 10,
  "n_pathways_analyzed": 15,
  "pathways": {
    "TP53_Pathway": {
      "description": "...",
      "n_drivers": 1,
      "avg_driver_score": 0.85,
      "drivers": {"TP53": 0.85}
    }
  }
}
```

### Visualizations

#### `pathway_enrichment_heatmap.png`
Bar chart showing top pathways ranked by average driver score
- Colored by driver score intensity
- Labeled with number of drivers per pathway
- Sorted descending by score

#### `pathway_gene_network.png`
4-panel visualization of critical pathways:
- Each panel shows top driver genes in one critical pathway
- Bar heights indicate driver probability scores
- Useful for identifying path-specific driver combinations

---

## Interpretation Guide

### Critical vs High Impact Pathways

**CRITICAL pathways** = Essential for cancer biology:
- Loss-of-function: TP53, RB1, DNA_Repair
- Gain-of-function: MAPK, PI3K, RTK

**HIGH pathways** = Supporting roles and context-dependent

### Driver Rate Interpretation

- **100%** = All pathway genes affected
- **50%** = Half the pathway's genes mutated
- **10%** = Specific key nodes affected (often most significant)

### P-value Interpretation

- **p < 0.01**: Highly significant enrichment
- **p < 0.05**: Significant enrichment
- **p > 0.05**: Not statistically enriched

### Clinical Significance

**Growth Signaling + Cell Cycle Loss** = High proliferation  
**DNA Repair Loss** = Genomic instability + mutation burden  
**Immune Evasion** = Low immunogenicity  
**Multiple critical pathways** = High clinical burden

---

## Integration with Other Agents

### Downstream Usage

1. **Drug Agent** → Uses pathway info for treatment selection
   - RTK mutations → TKI therapy
   - PI3K mutations → PI3K/AKT inhibitors
   - DNA repair loss → Platinum chemotherapy

2. **Prognosis Agent** → Pathway patterns predict survival
   - Multiple critical pathways → poorer prognosis
   - Specific combination patterns → therapy response

3. **Tumor Immune Agent** → Immune evasion pathway status

---

## Customization

### Adding New Pathways

Edit the `PATHWAYS` dictionary in `step5_pathway_agent.py`:

```python
PATHWAYS = {
    "my_new_pathway": {
        "genes": ["GENE1", "GENE2", "GENE3"],
        "description": "Pathway description",
        "category": "growth_signaling",  # or other category
        "impact": "critical",  # or "high"
    },
    ...
}
```

### Changing Cancer Types

The current pathways are optimized for lung cancer (LUAD). For other cancers:
- Modify gene lists in each pathway
- Add/remove pathways as needed
- Adjust impact levels based on literature

---

## Performance Notes

- **Speed**: ~100ms per patient (with mutation agent)
- **Memory**: ~50MB (models + pathways loaded)
- **Scalability**: Can process 1000s of patients in batch mode

---

## Troubleshooting

### Issue: No critical pathways found

**Solution**: 
- Check that driver genes match pathway gene lists
- Verify mutation agent scores are > 0.5 (driver threshold)
- May indicate pathway-specific mutations are absent

### Issue: Low p-values for all pathways

**Solution**: 
- Normal if many drivers present
- Indicates widespread pathway disruption
- Consider filtering to top pathways only

### Issue: Missing visualizations

**Solution**:
```bash
pip install matplotlib seaborn
```

---

## References

- **KEGG**: Kyoto Encyclopedia of Genes and Genomes
- **Reactome**: Pathway database covering human biology
- **Hallmark pathways**: Gene Ontology biological processes
- **Cancer literature**: Driver gene compilations from:
  - OncoKB
  - CIViC Database
  - IntOGen

---

## Questions & Support

For issues or modifications:
1. Check `PIPELINE_DOCUMENTATION.md` for full system overview
2. Review `per_gene_analysis.py` for mutation-level details
3. See `step4_mutation_agent.py` for mutation classification details

---

**Last Updated**: March 2026  
**Version**: 1.0  
**Status**: Production Ready
