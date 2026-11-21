"""
MUTATION PATHWAY INTEGRATION HELPER
===================================
Utility functions for seamless integration between Mutation Agent and Pathway Agent.

Use this module to easily connect mutation predictions with pathway analysis.

Run:
    python integration_helper.py
    from integration_helper import analyze_patient_mutations
"""

import pandas as pd
import json
from pathlib import Path
from step4_mutation_agent import MutationAgent
from step5_pathway_agent import PathwayAgent
from typing import Dict, List, Tuple

# ─── Setup ──────────────────────────────────────────────────────────────────────
OUT = Path("output")
FIGS = Path("figures")
for d in [OUT, FIGS]:
    d.mkdir(parents=True, exist_ok=True)


class MutationPathwayAnalyzer:
    """
    Unified analyzer that combines Mutation Agent and Pathway Agent.
    
    Workflow:
        1. Initialize with mutations
        2. Get driver predictions
        3. Perform pathway analysis
        4. Export comprehensive results
    """
    
    def __init__(self, output_dir: str = None):
        self.output_dir = Path(output_dir) if output_dir else OUT
        self.mutation_agent = MutationAgent()
        self.pathway_agent = None
        self.results = {}
        
    def analyze_patient(
        self,
        patient_id: str,
        mutations: List[Dict]
    ) -> Dict:
        """
        Complete analysis pipeline for one patient.
        
        Args:
            patient_id: Patient identifier
            mutations: List of mutation dicts
                [{"gene": "TP53", "effect": "missense", ...}, ...]
        
        Returns:
            Complete analysis result dict
        """
        print(f"\n[MutationPathwayAnalyzer] Analyzing {patient_id}...")
        
        # Step 1: Get driver predictions
        print(f"  Step 1: Driver classification...")
        mutation_result = self.mutation_agent.predict(mutations, patient_id=patient_id)
        
        # Extract driver genes
        driver_genes = {
            m["gene"]: m["score"]
            for m in mutation_result.get("driver_mutations_detail", [])
        }
        
        print(f"    → Found {len(driver_genes)} driver genes")
        
        # Step 2: Pathway analysis
        print(f"  Step 2: Pathway enrichment...")
        pathway_agent = PathwayAgent()
        pathway_agent.load_mutation_output(driver_genes)
        pathway_agent.analyze_pathways()
        
        # Step 3: Extract results
        critical_pathways = pathway_agent.get_critical_pathways()
        
        result = {
            "patient_id": patient_id,
            "n_mutations": len(mutations),
            "n_drivers": len(driver_genes),
            "driver_genes": driver_genes,
            "n_critical_pathways": len(critical_pathways),
            "critical_pathways": {
                name: {
                    "n_drivers": data["n_drivers"],
                    "avg_score": data["avg_driver_score"],
                    "drivers": data["drivers"],
                    "description": data["description"],
                }
                for name, data in critical_pathways
            },
            "mutation_detail": mutation_result,
            "pathway_agent": pathway_agent,
        }
        
        self.results[patient_id] = result
        print(f"    → Found {len(critical_pathways)} critical pathways")
        
        return result
    
    def analyze_batch(self, patient_mutations_dict: Dict[str, List[Dict]]):
        """Analyze multiple patients."""
        for patient_id, mutations in patient_mutations_dict.items():
            self.analyze_patient(patient_id, mutations)
        return self
    
    def get_patient_summary(self, patient_id: str) -> Dict:
        """Get summary for single patient."""
        if patient_id not in self.results:
            return None
        
        result = self.results[patient_id]
        return {
            "patient_id": patient_id,
            "n_mutations": result["n_mutations"],
            "n_drivers": result["n_drivers"],
            "n_critical_pathways": result["n_critical_pathways"],
            "driver_genes": result["driver_genes"],
            "pathways": result["critical_pathways"],
        }
    
    def export_patient_report(self, patient_id: str, format_type: str = "csv") -> str:
        """
        Export single patient results.
        
        Args:
            patient_id: Patient ID
            format_type: "csv", "json", or "txt"
        """
        if patient_id not in self.results:
            return None
        
        result = self.results[patient_id]
        
        if format_type == "json":
            output_file = self.output_dir / f"{patient_id}_analysis.json"
            with open(output_file, "w") as f:
                json.dump(self.get_patient_summary(patient_id), f, indent=2)
            return str(output_file)
        
        elif format_type == "csv":
            # Create multi-row CSV with pathway details
            rows = []
            for pathway_name, pathway_data in result["critical_pathways"].items():
                rows.append({
                    "patient_id": patient_id,
                    "pathway": pathway_name,
                    "n_drivers": pathway_data["n_drivers"],
                    "avg_score": pathway_data["avg_score"],
                    "drivers": "|".join(
                        [f"{g}={v:.3f}" for g, v in sorted(pathway_data["drivers"].items())]
                    ),
                })
            
            df = pd.DataFrame(rows)
            output_file = self.output_dir / f"{patient_id}_pathways.csv"
            df.to_csv(output_file, index=False)
            return str(output_file)
        
        elif format_type == "txt":
            output_file = self.output_dir / f"{patient_id}_report.txt"
            with open(output_file, "w") as f:
                f.write(f"Patient: {patient_id}\n")
                f.write(f"Mutations analyzed: {result['n_mutations']}\n")
                f.write(f"Driver genes: {result['n_drivers']}\n")
                f.write(f"Critical pathways affected: {result['n_critical_pathways']}\n")
                f.write("\nDriver genes:\n")
                for gene, score in sorted(result["driver_genes"].items(), key=lambda x: x[1], reverse=True):
                    f.write(f"  {gene}: {score:.3f}\n")
                f.write("\nCritical pathways:\n")
                for pathway_name, data in sorted(result["critical_pathways"].items(),
                                                 key=lambda x: x[1]["avg_score"], reverse=True):
                    f.write(f"  {pathway_name}\n")
                    f.write(f"    Drivers: {list(data['drivers'].keys())}\n")
                    f.write(f"    Avg score: {data['avg_score']:.3f}\n")
            return str(output_file)
    
    def create_summary_table(self) -> pd.DataFrame:
        """Create summary table for all patients."""
        rows = []
        for patient_id, result in self.results.items():
            rows.append({
                "patient_id": patient_id,
                "n_mutations": result["n_mutations"],
                "n_drivers": result["n_drivers"],
                "driver_rate": result["n_drivers"] / result["n_mutations"] if result["n_mutations"] > 0 else 0,
                "n_critical_pathways": result["n_critical_pathways"],
                "top_pathway": max(
                    result["critical_pathways"].items(),
                    key=lambda x: x[1]["avg_score"],
                    default=("N/A", {})
                )[0] if result["critical_pathways"] else "N/A",
                "driver_genes": "|".join(sorted(result["driver_genes"].keys())),
            })
        
        df = pd.DataFrame(rows)
        output_file = self.output_dir / "patient_summary.csv"
        df.to_csv(output_file, index=False)
        print(f"✓ Saved summary table to {output_file}")
        return df
    
    def print_summary(self):
        """Print analysis summary."""
        print("\n" + "="*80)
        print("ANALYSIS SUMMARY")
        print("="*80)
        
        total_patients = len(self.results)
        total_mutations = sum(r["n_mutations"] for r in self.results.values())
        total_drivers = sum(r["n_drivers"] for r in self.results.values())
        
        print(f"\nPatients analyzed: {total_patients}")
        print(f"Total mutations: {total_mutations}")
        print(f"Total drivers: {total_drivers}")
        print(f"Average drivers per patient: {total_drivers/total_patients:.1f}")
        
        print(f"\nPer-patient breakdown:")
        for patient_id, result in self.results.items():
            print(f"  {patient_id}")
            print(f"    Mutations: {result['n_mutations']}")
            print(f"    Drivers: {result['n_drivers']}")
            print(f"    Critical pathways: {result['n_critical_pathways']}")
            if result['critical_pathways']:
                top = max(result['critical_pathways'].items(), 
                         key=lambda x: x[1]['avg_score'])
                print(f"    Top pathway: {top[0]} (score={top[1]['avg_score']:.3f})")


# ─── Convenience Functions ──────────────────────────────────────────────────────

def analyze_patient_mutations(
    patient_id: str,
    mutations: List[Dict],
    export_format: str = "all"
) -> Dict:
    """
    Quick one-liner analysis of patient mutations.
    
    Args:
        patient_id: Patient ID
        mutations: List of mutation dicts
        export_format: "all", "csv", "json", in addition to return value
    
    Returns:
        Analysis result dictionary
    
    Example:
        result = analyze_patient_mutations("P001", [
            {"gene": "TP53", "effect": "missense", ...}
        ])
    """
    analyzer = MutationPathwayAnalyzer()
    result = analyzer.analyze_patient(patient_id, mutations)
    
    if export_format in ["all", "csv"]:
        analyzer.export_patient_report(patient_id, "csv")
    if export_format in ["all", "json"]:
        analyzer.export_patient_report(patient_id, "json")
    
    return result


def batch_analyze(patient_mutations_dict: Dict[str, List[Dict]]) -> pd.DataFrame:
    """
    Analyze batch of patients and return summary.
    
    Args:
        patient_mutations_dict: {patient_id: [mutations], ...}
    
    Returns:
        Summary dataframe
    """
    analyzer = MutationPathwayAnalyzer()
    analyzer.analyze_batch(patient_mutations_dict)
    summary = analyzer.create_summary_table()
    analyzer.print_summary()
    return summary


# ─── Example Usage ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    
    print("="*80)
    print("MUTATION-PATHWAY INTEGRATION HELPER")
    print("="*80)
    
    # Example data
    example_patients = {
        "patient_001": [
            {"gene": "TP53", "effect": "Missense_Mutation", "protein_mutation": "R175H",
             "chromosome": 17, "position": 7674221, "vaf": 0.45, "coding": 1},
            {"gene": "EGFR", "effect": "Missense_Mutation", "protein_mutation": "L858R",
             "chromosome": 7, "position": 55086714, "vaf": 0.52, "coding": 1},
            {"gene": "KRAS", "effect": "Missense_Mutation", "protein_mutation": "G12C",
             "chromosome": 12, "position": 25398284, "vaf": 0.48, "coding": 1},
        ],
        "patient_002": [
            {"gene": "RB1", "effect": "Nonsense_Mutation", "protein_mutation": "Q14X",
             "chromosome": 13, "position": 48877881, "vaf": 0.47, "coding": 1},
            {"gene": "KRAS", "effect": "Missense_Mutation", "protein_mutation": "G12V",
             "chromosome": 12, "position": 25398284, "vaf": 0.51, "coding": 1},
        ],
    }
    
    # Run analysis
    summary = batch_analyze(example_patients)
    
    print("\n" + "-"*80)
    print("Summary table:")
    print("-"*80)
    print(summary.to_string(index=False))
    
    print("\n" + "="*80)
    print("Integration helper complete!")
    print("="*80)
