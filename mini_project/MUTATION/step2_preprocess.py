"""
STEP 2 — DATA PREPROCESSING FOR MUTATION AGENT
================================================
Guide Reference: Section 3 — Internal Steps Performed by Mutation Agent

  Step 1 — Data Loading       : load mutations_all.csv using pandas
  Step 2 — Data Cleaning      : remove missing, duplicates, irrelevant columns
  Step 3 — Feature Encoding   : Label Encoding (gene) + One Hot Encoding (effect)
  Step 4 — Feature Engineering: mutation frequency + mutation type importance
                                 + aa_position (fixes EGFR misclassification)
                                 + is_known_hotspot (biological prior knowledge)

Label: cancer_driver column
  t = Driver   -> 1  (causes cancer progression)
  f = Passenger -> 0 (does not contribute to cancer growth)

Optimisations:
  1. Filter to LUNG_GENES immediately — 9.2M -> ~21K rows
  2. Simplified effect categories — 40 types -> 15 clean types
  3. Simple integer bucketing instead of qcut()
  4. Gene frequency computed on filtered data only

Run:
    python step2_preprocess.py
"""

import re
import warnings
import time
import pandas as pd
import numpy  as np
import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
from sklearn.preprocessing import LabelEncoder, OneHotEncoder

warnings.filterwarnings("ignore")

# ─── Paths ────────────────────────────────────────────────────────────────────
RAW  = Path("data/raw")
PROC = Path("data/processed")
ENC  = PROC / "encoders"
FIGS = Path("figures")
for d in [PROC, ENC, FIGS]:
    d.mkdir(parents=True, exist_ok=True)

# ─── Lung cancer driver genes ─────────────────────────────────────────────────
# Filter immediately after load — reduces 9.2M rows -> ~21K rows
LUNG_GENES = {
    "EGFR", "KRAS", "TP53",   "ALK",    "ROS1",
    "MET",  "BRAF", "ERBB2",  "RET",    "STK11",
    "KEAP1","NF1",  "PIK3CA", "CDKN2A", "RB1",
    "PTEN", "SMAD4","ARID1A", "SETD2",
}

# ─── Known oncogenic hotspot positions ────────────────────────────────────────
# Used to create is_known_hotspot feature
# These are the amino acid positions of the most clinically validated
# driver mutations in lung cancer — gives the model biological prior knowledge
HOTSPOT_POSITIONS = {
    "EGFR":   {858, 719, 746, 747, 748, 749, 750, 790, 861, 768},
    "KRAS":   {12, 13, 61},
    "BRAF":   {600},
    "TP53":   {175, 248, 249, 273, 245, 220, 179, 282},
    "PIK3CA": {542, 545, 1047},
    "MET":    {14},
    "ERBB2":  {310, 309},
    "ALK":    {1174, 1275},
    "RET":    {918, 634},
    "NRAS":   {12, 13, 61},
}

# ─── Effect simplification ────────────────────────────────────────────────────
# Collapse 40 raw variant types -> 15 clean biologically meaningful categories
def simplify_effect(e: str) -> str:
    if pd.isna(e):
        return "missense"
    e = str(e).strip().lower()
    e = e.replace("_mutation", "").replace("_variant", "").replace(" ", "_")

    if "nonsense"      in e or "stop_gained"      in e: return "nonsense"
    if "frameshift"    in e:                             return "frameshift"
    if "ess_splice"    in e or "splice_donor"     in e \
                           or "splice_acceptor"   in e: return "ess_splice"
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

# ─── Mutation type impact scores ──────────────────────────────────────────────
# Guide Section 3 Step 4 table:
#   Nonsense/Frameshift -> High     (3)
#   Missense            -> Moderate (2)
#   Silent              -> Low      (1)
#   Intronic/Upstream   -> None     (0)
EFFECT_IMPACT = {
    "nonsense":      3,
    "frameshift":    3,
    "ess_splice":    3,
    "start_lost":    3,
    "stop_lost":     2,
    "inframe":       2,
    "missense":      2,
    "splice_region": 2,
    "silent":        1,
    "utr5":          1,
    "utr3":          1,
    "other":         1,
    "intronic":      0,
    "upstream":      0,
    "downstream":    0,
}

EFFECT_CATEGORIES = sorted(EFFECT_IMPACT.keys())   # 15 fixed categories


# ─── Helper: extract amino acid position from protein_mutation ────────────────
def extract_aa_position(protein_mut: str) -> int:
    """
    Extract the amino acid position number from protein mutation string.
    Examples:
      L858R   -> 858
      p.G12C  -> 12
      R175H   -> 175
      E746del -> 746
      nan/""  -> 0
    """
    if pd.isna(protein_mut) or str(protein_mut).strip() in ("", "nan", "None"):
        return 0
    match = re.search(r'\d+', str(protein_mut))
    return int(match.group()) if match else 0


# ─── Helper: check if mutation hits a known hotspot position ──────────────────
def is_hotspot(gene: str, aa_pos: int) -> int:
    """
    Returns 1 if this gene + amino acid position is a known oncogenic hotspot.
    Returns 0 otherwise.
    This gives the model biological prior knowledge about important positions.
    """
    if gene in HOTSPOT_POSITIONS and aa_pos > 0:
        return int(aa_pos in HOTSPOT_POSITIONS[gene])
    return 0


print()
print("=" * 65)
print("  STEP 2 — Mutation Agent Data Preprocessing")
print("=" * 65)
t_total = time.time()


# ═════════════════════════════════════════════════════════════════════════════
# STEP 1 — DATA LOADING  (Guide Section 3, Step 1)
# "The agent loads mutation dataset using pandas"
# ═════════════════════════════════════════════════════════════════════════════
print()
print("[STEP 1] Data Loading ...")
t0 = time.time()

LOAD_COLS = [
    "gene_symbol", "model_name",   "effect",    "vaf",
    "chromosome",  "position",     "coding",
    "cancer_driver", "protein_mutation",
    "cancer_predisposition_variant",
]

mut = pd.read_csv(
    RAW / "mutations_all.csv",
    usecols=LOAD_COLS,
    low_memory=False
)

print(f"         Loaded          : {len(mut):,} rows × {len(mut.columns)} cols"
      f"  ({time.time()-t0:.1f}s)")
print(f"         cancer_driver   : {mut['cancer_driver'].value_counts().to_dict()}")
print(f"         Driver rate     : {(mut['cancer_driver']=='t').mean():.4%}")


# ─── KEY OPTIMISATION — Filter to lung genes immediately ─────────────────────
print()
print("[OPT]  Filtering to 19 lung cancer genes ...")
t0 = time.time()
mut = mut[mut["gene_symbol"].isin(LUNG_GENES)].copy()
print(f"         After filter    : {len(mut):,} rows  ({time.time()-t0:.1f}s)")
print(f"         Genes found     : {sorted(mut['gene_symbol'].unique())}")


# ═════════════════════════════════════════════════════════════════════════════
# STEP 2 — DATA CLEANING  (Guide Section 3, Step 2)
# "Remove missing values, duplicate entries, irrelevant metadata columns"
# ═════════════════════════════════════════════════════════════════════════════
print()
print("[STEP 2] Data Cleaning ...")
t0 = time.time()

# Remove irrelevant metadata columns
# Guide says remove: center, sequencer, study_id
# Equivalents here: ensembl_gene_id, transcript_id, rna_mutation,
#                   cdna_mutation, source, gene_id, model_id
# (already not loaded via usecols — no further action needed)

# Remove rows missing critical values
before = len(mut)
mut = mut.dropna(subset=["gene_symbol", "effect", "cancer_driver"])
print(f"         After removing missing values  : {len(mut):,}  "
      f"(removed {before-len(mut):,})")

# Remove duplicate mutation entries (Guide Step 2)
before = len(mut)
mut = mut.drop_duplicates(
    subset=["gene_symbol", "model_name", "effect", "chromosome", "position"]
)
print(f"         After removing duplicates      : {len(mut):,}  "
      f"(removed {before-len(mut):,})")

# Clean effect — simplify to 15 clean categories
mut["effect"] = mut["effect"].apply(simplify_effect)
print(f"         Effect categories              : "
      f"{sorted(mut['effect'].unique())}")

# Clean chromosome — remove chr prefix, map X=23, Y=24
mut["chromosome"] = (
    mut["chromosome"].astype(str)
    .str.replace("chr", "", regex=False).str.strip()
    .replace({"X": "23", "Y": "24", "nan": "0", "": "0"})
)
mut["chromosome"] = (pd.to_numeric(mut["chromosome"], errors="coerce")
                     .fillna(0).astype(int))

# Clean position
mut["position"] = (pd.to_numeric(mut["position"], errors="coerce")
                   .fillna(0).astype(int))

# Clean coding flag — t/f -> 1/0
mut["coding"] = (
    mut["coding"].astype(str).str.strip().str.lower() == "t"
).astype(int)

# Clean cancer_predisposition_variant — t/f -> 1/0
mut["cancer_predisposition_variant"] = (
    mut["cancer_predisposition_variant"]
    .astype(str).str.strip().str.lower() == "t"
).astype(int)

# Fill missing VAF with median
vaf_median = mut["vaf"].median()
mut["vaf"] = mut["vaf"].fillna(vaf_median)

# Create binary label: t=Driver(1), f=Passenger(0)
mut["LABEL"] = (
    mut["cancer_driver"].str.strip().str.lower() == "t"
).astype(int)
mut.drop(columns=["cancer_driver"], inplace=True)

print(f"         Final shape                    : {mut.shape}")
print(f"         Driver  (1)                    : {mut['LABEL'].sum():,}  "
      f"({mut['LABEL'].mean():.4%})")
print(f"         Passenger (0)                  : {(mut['LABEL']==0).sum():,}")
print(f"         Time                           : {time.time()-t0:.1f}s")


# ═════════════════════════════════════════════════════════════════════════════
# STEP 3 — FEATURE ENCODING  (Guide Section 3, Step 3)
# "Convert categorical mutation data into numbers"
# Techniques: Label Encoding + One Hot Encoding
# ═════════════════════════════════════════════════════════════════════════════
print()
print("[STEP 3] Feature Encoding ...")
t0 = time.time()

# 3a. Label Encoding for gene name
# Guide table: EGFR=1, KRAS=2, TP53=3 ...
le_gene = LabelEncoder()
mut["gene_enc"] = le_gene.fit_transform(mut["gene_symbol"].astype(str))
joblib.dump(le_gene, ENC / "le_gene.pkl")
print(f"         Label Encoding  : gene_symbol -> gene_enc")
print(f"         Gene classes    : {len(le_gene.classes_)}")
for gene in ["EGFR", "KRAS", "TP53"]:
    if gene in le_gene.classes_:
        enc = le_gene.transform([gene])[0]
        print(f"           {gene} -> {enc}")

# 3b. One Hot Encoding for effect (mutation type)
# OHE is correct because mutation types are NOMINAL (no numeric order)
# Fixed categories ensure train/inference columns are always identical
# ABLATION 3: DISABLED OHE to test if model relies on effect type encoding
ohe_effect = OneHotEncoder(
    categories=[EFFECT_CATEGORIES],
    sparse_output=False,
    handle_unknown="ignore",
    dtype=int
)
ohe_matrix = ohe_effect.fit_transform(mut[["effect"]])
ohe_cols   = [f"ohe_effect_{c}" for c in EFFECT_CATEGORIES]
# ohe_df     = pd.DataFrame(ohe_matrix, columns=ohe_cols,
#                            dtype=int, index=mut.index)
# mut = pd.concat([mut, ohe_df], axis=1)
ohe_cols = []  # ABLATION 3: Disable OHE columns
joblib.dump(ohe_effect, ENC / "ohe_effect.pkl")
joblib.dump(EFFECT_CATEGORIES, ENC / "effect_categories.pkl")
print(f"         One Hot Encoding: effect -> DISABLED (ablation 3)")
print(f"         OHE columns     : DISABLED (ablation 3)")
print(f"         Encoding time   : {time.time()-t0:.1f}s")


# ═════════════════════════════════════════════════════════════════════════════
# STEP 4 — FEATURE ENGINEERING  (Guide Section 3, Step 4)
# Guide specifies two features PLUS two additional biological features:
#   1. Mutation Frequency    — how often each gene mutates  (GUIDE)
#   2. Mutation Type Impact  — impact score per type        (GUIDE)
#   3. AA Position           — amino acid position number   (FIX for EGFR)
#   4. Is Known Hotspot      — known oncogenic position     (FIX for EGFR)
# ═════════════════════════════════════════════════════════════════════════════
print()
print("[STEP 4] Feature Engineering ...")
t0 = time.time()

# 4a. Mutation Frequency per gene (GUIDE FEATURE 1) — ABLATION TEST 2 DISABLED
# "How often a gene mutates"
# Example: TP53=210, EGFR=120, KRAS=95
gene_freq = (mut["gene_symbol"].value_counts()
             .rename("gene_mutation_count")
             .reset_index()
             .rename(columns={"index": "gene_symbol"}))
gene_freq_dict = dict(zip(gene_freq["gene_symbol"],
                           gene_freq["gene_mutation_count"]))
# ABLATION TEST 2 - Disable mutation frequency feature
mut["gene_mutation_count"] = 0  # Set to 0 instead of mapping
joblib.dump(gene_freq_dict, ENC / "gene_freq.pkl")
print(f"         [4a] Mutation Frequency (gene_mutation_count): DISABLED (ablation)")

# 4b. Mutation Type Importance score (GUIDE FEATURE 2)
# Guide: Nonsense/Frameshift=High(3), Missense=Moderate(2),
#        Silent=Low(1), Intronic=None(0)
mut["effect_impact"] = (mut["effect"].map(EFFECT_IMPACT)
                        .fillna(1).astype(int))
joblib.dump(EFFECT_IMPACT, ENC / "effect_impact.pkl")
print(f"         [4b] Mutation Type Importance (effect_impact):")
print(f"              High(3): {(mut['effect_impact']==3).sum():,}  "
      f"Moderate(2): {(mut['effect_impact']==2).sum():,}  "
      f"Low(1): {(mut['effect_impact']==1).sum():,}  "
      f"None(0): {(mut['effect_impact']==0).sum():,}")

# 4c. AA Position — ABLATION TEST 2 DISABLED
# FIX: This is what allows the model to distinguish EGFR L858R from
#      other EGFR missense mutations. Without this, all EGFR missense
#      mutations have identical feature vectors -> model cannot tell
#      L858R (driver) from A123V (passenger)
mut["aa_position"] = mut["protein_mutation"].apply(extract_aa_position)
# ABLATION TEST 2 - Disable AA position normalization
mut["aa_position_norm"] = 0  # Set to 0 instead of normalizing
print(f"         [4c] AA Position (aa_position_norm): DISABLED (ablation)")

# 4d. Is Known Hotspot binary flag — ABLATION TEST DISABLED
# Originally designed to give model biological prior knowledge
# Comment out this section to test if model memorizes hotspots
# or learns real biological patterns
# 
# mut["is_known_hotspot"] = mut.apply(
#     lambda r: is_hotspot(r["gene_symbol"], r["aa_position"]),
#     axis=1
# ).astype(int)
joblib.dump(HOTSPOT_POSITIONS, ENC / "hotspot_positions.pkl")
# 
# Instead, create a dummy column set to 0
mut["is_known_hotspot"] = 0  # Disabled for ablation study

print(f"         [4d] Known Hotspot feature: DISABLED (ablation study)")

# 4e. VAF features
# High VAF (>=0.4) = clonal/early mutation = more likely driver
# Low VAF  (<=0.1) = subclonal/late mutation = more likely passenger
mut["vaf_high"] = (mut["vaf"] >= 0.4).astype(int)
mut["vaf_low"]  = (mut["vaf"] <= 0.1).astype(int)

# 4f. Position bin — simple integer bucketing
# Divide 0–250M genomic positions into 10 equal buckets
mut["position_bin"] = (mut["position"] // 25_000_000).clip(0, 9).astype(int)

print(f"         Feature engineering time: {time.time()-t0:.1f}s")


# ═════════════════════════════════════════════════════════════════════════════
# BUILD FINAL FEATURE MATRIX
# ═════════════════════════════════════════════════════════════════════════════
print()
print("[5] Building final feature matrix ...")

BASE_FEATURES = [
    # Guide Step 3 — Label Encoded
    "gene_enc",

    # Guide Step 4 Feature 2 — Mutation Type Importance
    "effect_impact",

    # Location features
    "chromosome",
    "position_bin",

    # Allele frequency features
    "vaf",
    "vaf_high",
    "vaf_low",

    # Coding region
    "coding",

    # Clinical significance
    "cancer_predisposition_variant",

    # ABLATION TEST 2 — Disabled to test if model memorizes gene frequency
    # "gene_mutation_count",

    # ABLATION TEST 2 — Disabled to test if model memorizes AA position
    # "aa_position_norm",

    # ABLATION TEST 1 — Disabled to test if model memorizes hotspots
    # "is_known_hotspot",
]

# All features = base features + One Hot Encoded effect columns (Guide Step 3)
FEATURE_COLS = BASE_FEATURES + ohe_cols   # 12 base + 15 OHE = 27 total

X = mut[FEATURE_COLS].copy()
y = mut["LABEL"].values

# Final null check
null_count = X.isnull().sum().sum()
assert null_count == 0, f"Null values found: {null_count}"

print(f"         Feature matrix X  : {X.shape}")
print(f"         Labels y          : {y.shape}")
print(f"         Total features    : {len(FEATURE_COLS)}")
print(f"           Base features   : {len(BASE_FEATURES)}")
print(f"           OHE features    : {len(ohe_cols)}")
print(f"         Driver rate       : {y.mean():.4%}")
print(f"         Null values       : {null_count}")

# Save all artefacts needed for inference
joblib.dump(FEATURE_COLS,    ENC / "feature_cols.pkl")
joblib.dump(BASE_FEATURES,   ENC / "base_feature_cols.pkl")
joblib.dump(ohe_cols,        ENC / "ohe_cols.pkl")
joblib.dump(simplify_effect, ENC / "simplify_effect_fn.pkl")


# ═════════════════════════════════════════════════════════════════════════════
# SAVE PROCESSED DATA
# ═════════════════════════════════════════════════════════════════════════════
print()
print("[6] Saving processed data ...")
t0 = time.time()

features_df = X.copy()
features_df["LABEL"]            = y
features_df["gene_symbol"]      = mut["gene_symbol"].values
features_df["effect"]           = mut["effect"].values
features_df["protein_mutation"] = mut["protein_mutation"].values
features_df["model_name"]       = mut["model_name"].values
features_df["chromosome"]       = mut["chromosome"].values
features_df["position"]         = mut["position"].values

features_df.to_csv(PROC / "mutation_features.csv", index=False)

# Save gene encoding reference for documentation
pd.DataFrame({
    "gene":    le_gene.classes_,
    "encoded": range(len(le_gene.classes_))
}).to_csv(PROC / "gene_encoding_reference.csv", index=False)

print(f"         o mutation_features.csv     : {features_df.shape}")
print(f"         o gene_encoding_reference.csv")
print(f"         o le_gene.pkl")
print(f"         o ohe_effect.pkl")
print(f"         o effect_categories.pkl")
print(f"         o feature_cols.pkl         : {len(FEATURE_COLS)} features")
print(f"         o gene_freq.pkl")
print(f"         o effect_impact.pkl")
print(f"         o hotspot_positions.pkl")
print(f"         Time: {time.time()-t0:.1f}s")


# ═════════════════════════════════════════════════════════════════════════════
# EDA FIGURES
# ═════════════════════════════════════════════════════════════════════════════
print()
print("[7] Generating EDA figures ...")

# (A) Mutation type distribution
fig, ax = plt.subplots(figsize=(12, 5))
ec = mut["effect"].value_counts()
ax.barh(ec.index, ec.values, color="#0B1E3D", alpha=0.85)
ax.set_xlabel("Count")
ax.set_title("Mutation Type Distribution (Lung Cancer Genes)",
             fontweight="bold")
ax.invert_yaxis()
plt.tight_layout()
plt.savefig(FIGS / "mutation_type_distribution.png", dpi=150)
plt.close()
print("         o mutation_type_distribution.png")

# (B) Driver rate by mutation type
dr_effect = (mut.groupby("effect")["LABEL"]
             .mean().sort_values(ascending=False))
fig, ax = plt.subplots(figsize=(12, 5))
bar_colors = ["#E11D48" if v > 0.01 else "#94A3B8"
              for v in dr_effect.values]
dr_effect.plot(kind="barh", ax=ax, color=bar_colors)
ax.set_xlabel("Driver Rate")
ax.set_title("Driver Rate by Mutation Type\n"
             "(High=Nonsense/Frameshift  Moderate=Missense  "
             "Low=Silent  None=Intronic)",
             fontweight="bold")
ax.invert_yaxis()
plt.tight_layout()
plt.savefig(FIGS / "driver_rate_by_mutation_type.png", dpi=150)
plt.close()
print("         o driver_rate_by_mutation_type.png")

# (C) Gene mutation frequency (Guide Feature 1)
fig, ax = plt.subplots(figsize=(12, 5))
gf = gene_freq.sort_values("gene_mutation_count", ascending=False)
ax.barh(gf["gene_symbol"], gf["gene_mutation_count"], color="#F59E0B")
ax.set_xlabel("Mutation Count")
ax.set_title("Gene Mutation Frequency  (Feature: gene_mutation_count)",
             fontweight="bold")
ax.invert_yaxis()
plt.tight_layout()
plt.savefig(FIGS / "gene_mutation_frequency.png", dpi=150)
plt.close()
print("         o gene_mutation_frequency.png")

# (D) Driver mutation count per gene
tdg = mut[mut["LABEL"] == 1]["gene_symbol"].value_counts()
fig, ax = plt.subplots(figsize=(12, 5))
ax.barh(tdg.index, tdg.values, color="#0D9488")
ax.set_xlabel("Driver Mutation Count")
ax.set_title("Driver Mutation Count per Gene", fontweight="bold")
ax.invert_yaxis()
plt.tight_layout()
plt.savefig(FIGS / "top_driver_genes.png", dpi=150)
plt.close()
print("         o top_driver_genes.png")

# (E) VAF distribution — driver vs passenger
fig, ax = plt.subplots(figsize=(10, 4))
mut[mut["LABEL"] == 1]["vaf"].hist(bins=40, ax=ax, alpha=0.75,
                                    color="#E11D48", label="Driver")
mut[mut["LABEL"] == 0]["vaf"].hist(bins=40, ax=ax, alpha=0.45,
                                    color="#0D9488", label="Passenger")
ax.set_xlabel("VAF (Variant Allele Frequency)")
ax.set_ylabel("Count")
ax.set_title("VAF Distribution: Driver vs Passenger", fontweight="bold")
ax.legend()
plt.tight_layout()
plt.savefig(FIGS / "vaf_driver_vs_passenger.png", dpi=150)
plt.close()
print("         o vaf_driver_vs_passenger.png")

# (F) Hotspot vs non-hotspot driver rate
hotspot_dr = mut.groupby("is_known_hotspot")["LABEL"].mean()
fig, ax = plt.subplots(figsize=(6, 4))
ax.bar(["Non-hotspot (0)", "Known hotspot (1)"],
       hotspot_dr.values,
       color=["#94A3B8", "#E11D48"], alpha=0.87)
ax.set_ylabel("Driver Rate")
ax.set_title("Driver Rate: Known Hotspot vs Non-Hotspot Positions",
             fontweight="bold")
plt.tight_layout()
plt.savefig(FIGS / "hotspot_driver_rate.png", dpi=150)
plt.close()
print("         o hotspot_driver_rate.png")

print()
print("=" * 65)
print(f"  Total time : {time.time()-t_total:.1f}s")
print(f"  Features   : {len(FEATURE_COLS)} "
      f"({len(BASE_FEATURES)} base + {len(ohe_cols)} OHE)")
print(f"  Samples    : {len(features_df):,}")
print(f"  Drivers    : {y.sum():,} ({y.mean():.4%})")
print("  Next step  -> python step3_train.py")
print("=" * 65)