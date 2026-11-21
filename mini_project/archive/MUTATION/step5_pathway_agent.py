"""
STEP 5 — PATHWAY ANALYSIS AGENT
=================================
Takes driver mutations from Mutation Agent and maps them to canonical pathways.

Purpose:
  - Map driver genes to biological pathways (KEGG, Reactome, hallmark pathways)
  - Identify affected pathway modules in cancer
  - Stratify pathways by severity (# drivers, average driver score)
  - Generate pathway enrichment analysis
  - Create pathway-level insights for precision medicine

Input:
  Mutation Agent output: {gene: "TP53", score: 0.85}, ...

Output:
  1. Pathway enrichment table (pathway, n_genes, n_drivers, avg_score, p_value)
  2. Gene-pathway mapping visualization
  3. Pathway significance heatmap
  4. Driver gene network by pathway

Downstream agents:
  Drug Agent -> uses pathway info for resistance prediction
  Prognosis Agent -> pathway mutations predict survival

Run:
    python step5_pathway_agent.py
    from step5_pathway_agent import PathwayAgent
"""

import pandas as pd
import numpy as np
import json
import warnings
from pathlib import Path
from scipy.stats import hypergeom, fisher_exact
from collections import defaultdict
from step4_mutation_agent import MutationAgent
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

warnings.filterwarnings("ignore")

# ─── Output directories ────────────────────────────────────────────────────────
OUT = Path("output")
FIGS = Path("figures")
for d in [OUT, FIGS]:
    d.mkdir(parents=True, exist_ok=True)


# ─── CANCER PATHWAY DEFINITIONS ─────────────────────────────────────────────────
# Based on KEGG, Reactome, and Hallmark pathway databases
PATHWAYS = {
    "TP53_Pathway": {
        "genes": ["TP53", "MDM2", "CDKN1A", "BAX", "PUMA", "ATM", "ATR", "CHK2"],
        "description": "p53 tumor suppressor - cell cycle checkpoint & apoptosis",
        "category": "tumor_suppression",
        "impact": "critical"
    },
    "RB1_Pathway": {
        "genes": ["RB1", "E2F1", "CDK4", "CDK6", "CYCLIN_D", "CDKN2A"],
        "description": "Retinoblastoma pathway - G1/S checkpoint control",
        "category": "cell_cycle",
        "impact": "critical"
    },
    "MAPK_ERK_Pathway": {
        "genes": ["KRAS", "NRAS", "HRAS", "BRAF", "MEK1", "MEK2", "ERK1", "ERK2", "RAF1", "ROS1"],
        "description": "MAPK/ERK cascade - proliferation & survival",
        "category": "growth_signaling",
        "impact": "critical"
    },
    "PI3K_AKT_Pathway": {
        "genes": ["PIK3CA", "PIK3R1", "PTEN", "AKT1", "AKT2", "mTOR", "TSC1", "TSC2"],
        "description": "PI3K/AKT/mTOR - survival & metabolism",
        "category": "growth_signaling",
        "impact": "critical"
    },
    "RTK_Signaling": {
        "genes": ["EGFR", "ERBB2", "ERBB3", "ERBB4", "MET", "ALK", "RET", "FGFR1", "FGFR2", "FGFR3"],
        "description": "Receptor Tyrosine Kinases - growth signal reception",
        "category": "growth_signaling",
        "impact": "critical"
    },
    "TGF_Beta_Pathway": {
        "genes": ["SMAD2", "SMAD3", "SMAD4", "SMAD6", "SMAD7", "TGF_BETA_R1", "TGF_BETA_R2"],
        "description": "TGF-beta signaling - EMT & differentiation",
        "category": "differentiation",
        "impact": "high"
    },
    "Wnt_Pathway": {
        "genes": ["APC", "CTNNB1", "GSK3B", "LEF1", "TCF", "AXIN"],
        "description": "Wnt/beta-catenin signaling - stem-cell-like properties",
        "category": "differentiation",
        "impact": "high"
    },
    "DNA_Repair": {
        "genes": ["BRCA1", "BRCA2", "MLH1", "MSH2", "MSH6", "PMS2", "POLD1", "CHEK2", "ATM", "ATR"],
        "description": "DNA damage response & repair pathways",
        "category": "genomic_stability",
        "impact": "critical"
    },
    "p16_CDKN2A": {
        "genes": ["CDKN2A", "RB1", "CDK4", "CDK6", "CYCLIN_D"],
        "description": "p16/CDK4/6/RB pathway - cell cycle arrest",
        "category": "cell_cycle",
        "impact": "high"
    },
    "NF1_RAS_Pathway": {
        "genes": ["NF1", "KRAS", "NRAS", "HRAS", "BRAF"],
        "description": "NF1 RAS regulation - neurofibromatosis suppression",
        "category": "growth_signaling",
        "impact": "high"
    },
    "TP53_CDKN1A_Pathway": {
        "genes": ["TP53", "CDKN1A", "GADD45", "MDM2"],
        "description": "p53-p21 cell cycle arrest and apoptosis",
        "category": "cell_cycle",
        "impact": "high"
    },
    "Angiogenesis": {
        "genes": ["VEGF", "VEGFR1", "VEGFR2", "HIF1A", "KDR", "PGF"],
        "description": "Vascular endothelial growth factor - angiogenesis",
        "category": "tumor_microenvironment",
        "impact": "high"
    },
    "Immune_Checkpoint": {
        "genes": ["PD1", "PDL1", "PDL2", "CTLA4", "IDO"],
        "description": "Immune checkpoint molecules - immune evasion",
        "category": "immune_evasion",
        "impact": "high"
    },
    "Chromatin_Remodeling": {
        "genes": ["ARID1A", "BAP1", "PBRM1", "CHD1", "SETD2", "CREBBP"],
        "description": "Epigenetic chromatin modifiers - tumor suppressors",
        "category": "epigenetic",
        "impact": "high"
    },
    "Apoptosis": {
        "genes": ["BAX", "BAK", "BCL2", "BCL2L1", "MCL1", "FAS", "TNF", "CASP9"],
        "description": "Programmed cell death - apoptosis pathways",
        "category": "cell_death",
        "impact": "high"
    }
}


class PathwayAgent:
    """
    Pathway Analysis Agent — maps driver mutations to biological pathways
    and performs pathway enrichment analysis.
    """

    def __init__(self):
        self.mutation_agent = MutationAgent()
        self.pathways = PATHWAYS
        self.driver_genes = {}
        self.pathway_results = {}

    def load_mutation_output(self, driver_genes_dict):
        """
        Load driver genes and scores from Mutation Agent.
        
        Args:
            driver_genes_dict: {"EGFR": 0.92, "TP53": 0.85, ...}
        """
        self.driver_genes = driver_genes_dict
        print(f"[PathwayAgent] Loaded {len(driver_genes_dict)} driver genes")
        return self

    def normalize_gene_name(self, gene):
        """Normalize gene name for pathway matching."""
        gene = str(gene).strip().upper()
        # Handle special cases
        mapping = {
            "CDKN2A": "CDKN2A",
            "CDKN1A": "CDKN1A",
            "MEK1": "MEK1",
            "MEK2": "MEK2",
            "ERK1": "ERK1",
            "ERK2": "ERK2",
        }
        return mapping.get(gene, gene)

    def analyze_pathways(self):
        """Perform pathway enrichment analysis."""
        print("\n[PathwayAgent] Analyzing pathways...")
        
        for pathway_name, pathway_data in self.pathways.items():
            genes = [self.normalize_gene_name(g) for g in pathway_data["genes"]]
            
            # Find driver genes in this pathway
            drivers = {}
            for gene in genes:
                if gene in self.driver_genes:
                    drivers[gene] = self.driver_genes[gene]
            
            # Calculate pathway metrics
            n_genes = len(genes)
            n_drivers = len(drivers)
            avg_score = np.mean(list(drivers.values())) if drivers else 0.0
            max_score = max(drivers.values()) if drivers else 0.0
            
            # Calculate p-value using hypergeometric distribution
            # (probability of observing k drivers by chance)
            total_drivers = len(self.driver_genes)
            total_genes = 18000  # Approximate human genome
            
            if n_drivers > 0:
                pval = self._hypergeom_pvalue(
                    n_drivers, n_genes, total_drivers, total_genes
                )
            else:
                pval = 1.0
            
            self.pathway_results[pathway_name] = {
                "description": pathway_data["description"],
                "category": pathway_data["category"],
                "impact": pathway_data["impact"],
                "n_genes": n_genes,
                "n_drivers": n_drivers,
                "driver_rate": n_drivers / n_genes if n_genes > 0 else 0,
                "avg_driver_score": avg_score,
                "max_driver_score": max_score,
                "p_value": pval,
                "drivers": drivers,
                "all_genes": genes,
            }
        
        print(f"[PathwayAgent] Analyzed {len(self.pathway_results)} pathways")
        return self

    def _hypergeom_pvalue(self, k, n, K, N):
        """
        Calculate hypergeometric p-value.
        k = drivers in pathway, n = genes in pathway
        K = total drivers, N = total genes
        """
        try:
            return hypergeom.sf(k - 1, N, K, n)
        except:
            return 1.0

    def get_top_pathways(self, metric="avg_driver_score", top_n=10):
        """Get top pathways by a specific metric."""
        sorted_pathways = sorted(
            self.pathway_results.items(),
            key=lambda x: x[1][metric],
            reverse=True
        )
        return sorted_pathways[:top_n]

    def get_critical_pathways(self):
        """Get only critical impact pathways with drivers."""
        critical = {
            name: data
            for name, data in self.pathway_results.items()
            if data["impact"] == "critical" and data["n_drivers"] > 0
        }
        return sorted(
            critical.items(),
            key=lambda x: x[1]["avg_driver_score"],
            reverse=True
        )

    def export_results(self, output_csv=None):
        """Export pathway results to CSV."""
        if output_csv is None:
            output_csv = OUT / "pathway_analysis.csv"
        
        rows = []
        for pathway_name, data in self.pathway_results.items():
            rows.append({
                "pathway": pathway_name,
                "description": data["description"],
                "category": data["category"],
                "impact": data["impact"],
                "n_genes_pathway": data["n_genes"],
                "n_driver_genes": data["n_drivers"],
                "driver_rate": data["driver_rate"],
                "avg_driver_score": data["avg_driver_score"],
                "max_driver_score": data["max_driver_score"],
                "p_value": data["p_value"],
                "log10_pval": -np.log10(data["p_value"]) if data["p_value"] > 0 else 0,
                "driver_genes": "|".join(
                    [f"{g}={v:.3f}" for g, v in sorted(data["drivers"].items())]
                )
            })
        
        df = pd.DataFrame(rows)
        df = df.sort_values("avg_driver_score", ascending=False)
        df.to_csv(output_csv, index=False)
        print(f"[PathwayAgent] Saved pathway analysis to {output_csv}")
        return df

    def export_json(self, output_json=None):
        """Export detailed results to JSON."""
        if output_json is None:
            output_json = OUT / "pathway_analysis.json"
        
        # Convert for JSON serialization
        output_data = {
            "analysis_type": "pathway_enrichment",
            "n_driver_genes": len(self.driver_genes),
            "n_pathways_analyzed": len(self.pathway_results),
            "pathways": {}
        }
        
        for pathway_name, data in self.pathway_results.items():
            output_data["pathways"][pathway_name] = {
                "description": data["description"],
                "category": data["category"],
                "impact": data["impact"],
                "n_genes": data["n_genes"],
                "n_drivers": data["n_drivers"],
                "driver_rate": float(data["driver_rate"]),
                "avg_driver_score": float(data["avg_driver_score"]),
                "p_value": float(data["p_value"]),
                "drivers": {g: float(s) for g, s in data["drivers"].items()}
            }
        
        with open(output_json, "w") as f:
            json.dump(output_data, f, indent=2)
        
        print(f"[PathwayAgent] Saved detailed results to {output_json}")
        return output_data

    def visualize_pathway_heatmap(self, output_fig=None):
        """Create pathway enrichment heatmap."""
        if output_fig is None:
            output_fig = FIGS / "pathway_enrichment_heatmap.png"
        
        df = self._get_results_dataframe()
        if df.empty:
            return None
        
        # Create heatmap data
        df_heat = df[["pathway", "n_drivers", "avg_driver_score", "driver_rate"]].copy()
        df_heat = df_heat.sort_values("avg_driver_score", ascending=False).head(15)
        
        fig, ax = plt.subplots(figsize=(12, 8))
        
        # Normalize scores for visualization
        norm_scores = df_heat["avg_driver_score"].values / df_heat["avg_driver_score"].max()
        colors = plt.cm.RdYlGn_r(norm_scores)
        
        bars = ax.barh(df_heat["pathway"], df_heat["avg_driver_score"], color=colors)
        
        # Add number of drivers as text
        for i, (bar, n_drivers) in enumerate(zip(bars, df_heat["n_drivers"].values)):
            ax.text(bar.get_width() + 0.01, bar.get_y() + bar.get_height()/2,
                   f'n={int(n_drivers)}', va='center', fontsize=9)
        
        ax.set_xlabel("Average Driver Score", fontsize=12, fontweight="bold")
        ax.set_ylabel("Pathway", fontsize=12, fontweight="bold")
        ax.set_title("Pathway Enrichment by Driver Genes", fontsize=14, fontweight="bold")
        ax.set_xlim(0, max(df_heat["avg_driver_score"]) * 1.15)
        
        plt.tight_layout()
        plt.savefig(output_fig, dpi=300, bbox_inches="tight")
        plt.close()
        print(f"[PathwayAgent] Saved heatmap to {output_fig}")
        return output_fig

    def visualize_pathway_network(self, output_fig=None):
        """Create gene-pathway network visualization."""
        if output_fig is None:
            output_fig = FIGS / "pathway_gene_network.png"
        
        # Get critical pathways
        critical = self.get_critical_pathways()
        
        if not critical:
            print("[PathwayAgent] No critical pathways with drivers found")
            return None
        
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        axes = axes.flatten()
        
        for idx, (pathway_name, data) in enumerate(critical[:4]):
            ax = axes[idx]
            
            drivers = data["drivers"]
            if not drivers:
                continue
            
            genes = sorted(drivers.items(), key=lambda x: x[1], reverse=True)[:10]
            gene_names = [g[0] for g in genes]
            scores = [g[1] for g in genes]
            
            colors = plt.cm.viridis(np.linspace(0, 1, len(genes)))
            ax.barh(gene_names, scores, color=colors)
            ax.set_xlabel("Driver Score", fontsize=11, fontweight="bold")
            ax.set_title(f"{pathway_name}\n({data['category']})", fontsize=12, fontweight="bold")
            ax.set_xlim(0, 1.0)
            
            for i, v in enumerate(scores):
                ax.text(v + 0.02, i, f"{v:.3f}", va="center", fontsize=9)
        
        # Hide unused subplots
        for idx in range(len(critical), 4):
            axes[idx].axis("off")
        
        plt.suptitle("Critical Pathways - Top Driver Genes", 
                    fontsize=16, fontweight="bold", y=0.995)
        plt.tight_layout()
        plt.savefig(output_fig, dpi=300, bbox_inches="tight")
        plt.close()
        print(f"[PathwayAgent] Saved network visualization to {output_fig}")
        return output_fig

    def _get_results_dataframe(self):
        """Convert results to dataframe."""
        rows = []
        for pathway_name, data in self.pathway_results.items():
            rows.append({
                "pathway": pathway_name,
                "n_drivers": data["n_drivers"],
                "avg_driver_score": data["avg_driver_score"],
                "driver_rate": data["driver_rate"],
                "p_value": data["p_value"],
            })
        return pd.DataFrame(rows)

    def print_summary(self):
        """Print pathway analysis summary."""
        print("\n" + "="*80)
        print("PATHWAY ANALYSIS SUMMARY")
        print("="*80)
        
        print(f"\nDriver genes analyzed: {len(self.driver_genes)}")
        print(f"Pathways with drivers: {sum(1 for d in self.pathway_results.values() if d['n_drivers'] > 0)}")
        
        critical = self.get_critical_pathways()
        print(f"\n[CRITICAL PATHWAYS] ({len(critical)} pathways)")
        print("-" * 80)
        for pathway_name, data in critical:
            print(f"  {pathway_name}")
            print(f"    Driver genes: {list(data['drivers'].keys())}")
            print(f"    Avg score: {data['avg_driver_score']:.3f}")
            print(f"    Impact: {data['impact']} | p-value: {data['p_value']:.2e}")
        
        top_pathways = self.get_top_pathways(top_n=10)
        print(f"\n[TOP 10 PATHWAYS BY DRIVER SCORE]")
        print("-" * 80)
        for pathway_name, data in top_pathways:
            if data['n_drivers'] > 0:
                print(f"  {data['n_drivers']:2d} drivers | "
                      f"avg={data['avg_driver_score']:.3f} | "
                      f"{pathway_name}")


def main():
    """Main execution."""
    print("\n" + "="*80)
    print("STEP 5 — PATHWAY ANALYSIS AGENT")
    print("="*80)
    
    # Initialize agent
    agent = PathwayAgent()
    
    # Example driver genes (would come from Mutation Agent in practice)
    example_drivers = {
        "EGFR": 0.92,
        "TP53": 0.85,
        "KRAS": 0.78,
        "PTEN": 0.82,
        "PIK3CA": 0.75,
        "RB1": 0.88,
        "ARID1A": 0.71,
        "NF1": 0.79,
        "BRAF": 0.68,
        "SMAD4": 0.74,
    }
    
    # Load and analyze
    agent.load_mutation_output(example_drivers)
    agent.analyze_pathways()
    
    # Export results
    df = agent.export_results()
    agent.export_json()
    
    # Visualizations
    agent.visualize_pathway_heatmap()
    agent.visualize_pathway_network()
    
    # Summary
    agent.print_summary()
    
    print("\n[PathwayAgent] Analysis complete!")
    print(f"[PathwayAgent] Results saved to {OUT}/")
    print(f"[PathwayAgent] Figures saved to {FIGS}/")


if __name__ == "__main__":
    main()
