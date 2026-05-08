"""Quick test of the prediction engine."""
import sys
sys.path.insert(0, '.')
from resistance_predictor import predict_resistance

r = predict_resistance([
    {'gene': 'EGFR', 'vaf': 0.45},
    {'gene': 'TP53', 'vaf': 0.82},
    {'gene': 'KRAS', 'vaf': 0.35},
])

print(f"Pathways affected: {len(r['affected_pathways'])}")
print(f"Drugs evaluated: {r['mutation_summary']['drugs_evaluated']}")

print("\nTop 5 most sensitive drugs:")
for i, d in enumerate(r['drug_predictions'][:5], 1):
    print(f"  {i}. {d['drug_name']:25s} resist={d['resistance_score']:.3f}  [{d['category']}]")
    for x in d['reasoning']:
        print(f"       {x}")

print("\nTop 3 most resistant drugs:")
for i, d in enumerate(r['drug_predictions'][-3:], 1):
    print(f"  {i}. {d['drug_name']:25s} resist={d['resistance_score']:.3f}  [{d['category']}]")
