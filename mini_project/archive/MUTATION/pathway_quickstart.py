"""
PATHWAY ANALYSIS QUICK START
============================
Simple example showing how to use PathwayAgent with Mutation Agent outputs.

Usage:
    python pathway_quickstart.py
"""

from step5_pathway_agent import PathwayAgent
import json

print("\n" + "="*80)
print("PATHWAY ANALYSIS QUICK START")
print("="*80)

# ─── Example 1: Basic Pathway Analysis from Driver Genes ─────────────────────────
print("\n[EXAMPLE 1] Basic Pathway Analysis")
print("-" * 80)

# These would typically come from the Mutation Agent
driver_genes = {
    "TP53": 0.85,      # p53 tumor suppressor (high confidence)
    "EGFR": 0.92,      # Receptor tyrosine kinase (very high confidence)
    "KRAS": 0.78,      # RAS pathway (high confidence)
    "PTEN": 0.82,      # PI3K/AKT pathway inhibitor
    "RB1": 0.88,       # Cell cycle regulator
}

# Initialize pathway agent
agent = PathwayAgent()
agent.load_mutation_output(driver_genes)
agent.analyze_pathways()

# Get summary
print("\nDriver genes to analyze:")
for gene, score in driver_genes.items():
    print(f"  {gene:12s} : {score:.3f}")

# Get critical pathways
critical_pathways = agent.get_critical_pathways()
print(f"\nCritical pathways affected: {len(critical_pathways)}")
for pathway_name, data in critical_pathways[:5]:
    print(f"\n  {pathway_name}")
    print(f"    Description : {data['description']}")
    print(f"    Driver genes: {list(data['drivers'].keys())}")
    print(f"    Avg score   : {data['avg_driver_score']:.3f}")
    print(f"    Category    : {data['category']}")

# ─── Example 2: Detailed Pathway Information ──────────────────────────────────────
print("\n\n[EXAMPLE 2] Detailed Pathway Information")
print("-" * 80)

# Get specific pathway details
pathway_name = "TP53_Pathway"
if pathway_name in agent.pathway_results:
    pathway = agent.pathway_results[pathway_name]
    print(f"\nPathway: {pathway_name}")
    print(f"  Description: {pathway['description']}")
    print(f"  Impact level: {pathway['impact']}")
    print(f"  All genes in pathway: {pathway['all_genes']}")
    print(f"  Drivers in pathway: {pathway['drivers']}")
    print(f"  Pathway coverage: {pathway['driver_rate']*100:.1f}%")

# ─── Example 3: Top Pathways Ranking ───────────────────────────────────────────────
print("\n\n[EXAMPLE 3] Top Pathways by Driver Score")
print("-" * 80)

top_pathways = agent.get_top_pathways(metric="avg_driver_score", top_n=8)
print("\nRanked by average driver score:")
for i, (pathway_name, data) in enumerate(top_pathways, 1):
    if data['n_drivers'] > 0:
        print(f"  {i}. {pathway_name}")
        print(f"     {data['n_drivers']} driver(s) | avg score: {data['avg_driver_score']:.3f}")

# ─── Example 4: Category-based Analysis ─────────────────────────────────────────────
print("\n\n[EXAMPLE 4] Pathways by Category")
print("-" * 80)

categories = {}
for pathway_name, data in agent.pathway_results.items():
    category = data['category']
    if category not in categories:
        categories[category] = {"count": 0, "driver_count": 0, "avg_score": []}
    categories[category]["count"] += 1
    if data['n_drivers'] > 0:
        categories[category]["driver_count"] += 1
        categories[category]["avg_score"].append(data['avg_driver_score'])

for category, stats in sorted(categories.items()):
    avg_score = sum(stats['avg_score']) / len(stats['avg_score']) if stats['avg_score'] else 0
    print(f"\n  {category.upper()}")
    print(f"    Total pathways: {stats['count']}")
    print(f"    Pathways with drivers: {stats['driver_count']}")
    print(f"    Average driver score: {avg_score:.3f}")

# ─── Example 5: Export Results ──────────────────────────────────────────────────────
print("\n\n[EXAMPLE 5] Exporting Results")
print("-" * 80)

# Export to CSV
df = agent.export_results()
print(f"\n✓ Exported pathway analysis to CSV")
print(f"  Rows: {len(df)}")
print(f"  Top 5 pathways by score:")
print(df[["pathway", "n_driver_genes", "avg_driver_score"]].head(5).to_string(index=False))

# Export to JSON
json_output = agent.export_json()
print(f"\n✓ Exported detailed results to JSON")
print(f"  Pathways with drivers: {len([p for p in json_output['pathways'].values() if p['n_drivers'] > 0])}")

# Generate visualizations
agent.visualize_pathway_heatmap()
print(f"\n✓ Generated pathway enrichment heatmap")

agent.visualize_pathway_network()
print(f"✓ Generated pathway network visualization")

# ─── Example 6: Cancer Biology Interpretation ──────────────────────────────────────
print("\n\n[EXAMPLE 6] Cancer Biology Interpretation")
print("-" * 80)

print("\nDriver gene pathways indicate:")

growth_signal = any(
    p['n_drivers'] > 0 for name, p in agent.pathway_results.items()
    if p['category'] == 'growth_signaling'
)
if growth_signal:
    print("  ✓ GROWTH SIGNALING: Activation of proliferation pathways (MAPK, PI3K, RTK)")

cell_cycle = any(
    p['n_drivers'] > 0 for name, p in agent.pathway_results.items()
    if p['category'] == 'cell_cycle'
)
if cell_cycle:
    print("  ✓ CELL CYCLE: Loss of cell cycle checkpoints (p53, Rb)")

genomic_stability = any(
    p['n_drivers'] > 0 for name, p in agent.pathway_results.items()
    if p['category'] == 'genomic_stability'
)
if genomic_stability:
    print("  ✓ GENOMIC STABILITY: Impaired DNA damage response")

differentiation = any(
    p['n_drivers'] > 0 for name, p in agent.pathway_results.items()
    if p['category'] == 'differentiation'
)
if differentiation:
    print("  ✓ DIFFERENTIATION: Altered developmental pathways (Wnt, TGF-β)")

immune_evasion = any(
    p['n_drivers'] > 0 for name, p in agent.pathway_results.items()
    if p['category'] == 'immune_evasion'
)
if immune_evasion:
    print("  ✓ IMMUNE EVASION: Checkpoint pathway alterations")

# ─── Final Summary ─────────────────────────────────────────────────────────────────
print("\n\n" + "="*80)
print("QUICK START COMPLETE")
print("="*80)

print("\nNext Steps:")
print("  1. Use mutation_to_pathway_pipeline.py for full patient analysis")
print("  2. Customize PATHWAYS dict in step5_pathway_agent.py for specific needs")
print("  3. Integrate with Drug Agent for treatment recommendations")
print("  4. Use pathway results for patient stratification and prognosis")

print("\nFor more information:")
print("  - See PIPELINE_DOCUMENTATION.md")
print("  - Check per_gene_analysis.py for mutation-level details")
print("  - Review step4_mutation_agent.py for driver prediction details")

print("\n" + "="*80)
