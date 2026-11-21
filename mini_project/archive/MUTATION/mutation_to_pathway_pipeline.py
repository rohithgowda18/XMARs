"""
MUTATION TO PATHWAY PIPELINE
=============================
End-to-end pipeline: Mutation Agent output -> Pathway Analysis

This script:
1. Loads trained Mutation Agent model
2. Takes sample patient mutations
3. Generates driver predictions
4. Maps drivers to pathways
5. Produces pathway enrichment report

Run:
    python mutation_to_pathway_pipeline.py
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from step4_mutation_agent import MutationAgent
from step5_pathway_agent import PathwayAgent

# ─── Setup ──────────────────────────────────────────────────────────────────────
OUT = Path("output")
OUT.mkdir(parents=True, exist_ok=True)

print("="*80)
print("MUTATION TO PATHWAY ANALYSIS PIPELINE")
print("="*80)

# ─── STEP 1: Load Mutation Agent ────────────────────────────────────────────────
print("\n[STEP 1] Loading Mutation Agent...")
try:
    mutation_agent = MutationAgent()
    print("✓ Mutation Agent loaded successfully")
except Exception as e:
    print(f"✗ Error loading Mutation Agent: {e}")
    exit(1)

# ─── STEP 2: Define Test Mutations (Real TCGA examples) ──────────────────────────
print("\n[STEP 2] Preparing test mutations...")

test_patient_mutations = {
    "patient_001": [
        {"gene": "TP53", "protein_mutation": "R175H", "effect": "missense",
         "chromosome": 17, "position": 7674221, "vaf": 0.45, "coding": 1},
        {"gene": "EGFR", "protein_mutation": "L858R", "effect": "missense",
         "chromosome": 7, "position": 55086714, "vaf": 0.52, "coding": 1},
        {"gene": "KRAS", "protein_mutation": "G12C", "effect": "missense",
         "chromosome": 12, "position": 25398284, "vaf": 0.48, "coding": 1},
        {"gene": "PTEN", "protein_mutation": "R130X", "effect": "nonsense",
         "chromosome": 10, "position": 89720686, "vaf": 0.50, "coding": 1},
    ],
    "patient_002": [
        {"gene": "RB1", "protein_mutation": "Q14X", "effect": "nonsense",
         "chromosome": 13, "position": 48877881, "vaf": 0.47, "coding": 1},
        {"gene": "KRAS", "protein_mutation": "G12V", "effect": "missense",
         "chromosome": 12, "position": 25398284, "vaf": 0.51, "coding": 1},
        {"gene": "NF1", "protein_mutation": "R1947X", "effect": "nonsense",
         "chromosome": 17, "position": 29421944, "vaf": 0.49, "coding": 1},
    ],
    "patient_003": [
        {"gene": "ARID1A", "protein_mutation": "L1234X", "effect": "nonsense",
         "chromosome": 1, "position": 26773142, "vaf": 0.46, "coding": 1},
        {"gene": "PIK3CA", "protein_mutation": "H1047R", "effect": "missense",
         "chromosome": 3, "position": 179234297, "vaf": 0.54, "coding": 1},
        {"gene": "SMAD4", "protein_mutation": "P130L", "effect": "missense",
         "chromosome": 18, "position": 48590905, "vaf": 0.50, "coding": 1},
    ],
}

print(f"✓ Prepared {len(test_patient_mutations)} patients with mutations")
for patient, mutations in test_patient_mutations.items():
    print(f"  - {patient}: {len(mutations)} mutations")

# ─── STEP 3: Get Driver Predictions from Mutation Agent ──────────────────────────
print("\n[STEP 3] Getting driver predictions from Mutation Agent...")

patient_driver_predictions = {}

for patient_id, mutations in test_patient_mutations.items():
    print(f"\n  Processing {patient_id}...")
    
    # Get predictions from mutation agent
    prediction_result = mutation_agent.predict(mutations, patient_id=patient_id)
    
    # Extract driver genes and scores
    driver_genes = {}
    for driver_mut in prediction_result.get("driver_mutations_detail", []):
        gene = driver_mut["gene"]
        score = driver_mut["score"]
        driver_genes[gene] = score
        print(f"    {gene:12s} {score:.3f} ({driver_mut.get('mutation', 'N/A')})")
    
    patient_driver_predictions[patient_id] = {
        "mutations_tested": len(mutations),
        "drivers_found": len(driver_genes),
        "driver_genes": driver_genes,
        "all_predictions": prediction_result,
    }
    
    print(f"  -> Identified {len(driver_genes)} driver genes")

# ─── STEP 4: Pathway Analysis ──────────────────────────────────────────────────────
print("\n[STEP 4] Performing pathway analysis...")

patient_pathway_results = {}

for patient_id, pred_data in patient_driver_predictions.items():
    print(f"\n  Analyzing pathways for {patient_id}...")
    
    # Initialize PathwayAgent
    pathway_agent = PathwayAgent()
    pathway_agent.load_mutation_output(pred_data["driver_genes"])
    pathway_agent.analyze_pathways()
    
    # Get critical pathways
    critical_pathways = pathway_agent.get_critical_pathways()
    
    patient_pathway_results[patient_id] = {
        "driver_genes": pred_data["driver_genes"],
        "critical_pathways": {
            name: {
                "n_drivers": data["n_drivers"],
                "avg_score": data["avg_driver_score"],
                "drivers": data["drivers"],
                "description": data["description"],
            }
            for name, data in critical_pathways
        },
        "pathway_agent": pathway_agent,
    }
    
    print(f"  -> Found {len(critical_pathways)} critical pathways with drivers")
    for pathway_name, data in critical_pathways[:3]:
        print(f"     • {pathway_name} ({data['n_drivers']} drivers, avg={data['avg_driver_score']:.3f})")

# ─── STEP 5: Generate Reports ──────────────────────────────────────────────────────
print("\n[STEP 5] Generating comprehensive reports...")

# ─── 5a: Per-patient pathway summary ───────────────────────────────────────────────
summary_rows = []

for patient_id, results in patient_pathway_results.items():
    for pathway_name, pathway_data in results["critical_pathways"].items():
        summary_rows.append({
            "patient_id": patient_id,
            "pathway": pathway_name,
            "n_driver_genes": pathway_data["n_drivers"],
            "avg_driver_score": pathway_data["avg_score"],
            "driver_genes": "|".join(
                [f"{g}={v:.3f}" for g, v in sorted(pathway_data["drivers"].items())]
            ),
            "description": pathway_data["description"],
        })

summary_df = pd.DataFrame(summary_rows)
summary_df = summary_df.sort_values(["patient_id", "avg_driver_score"], ascending=[True, False])
summary_df.to_csv(OUT / "patient_pathway_summary.csv", index=False)
print(f"✓ Saved patient pathway summary to {OUT / 'patient_pathway_summary.csv'}")

# ─── 5b: Aggregated pathway analysis across all patients ──────────────────────────
all_drivers = {}
all_pathways = {}

for patient_id, results in patient_pathway_results.items():
    all_drivers.update(results["driver_genes"])
    
    for pathway_name, data in results["critical_pathways"].items():
        if pathway_name not in all_pathways:
            all_pathways[pathway_name] = {
                "description": data["description"],
                "patients": [],
                "drivers": {},
            }
        all_pathways[pathway_name]["patients"].append(patient_id)
        all_pathways[pathway_name]["drivers"].update(data["drivers"])

# Create aggregated analysis
aggregated_pathway_agent = PathwayAgent()
aggregated_pathway_agent.load_mutation_output(all_drivers)
aggregated_pathway_agent.analyze_pathways()
aggregated_df = aggregated_pathway_agent.export_results(OUT / "pathway_analysis_aggregated.csv")

# Visualizations
aggregated_pathway_agent.visualize_pathway_heatmap(
    f"{FIGS / 'pathway_enrichment_all_patients.png'}"
)
aggregated_pathway_agent.visualize_pathway_network(
    f"{FIGS / 'pathway_network_all_patients.png'}"
)

print(f"✓ Saved aggregated pathway analysis")

# ─── 5c: Detailed JSON report ──────────────────────────────────────────────────────
detailed_report = {
    "analysis_metadata": {
        "n_patients": len(test_patient_mutations),
        "n_mutations_total": sum(len(m) for m in test_patient_mutations.values()),
        "n_unique_drivers": len(all_drivers),
    },
    "patients": {}
}

for patient_id, results in patient_pathway_results.items():
    detailed_report["patients"][patient_id] = {
        "driver_genes": {g: float(s) for g, s in results["driver_genes"].items()},
        "critical_pathways": {
            pathway_name: {
                "n_driver_genes": int(data["n_drivers"]),
                "avg_driver_score": float(data["avg_score"]),
                "drivers": {g: float(s) for g, s in data["drivers"].items()},
            }
            for pathway_name, data in results["critical_pathways"].items()
        },
    }

with open(OUT / "mutation_pathway_report.json", "w") as f:
    json.dump(detailed_report, f, indent=2)
print(f"✓ Saved detailed JSON report to {OUT / 'mutation_pathway_report.json'}")

# ─── 5d: Print final summary ───────────────────────────────────────────────────────
print("\n" + "="*80)
print("PIPELINE EXECUTION SUMMARY")
print("="*80)

print(f"\nPatient Statistics:")
for patient_id, results in patient_pathway_results.items():
    print(f"\n  {patient_id}:")
    print(f"    Driver genes: {len(results['driver_genes'])}")
    print(f"    Critical pathways affected: {len(results['critical_pathways'])}")
    
    if results['critical_pathways']:
        top_pathway = max(
            results['critical_pathways'].items(),
            key=lambda x: x[1]['avg_driver_score']
        )
        print(f"    Most affected pathway: {top_pathway[0]} (score={top_pathway[1]['avg_score']:.3f})")

print(f"\nAggregate Statistics:")
print(f"  Total driver genes identified: {len(all_drivers)}")
print(f"  Unique driver genes: {sorted(set(all_drivers.keys()))}")
print(f"  Pathways with drivers: {len(all_pathways)}")

print(f"\nOutput Files Generated:")
print(f"  ✓ {OUT / 'patient_pathway_summary.csv'}")
print(f"  ✓ {OUT / 'pathway_analysis_aggregated.csv'}")
print(f"  ✓ {OUT / 'mutation_pathway_report.json'}")
print(f"  ✓ {FIGS / 'pathway_enrichment_all_patients.png'}")
print(f"  ✓ {FIGS / 'pathway_network_all_patients.png'}")

print("\n" + "="*80)
print("PIPELINE COMPLETE!")
print("="*80)
