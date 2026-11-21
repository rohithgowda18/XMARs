"""
STEP 1 — DOWNLOAD GDSC DATASETS
================================
Auto-downloads 5 files from Sanger GDSC release 8.5.
mutations_all.xlsx and cnv.xlsx are placed manually (require CMP login).

Manual files needed in data/raw/:
  mutations_all.xlsx  ← renamed from mutations_all_YYYYMMDD.xlsx
  cnv.xlsx            ← renamed from cnv_summary_YYYYMMDD.xlsx

Run:
    python step1_download_data.py
"""

import gzip
import shutil
import zipfile
import requests
from pathlib import Path

RAW = Path("data/raw")
RAW.mkdir(parents=True, exist_ok=True)

GDSC_BASE = "https://cog.sanger.ac.uk/cancerrxgene/GDSC_release8.5"
CMP_BASE  = "https://cog.sanger.ac.uk/cmp/download"


# ─── Auto-downloaded files ─────────────────────────────────────────────────────
DATASETS = {

    # GDSC2 drug sensitivity data — contains IC50 values for 200+ drugs
    # across 1000+ cancer cell lines. Used as the PRIMARY drug response
    # dataset to create resistance labels (sensitive vs resistant) for training.
    "GDSC2_IC50.xlsx": (
        f"{GDSC_BASE}/GDSC2_fitted_dose_response_27Oct23.xlsx"
    ),

    # GDSC1 drug sensitivity data — older version of the screen with
    # different drug panel. Used as a SECONDARY/validation drug response
    # source when a drug is not present in GDSC2.
    "GDSC1_IC50.xlsx": (
        f"{GDSC_BASE}/GDSC1_fitted_dose_response_27Oct23.xlsx"
    ),

    # Cell line metadata — maps each cell line to its tissue type,
    # cancer type, and COSMIC ID. Used to filter lung cancer cell lines
    # and add tissue-type features to the model.
    "cell_line_details.xlsx": (
        f"{GDSC_BASE}/Cell_Lines_Details.xlsx"
    ),

    # Screened compounds list — contains drug names, targets, and
    # pathway information for all drugs in the GDSC screen.
    # Used to map drug names and filter lung-cancer-relevant drugs.
    "screened_compounds.xlsx": (
        f"{GDSC_BASE}/screened_compounds_rel_8.5.csv"
    ),

    # Model list from Cell Model Passports — links cell line names
    # to COSMIC IDs, tissue types, and cancer subtypes.
    # Used to cross-reference and merge mutation data with IC50 data.
    "model_list.csv.gz": (
        f"{CMP_BASE}/model_list_latest.csv.gz"
    ),
}


# ─── Manually placed files (require CMP login) ────────────────────────────────
MANUAL_FILES = {

    # All somatic mutations (WES) across all GDSC cell lines —
    # contains gene name, mutation type, chromosome, position, AA change.
    # This is the CORE input for the Mutation Agent feature matrix.
    # Download: https://cellmodelpassports.sanger.ac.uk/downloads
    #           → Mutations All (212 MB)  → rename to mutations_all.xlsx
    "mutations_all.xlsx": (
        "https://cellmodelpassports.sanger.ac.uk/downloads"
        "  →  Mutations All  (212 MB)"
    ),

    # Copy number variation summary for cancer driver genes —
    # contains total copy number and CNA category (gain/loss/neutral).
    # Used as supplementary features alongside mutation data in training.
    # Download: https://cellmodelpassports.sanger.ac.uk/downloads
    #           → CNV Summary (7.96 MB)  → rename to cnv.xlsx
    "cnv.xlsx": (
        "https://cellmodelpassports.sanger.ac.uk/downloads"
        "  →  CNV Summary  (7.96 MB)"
    ),
}


# ─── Helpers ──────────────────────────────────────────────────────────────────
def download_file(name: str, url: str, dest: Path) -> bool:
    """Download one file; auto-decompress .gz. Returns True on success."""
    final_name = name.replace(".gz", "")
    final_path = dest / final_name

    if final_path.exists():
        mb = final_path.stat().st_size / 1e6
        print(f"  [SKIP] {final_name:<45} {mb:>8.1f} MB  (already exists)")
        return True

    print(f"  [↓]  {name}")
    print(f"       {url}")

    try:
        r = requests.get(url, stream=True, timeout=180)
        r.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print(f"  [FAIL] HTTP error: {e}\n")
        return False
    except requests.exceptions.ConnectionError as e:
        print(f"  [FAIL] Connection error: {e}\n")
        return False
    except requests.exceptions.Timeout:
        print(f"  [FAIL] Request timed out\n")
        return False

    raw_path = dest / name
    with open(raw_path, "wb") as f:
        for chunk in r.iter_content(1024 * 256):
            f.write(chunk)

    # Auto-decompress .gz → plain file
    if name.endswith(".gz"):
        print(f"  [~]  Decompressing …")
        with gzip.open(raw_path, "rb") as fi, open(final_path, "wb") as fo:
            shutil.copyfileobj(fi, fo)
        raw_path.unlink()

    mb = (dest / final_name).stat().st_size / 1e6
    print(f"  [OK] {final_name:<45} {mb:>8.1f} MB\n")
    return True


def auto_unzip_raw(dest: Path):
    """
    Unzip any .zip files dropped in data/raw/ and rename to standard names.
    Useful if downloaded files arrive as zip archives.
    """
    RENAME_MAP = {
        "mutations_all": "mutations_all.xlsx",
        "cnv_summary":   "cnv.xlsx",
        "cnv":           "cnv.xlsx",
    }

    for zip_path in sorted(dest.glob("*.zip")):
        print(f"\n  [ZIP] Found: {zip_path.name} — extracting ...")
        with zipfile.ZipFile(zip_path, "r") as z:
            for member in z.namelist():
                if member.endswith((".csv", ".xlsx", ".xls")):
                    std_name = None
                    for keyword, target in RENAME_MAP.items():
                        if keyword in member.lower():
                            std_name = target
                            break
                    out_name = std_name or Path(member).name
                    out_path = dest / out_name

                    if out_path.exists():
                        print(f"  [SKIP] {out_name} already exists")
                        continue

                    print(f"  [~]  Extracting {member} → {out_name}")
                    with z.open(member) as src, open(out_path, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    mb = out_path.stat().st_size / 1e6
                    print(f"  [OK] {out_name}  ({mb:.1f} MB)")

        zip_path.unlink()
        print(f"  [~]  Deleted {zip_path.name}")


def check_manual_files(dest: Path) -> bool:
    """Check manually placed files exist and print guidance if missing."""
    print("── Manual files check ──────────────────────────────────────")
    all_present = True
    for fname, source in MANUAL_FILES.items():
        fpath = dest / fname
        if fpath.exists():
            mb = fpath.stat().st_size / 1e6
            print(f"  [OK]  {fname:<45} {mb:>8.1f} MB")
        else:
            print(f"  [MISSING]  {fname}")
            print(f"             Download from : {source}")
            print(f"             Rename to     : {fname}")
            print(f"             Place at      : {fpath.resolve()}")
            all_present = False
    return all_present


# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":

    print()
    print("=" * 65)
    print("  GDSC Data Download")
    print("=" * 65)
    print(f"  Saving to : {RAW.resolve()}")
    print(f"  Auto      : {len(DATASETS)} files")
    print(f"  Manual    : {len(MANUAL_FILES)} files")
    print()

    # Auto-extract any zip files already dropped in data/raw/
    auto_unzip_raw(RAW)

    # Download auto files
    print("── Auto-download (GDSC release 8.5) ────────────────────────")
    for name, url in DATASETS.items():
        download_file(name, url, RAW)

    # Check manually placed files
    print()
    all_manual_present = check_manual_files(RAW)

    # ── Summary ───────────────────────────────────────────────────
    print()
    print("=" * 65)
    print("  File Summary")
    print("=" * 65)
    total_mb = 0
    for f in sorted(RAW.iterdir()):
        mb = f.stat().st_size / 1e6
        total_mb += mb
        print(f"  ✓  {f.name:<48} {mb:>8.1f} MB")
    print(f"\n  Total: {total_mb:.1f} MB")
    print()

    if all_manual_present:
        print("  ✅ All files present.")
        print("  Next step → python step2_preprocess.py")
    else:
        print("  ⚠  Place missing files manually and re-run this script.")
        print("     step2_preprocess.py will still run with available files.")

    print("=" * 65)