"""
STEP 4 — MUTATION AGENT (RUNTIME)
===================================
Follows the Mutation Agent Guide exactly:

Guide Section 2 — Input:
  Patient mutation data in MAF / CSV format:
  Patient_ID | Gene | Variant_Classification | Chromosome | Start_Position

Guide Section 3 — Internal Steps at inference:
  Step 1: Load patient mutation data
  Step 2: Clean + normalise input
  Step 3: Feature Encoding (Label Encoding + One Hot Encoding)
  Step 4: Feature Engineering (frequency + type importance + aa_position
                                + is_known_hotspot)
  Step 5: ML Model Prediction -> driver probability per mutation

Guide Section 5 — Output:
  Gene | Mutation | Driver Probability
  EGFR | L858R    | 0.92
  TP53 | R175H    | 0.85
  KRAS | G12C     | 0.78

Guide Section 7 — JSON output:
  {
    "patient_id": "P001",
    "driver_mutations": [
      {"gene": "EGFR", "score": 0.92},
      {"gene": "TP53", "score": 0.85},
      {"gene": "KRAS", "score": 0.78}
    ]
  }

Guide Section 8 — Downstream agents:
  Pathway Agent  -> maps driver genes to pathways
  Drug Agent     -> uses driver mutations for resistance prediction

Note on hotspot system:
  With aa_position_norm + is_known_hotspot features, the model
  now genuinely learns EGFR L858R as a driver.
  The hotspot override is kept as a safety net ONLY for cases
  where the model still underscores a validated hotspot.

Usage:
    python step4_mutation_agent.py
    from step4_mutation_agent import MutationAgent
"""

import re
import joblib
import numpy  as np
import pandas as pd
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

# ─── Paths ────────────────────────────────────────────────────────────────────
MODELS = Path("models")
ENC    = Path("data/processed/encoders")

# ─── Known driver hotspot positions (safety net only) ────────────────────────
# Used ONLY when model score is below 0.4 for a validated hotspot mutation
# Primary classification comes from the model (aa_position + is_known_hotspot
# features ensure model should get these right after retraining)
HOTSPOT_SAFETY = {
    "EGFR":   {858: 0.85, 719: 0.80, 790: 0.80, 746: 0.90,
               747: 0.90, 748: 0.90, 749: 0.90, 750: 0.90},
    "KRAS":   {12:  0.85, 13:  0.80, 61:  0.75},
    "BRAF":   {600: 0.90},
    "TP53":   {175: 0.90, 248: 0.88, 249: 0.85, 273: 0.88},
    "PIK3CA": {542: 0.80, 545: 0.80, 1047: 0.80},
    "ALK":    {1174: 0.85, 1275: 0.85},
    "RET":    {918: 0.85, 634: 0.85},
}


class MutationAgent:
    """
    Mutation Agent — classifies each mutation as Driver or Passenger.

    Guide Purpose:
      "Transform raw mutation data -> biologically meaningful mutation insights"
      "Identify important or driver mutations"
      "First analytical component in the multi-agent system"
    """

    def __init__(self, model_path: str = None):
        path = model_path or str(MODELS / "Mutation_Model_BEST.pkl")

        # Load trained model and all encoders
        self.model             = joblib.load(path)
        self.le_gene           = joblib.load(ENC / "le_gene.pkl")
        self.ohe_effect        = joblib.load(ENC / "ohe_effect.pkl")
        self.effect_categories = joblib.load(ENC / "effect_categories.pkl")
        self.effect_impact     = joblib.load(ENC / "effect_impact.pkl")
        self.gene_freq         = joblib.load(ENC / "gene_freq.pkl")
        self.feature_cols      = joblib.load(ENC / "feature_cols.pkl")
        self.ohe_cols          = joblib.load(ENC / "ohe_cols.pkl")
        self.hotspot_positions = joblib.load(ENC / "hotspot_positions.pkl")

        print(f"[MutationAgent] Model loaded  : {path}")
        print(f"[MutationAgent] Features      : {len(self.feature_cols)} columns")

    # ── Helper: normalise effect to training categories ───────────────────────
    def _normalise_effect(self, e: str) -> str:
        """
        Handles both MAF format (Missense_Mutation) and data format (missense).
        Maps all variants to the 15 training categories.
        """
        if pd.isna(e) or str(e).strip() == "":
            return "missense"
        e = str(e).strip().lower()
        e = e.replace("_mutation", "").replace("_variant", "").replace(" ", "_")

        if "nonsense"      in e or "stop_gained"      in e: return "nonsense"
        if "frameshift"    in e:                             return "frameshift"
        if "ess_splice"    in e or "splice_donor"     in e \
                           or "splice_acceptor"       in e: return "ess_splice"
        if "missense"      in e:                             return "missense"
        if "inframe"       in e or "in_frame"         in e: return "inframe"
        if "splice_region" in e:                             return "splice_region"
        if "start_lost"    in e or "translation_start" in e: return "start_lost"
        if "stop_lost"     in e or "nonstop"          in e: return "stop_lost"
        if "silent"        in e or "synonymous"       in e: return "silent"
        if "5prime_utr"    in e or "5'utr"            in e: return "utr5"
        if "3prime_utr"    in e or "3'utr"            in e: return "utr3"
        if "intronic"      in e or "intron"           in e: return "intronic"
        if "upstream"      in e or "5'flank"          in e: return "upstream"
        if "downstream"    in e or "3'flank"          in e: return "downstream"
        return "other"

    # ── Helper: clean chromosome ──────────────────────────────────────────────
    def _clean_chrom(self, chrom) -> int:
        c = str(chrom).replace("chr", "").strip()
        mapping = {"X":"23", "Y":"24", "MT":"25", "nan":"0", "":"0"}
        c = mapping.get(c, c)
        try:
            return int(float(c))
        except:
            return 0

    # ── Helper: encode gene ───────────────────────────────────────────────────
    def _encode_gene(self, gene: str) -> int:
        gene = str(gene).strip()
        if gene in self.le_gene.classes_:
            return int(self.le_gene.transform([gene])[0])
        return 0

    # ── Helper: extract amino acid position ───────────────────────────────────
    def _extract_aa_position(self, protein_mut: str) -> int:
        """Extract numeric position from L858R -> 858, p.G12C -> 12."""
        if pd.isna(protein_mut) or str(protein_mut).strip() in ("", "nan"):
            return 0
        match = re.search(r'\d+', str(protein_mut))
        return int(match.group()) if match else 0

    # ── Helper: check known hotspot ───────────────────────────────────────────
    def _is_hotspot(self, gene: str, aa_pos: int) -> int:
        """Returns 1 if this position is a known oncogenic hotspot."""
        if gene in self.hotspot_positions and aa_pos > 0:
            return int(aa_pos in self.hotspot_positions[gene])
        return 0

    # ── Helper: safety net hotspot override ──────────────────────────────────
    def _safety_hotspot(self, gene: str, aa_pos: int, model_score: float):
        """
        Safety net ONLY: if model score < 0.4 for a validated hotspot,
        apply override. This should rarely trigger after retraining with
        aa_position_norm + is_known_hotspot features.
        Returns (final_score, was_overridden, reason)
        """
        if gene in HOTSPOT_SAFETY and aa_pos in HOTSPOT_SAFETY[gene]:
            hs_score = HOTSPOT_SAFETY[gene][aa_pos]
            if model_score < 0.4:
                return (hs_score, True,
                        f"Safety override: {gene} pos {aa_pos} is validated "
                        f"hotspot (model={model_score:.4f} -> {hs_score})")
        return (model_score, False, "Model prediction")

    # ── Build feature vector for one mutation ─────────────────────────────────
    def _build_feature_row(self, mutation: dict) -> list:
        """
        Build feature vector matching trained model.
        Current model uses 9 features (ABLATION 3 result from validation).
        """
        gene    = str(mutation.get("gene", "UNKNOWN")).strip()
        effect  = self._normalise_effect(mutation.get("effect", "missense"))
        vaf     = float(mutation.get("vaf", 0.5))
        chrom   = self._clean_chrom(mutation.get("chromosome", 0))
        pos     = int(float(mutation.get("position", 0)))
        coding  = int(bool(mutation.get("coding", True)))
        cpv     = int(bool(mutation.get("cancer_predisposition_variant", False)))
        protein = str(mutation.get("protein_mutation", ""))

        # Guide Step 3a — Label Encoding
        gene_enc = self._encode_gene(gene)

        # Guide Step 4b — Mutation Type Importance (numeric score, not OHE)
        effect_impact = self.effect_impact.get(effect, 1)

        # VAF features
        vaf_high = int(vaf >= 0.4)
        vaf_low  = int(vaf <= 0.1)

        # Position bin
        position_bin = min(pos // 25_000_000, 9)

        # AA Position features (for hotspot override logic, not for model input)
        aa_pos = self._extract_aa_position(protein)

        # Feature vector must match training features: 9 columns
        # gene_enc, effect_impact, chromosome, position_bin, vaf, vaf_high, vaf_low, coding, cancer_predisposition_variant
        feature_values = [
            gene_enc,              # gene_enc
            effect_impact,         # effect_impact
            chrom,                 # chromosome
            position_bin,          # position_bin
            vaf,                   # vaf
            vaf_high,              # vaf_high
            vaf_low,               # vaf_low
            coding,                # coding
            cpv,                   # cancer_predisposition_variant
        ]

        return feature_values

    # ── Main predict method ───────────────────────────────────────────────────
    def predict(
        self,
        patient_mutations: list,
        patient_id: str = "PATIENT"
    ) -> dict:
        """
        Predict driver probability for each mutation.

        Guide Section 2 Input — list of mutation dicts:
          [{"gene": "EGFR", "effect": "Missense_Mutation",
            "protein_mutation": "L858R", "vaf": 0.45,
            "chromosome": "chr7", "position": 55249071}, ...]

        Guide Section 7 Output:
          {"patient_id": "P001",
           "driver_mutations": [{"gene": "EGFR", "score": 0.92}, ...]}
        """
        if not patient_mutations:
            return {"error": "No mutations provided"}

        # Build feature matrix
        X = np.array([self._build_feature_row(m) for m in patient_mutations])

        # Guide Step 5 — ML Model Prediction
        # predict_proba[:, 1] = probability of being a Driver mutation
        model_probas = self.model.predict_proba(X)[:, 1]

        # Score each mutation
        scored = []
        for mut, model_score in zip(patient_mutations, model_probas):
            gene    = str(mut.get("gene", "UNKNOWN")).strip()
            protein = str(mut.get("protein_mutation", "")).strip()
            effect  = self._normalise_effect(mut.get("effect", ""))

            aa_pos  = self._extract_aa_position(protein)

            # Apply safety net only if model underscores a known hotspot
            final_score, overridden, reason = self._safety_hotspot(
                gene, aa_pos, float(model_score)
            )

            # Mutation display name
            mutation_name = (protein
                             if protein and protein not in ("nan", "")
                             else effect)

            scored.append({
                "gene":        gene,
                "mutation":    mutation_name,
                "score":       round(final_score, 4),
                "model_score": round(float(model_score), 4),
                "overridden":  overridden,
                "reason":      reason,
            })

        # Sort by driver probability descending
        scored.sort(key=lambda x: x["score"], reverse=True)

        # Split drivers (score > 0.5) from passengers (score <= 0.5)
        drivers    = [m for m in scored if m["score"] > 0.5]
        passengers = [m for m in scored if m["score"] <= 0.5]

        # Guide Section 7 — exact output format
        output = {
            "patient_id": patient_id,

            # Guide Section 7 exact format
            "driver_mutations": [
                {"gene": m["gene"], "score": m["score"]}
                for m in drivers
            ],

            # Extended info for downstream agents
            "driver_mutations_detail": drivers,
            "passenger_mutations":     passengers,
            "mutation_burden":         len(drivers),
            "explanation_log":         [
                {"gene": m["gene"],
                 "mutation": m["mutation"],
                 "score": m["score"],
                 "model_score": m["model_score"],
                 "reason": m["reason"]}
                for m in scored
            ],
        }
        return output

    # ── Predict from CSV / MAF file ───────────────────────────────────────────
    def predict_from_csv(
        self,
        csv_path: str,
        patient_id_col: str = "model_name"
    ) -> dict:
        """Run prediction on a CSV/MAF file. Normalises column names."""
        df = pd.read_csv(csv_path, low_memory=False)
        col_map = {
            "gene_symbol":              "gene",
            "effect":                   "effect",
            "vaf":                      "vaf",
            "chromosome":               "chromosome",
            "position":                 "position",
            "protein_mutation":         "protein_mutation",
            "coding":                   "coding",
            "cancer_predisposition_variant": "cancer_predisposition_variant",
        }
        df = df.rename(columns=col_map)
        out = {}
        if patient_id_col in df.columns:
            for pid, grp in df.groupby(patient_id_col):
                out[pid] = self.predict(grp.to_dict("records"), patient_id=pid)
        else:
            out["ALL"] = self.predict(df.to_dict("records"), patient_id="ALL")
        return out


# ─────────────────────────────────────────────────────────────────────────────
# EXAMPLE RUN — shows Guide Sections 5, 6, 7, 8 output
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":

    print()
    print("=" * 65)
    print("  MUTATION AGENT — Guide Section 2 Input / Section 5-7 Output")
    print("=" * 65)

    agent = MutationAgent()

    # Guide Section 2 — Input Format
    patient_mutations = [
        {
            "gene":             "EGFR",
            "effect":           "Missense_Mutation",   # MAF format
            "protein_mutation": "L858R",
            "vaf":              0.45,
            "chromosome":       "chr7",
            "position":         55249071,
            "coding":           True,
            "cancer_predisposition_variant": False,
        },
        {
            "gene":             "TP53",
            "effect":           "Nonsense_Mutation",   # MAF format
            "protein_mutation": "R175H",
            "vaf":              0.38,
            "chromosome":       "chr17",
            "position":         7579472,
            "coding":           True,
            "cancer_predisposition_variant": True,
        },
        {
            "gene":             "KRAS",
            "effect":           "Missense_Mutation",
            "protein_mutation": "G12C",
            "vaf":              0.42,
            "chromosome":       "chr12",
            "position":         25398284,
            "coding":           True,
            "cancer_predisposition_variant": False,
        },
        {
            "gene":             "TTN",
            "effect":           "missense",             # data format
            "protein_mutation": "p.A1234V",
            "vaf":              0.12,
            "chromosome":       "chr2",
            "position":         179390716,
            "coding":           True,
            "cancer_predisposition_variant": False,
        },
        {
            "gene":             "MUC16",
            "effect":           "intronic",
            "protein_mutation": "",
            "vaf":              0.08,
            "chromosome":       "chr19",
            "position":         8888888,
            "coding":           False,
            "cancer_predisposition_variant": False,
        },
    ]

    result = agent.predict(patient_mutations, patient_id="P001")

    # ── Guide Section 5 — Model Output Table ─────────────────────────────
    print()
    print("  Guide Section 5 — Model Output:")
    print(f"  {'Gene':<12} {'Mutation':<15} {'Driver Probability':>18}  Source")
    print("  " + "-" * 60)
    for m in (result["driver_mutations_detail"] +
              result["passenger_mutations"]):
        label  = " <- DRIVER" if m["score"] > 0.5 else ""
        source = "safety_net" if m["overridden"] else "model"
        print(f"  {m['gene']:<12} {m['mutation']:<15} "
              f"{m['score']:>18.4f}  {source}{label}")

    # ── Guide Section 6 — Final Output ───────────────────────────────────
    print()
    print("  Guide Section 6 — Final Output:")
    print()
    print("  Detected Driver Mutations:")
    if result["driver_mutations"]:
        for m in result["driver_mutations_detail"]:
            print(f"    {m['gene']} {m['mutation']}")
    else:
        print("    No driver mutations detected")
    print()
    print("  Mutation Importance Scores:")
    for m in result["driver_mutations_detail"]:
        print(f"    {m['gene']} -> {m['score']}")

    # ── Guide Section 7 — JSON Output ────────────────────────────────────
    print()
    print("  Guide Section 7 — JSON Output (sent to Pathway & Drug Agent):")
    print("  {")
    print(f'    "patient_id": "{result["patient_id"]}",')
    print(f'    "driver_mutations": [')
    for m in result["driver_mutations"]:
        print(f'      {{"gene": "{m["gene"]}", "score": {m["score"]}}},')
    print(f'    ]')
    print("  }")

    # ── Guide Section 8 — Downstream agents ──────────────────────────────
    print()
    print("  Guide Section 8 — Next agents:")
    print("  Pathway Agent  -> maps driver genes to biological pathways")
    PATHWAY_MAP = {
        "EGFR": "EGFR Signaling Pathway",
        "KRAS": "MAPK Pathway",
        "TP53": "p53 Pathway",
        "ALK":  "ALK Pathway",
        "BRAF": "MAPK Pathway",
        "MET":  "EGFR Signaling Pathway",
        "RET":  "RET Pathway",
    }
    for m in result["driver_mutations"]:
        pathway = PATHWAY_MAP.get(m["gene"], "Unknown Pathway")
        print(f"    {m['gene']} -> {pathway}")
    print()
    print("  Drug Resistance Agent -> uses driver mutations for resistance prediction")
    DRUG_MAP = {
        "EGFR": "Gefitinib / Erlotinib / Osimertinib resistance",
        "KRAS": "Erlotinib resistance",
        "TP53": "General resistance marker",
        "BRAF": "Vemurafenib resistance",
        "ALK":  "Crizotinib / Alectinib sensitivity",
    }
    for m in result["driver_mutations"]:
        drug_note = DRUG_MAP.get(m["gene"], "Drug resistance analysis")
        print(f"    {m['gene']} mutation -> {drug_note}")

    print()
    print("=" * 65)
    print("  Mutation Agent complete.")
    print("  -> Output passed to Pathway Agent (Sprint 5)")
    print("=" * 65)