import re
import json
import logging
import time
from typing import List, Dict, Optional
from google import genai
from groq import Groq

logger = logging.getLogger(__name__)

# --- SAFETY-CRITICAL CONFIGURATION ---

# 1. Strict Protein/DNA Syntax Regex
VALID_MUTATION_REGEX = re.compile(r"^(p\.[A-Za-z0-9_*fs]+|c\.[0-9A-Za-z+>\-]+|MET_exon14_skipping)$")

# 2. Negation Words (Deterministic Rejection)
NEGATION_WORDS = [
    "negative", "not detected", "wild type", "absent", 
    "no mutation", "no evidence", "negative for", "none"
]

# 3. Invalid Gene Tokens (Noise Filtering)
INVALID_GENE_TOKENS = {
    "VARIANT", "DETECTED", "OBSERVED", "APPROX", "NEGATIVE", "MUTATION", 
    "VAF", "LOSS", "GAIN", "AMPLIFICATION", "FUSION", "MISSENSE", 
    "FRAMESHIFT", "STABLE", "HIGH", "LOW", "LOF", "GOF", "STOP", "ID", "TMB", "MSI"
}

# 4. Section-Aware Classification (False Positive Prevention)
POSITIVE_SECTIONS = [
    "genomic variants", "somatic - potentially actionable", "somatic - biologically relevant",
    "pathogenic variants", "clinically significant variants", "actionable mutations",
    "somatic variants", "alterations", "genomic findings", "biologically relevant variants",
    "variants of unknown significance"
]

NEGATIVE_SECTIONS = [
    "pertinent negatives", "pertinent negative", "no pathogenic", "wild type",
    "negative for", "no alterations detected", "germline - pathogenic",
    "genes tested", "genes with no reportable", "not detected",
    "no clinically significant", "no actionable"
]

def _classify_section(line: str) -> Optional[str]:
    """Detect if a line is a section header and classify it."""
    line_lower = line.lower().strip()
    for neg in NEGATIVE_SECTIONS:
        if neg in line_lower:
            return "negative"
    for pos in POSITIVE_SECTIONS:
        if pos in line_lower:
            return "positive"
    return None

def normalize_vaf(vaf_raw: str) -> float:
    """Normalize VAF percentage string to 0.0-1.0 decimal."""
    try:
        val = float(vaf_raw.replace('%', ''))
        return round(val / 100, 4) if val > 1.0 else round(val, 4)
    except:
        return 0.0

def extract_mutations(text: str, approved_genes: List[str], gemini_key: str = None, groq_key: str = None, pdf_file=None) -> List[Dict]:
    """
    STABILIZED EXTRACTION PIPELINE.
    Priority: Regex -> Groq (Llama 3.1) -> Gemini Vision (Fallback) -> Failure
    """
    if not text and not pdf_file:
        return []

    candidates = []
    
    # Layer 1: Regex Extraction (First & Fastest)
    logger.info("Running Layer 1: Regex Extraction...")
    candidates = _get_regex_candidates(text, approved_genes)
    
    # Layer 2: Groq Candidate Extraction (High Speed Llama 3.1)
    if not candidates and groq_key:
        logger.info("Running Layer 2: Groq extraction (Llama 3.1)...")
        candidates = _get_groq_candidates(text, groq_key)
    
    # Layer 3: Gemini Vision Fallback (For Scanned/Messy PDFs)
    # Triggered if text is very short OR no mutations found after Layer 2
    if (not candidates or len(text.strip()) < 200) and gemini_key and pdf_file:
        logger.warning("Digital extraction weak or missing. Triggering Gemini Vision fallback.")
        vision_candidates = _get_vision_candidates(pdf_file, gemini_key, approved_genes)
        if vision_candidates:
            candidates.extend(vision_candidates)
            logger.info(f"Gemini Vision extracted {len(vision_candidates)} candidates via OCR-fallback.")
        else:
            # Layer 3.5: EasyOCR Backup (Local/Offline Fallback)
            logger.warning("Gemini Vision failed. Running EasyOCR backup.")
            try:
                from .easyocr_parser import extract_text_with_easyocr
                ocr_text = extract_text_with_easyocr(pdf_file)
                if ocr_text and len(ocr_text.strip()) > 50:
                    ocr_candidates = _get_regex_candidates(ocr_text, approved_genes)
                    if ocr_candidates:
                        for c in ocr_candidates:
                            c["extractor"] = "clinical_v4_easyocr_fallback"
                            c["confidence"] = 0.75
                        candidates.extend(ocr_candidates)
                        logger.info(f"EasyOCR successfully extracted {len(ocr_candidates)} candidates.")
                else:
                    logger.error("EasyOCR extraction failed to yield meaningful text.")
            except Exception as ocr_err:
                logger.error(f"EasyOCR integration error: {ocr_err}")

    if not candidates:
        logger.error("All extraction providers failed to find candidates.")
        return []

    # Layer 4: Deterministic Validation & Deduplication
    # Keep longer mutation if one is prefix of another (e.g. p.R331f vs p.R331fs)
    cleaned_candidates = []
    candidates.sort(key=lambda x: len(str(x.get('mutation', ''))), reverse=True)
    
    for c in candidates:
        is_sub = False
        gene = c.get('gene')
        mut = str(c.get('mutation', ''))
        for longer in cleaned_candidates:
            if longer['gene'] == gene and str(longer['mutation']).startswith(mut):
                is_sub = True
                break
        if not is_sub:
            cleaned_candidates.append(c)
            
    validated_records = []
    seen_keys = set()

    for candidate in cleaned_candidates:
        valid_record = _validate_candidate(candidate, approved_genes)
        if valid_record:
            key = f"{valid_record['gene']}_{valid_record['mutation']}"
            if key not in seen_keys:
                validated_records.append(valid_record)
                seen_keys.add(key)
                logger.info(f"✅ Validated Mutation: {valid_record['gene']} {valid_record['mutation']}")
            
    logger.info(f"Pipeline Result: {len(validated_records)} validated records from {len(candidates)} candidates.")
    return validated_records

def _get_regex_candidates(text: str, approved_genes: List[str]):
    candidates = []

    # ---------------------------------------------------------------
    # STRICT ROW-AWARE PATTERNS
    # Gene must appear on the SAME LINE, CLOSE to the mutation.
    # This prevents cross-row contamination from OCR table corruption.
    # ---------------------------------------------------------------

    # Pattern 1: Gene + protein/DNA mutation + VAF% (strict same-row)
    # e.g. "KRAS p.G12C Missense variant 23.8%"
    ROW_VAF_REGEX = re.compile(
        r'\b(?P<gene>[A-Z][A-Z0-9]{1,10})\b'    # gene symbol (2-11 chars, strictly uppercase)
        r'[^A-Z\n]{1,30}'                       # flexible separator: no uppercase letters, no newlines (max 30 chars proximity)
        r'(?P<mutation>[pP]\.[A-Za-z0-9_*>]+(?:[fF][sS])?(?:[dD][eE][lL][A-Za-z]*)?|[cC]\.[0-9A-Za-z+>\-]+)'  # mutation
        r'.*?'                                     # optional description
        r'(?P<vaf>\d+(?:\.\d+)?)%'                 # VAF percentage
    )

    # Pattern 2: Gene + protein/DNA mutation without VAF (strict same-row)
    # e.g. "PTCH1 E1439*" or "KRAS p.G12C"
    ROW_SIMPLE_REGEX = re.compile(
        r'\b(?P<gene>[A-Z][A-Z0-9]{1,10})\b'    # gene symbol
        r'[^A-Z\n]{1,30}'                       # flexible separator: no uppercase letters, no newlines
        r'(?P<mutation>[pP]\.[A-Za-z0-9_*>]+(?:[fF][sS])?(?:[dD][eE][lL][A-Za-z]*)?|[cC]\.[0-9A-Za-z+>\-]+|[A-Z]\d+[A-Z*](?:[fF][sS])?)\b'
    )

    # Pattern 3: Structural alterations (same-row)
    # e.g. "CD274 amplification", "MET exon 14 skipping"
    ROW_STRUCTURAL_REGEX = re.compile(
        r'\b(?P<gene>[A-Z][A-Z0-9]{1,10})\b'
        r'[^A-Z\n]{1,30}'
        r'(?P<type>(?i:amplification|loss|fusion|exon\s*14\s*skipping|exon\s*14\s*splice|splice\s*site))\b'
    )

    lines = text.split("\n")
    current_section = "positive"  # Default: assume positive until a header says otherwise

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Section-awareness: detect section headers
        section_type = _classify_section(line)
        if section_type:
            current_section = section_type
            logger.info(f"Section detected: '{line.strip()[:60]}' \u2192 {current_section}")
            continue

        # SKIP all lines inside negative sections
        if current_section == "negative":
            continue

        # 1. Structured mutation + VAF (strict same-row)
        for match in ROW_VAF_REGEX.finditer(line):
            gene = match.group("gene").upper()
            mutation = match.group("mutation")
            vaf = float(match.group("vaf")) / 100

            # Validate gene against approved list
            if gene not in approved_genes or gene in INVALID_GENE_TOKENS:
                continue

            candidates.append({
                "gene": gene,
                "mutation": mutation,
                "vaf": round(vaf, 4),
                "confidence": 0.95,
                "source_text": line,
                "source_section": current_section
            })

        # 2. Simple mutation without VAF (strict same-row)
        for match in ROW_SIMPLE_REGEX.finditer(line):
            gene = match.group("gene").upper()
            mutation = match.group("mutation")

            if gene not in approved_genes or gene in INVALID_GENE_TOKENS:
                continue

            mutation_str = f"p.{mutation}" if not mutation.startswith(("p.", "c.")) else mutation
            # Deduplicate against VAF-pattern matches
            exists = any(c["gene"] == gene and c["mutation"] == mutation_str for c in candidates)
            if not exists:
                candidates.append({
                    "gene": gene,
                    "mutation": mutation_str,
                    "vaf": 0.5,
                    "confidence": 0.60,
                    "source_text": line,
                    "source_section": current_section
                })

        # 3. Structural Alterations (strict same-row)
        for match in ROW_STRUCTURAL_REGEX.finditer(line):
            gene = match.group("gene").upper()
            alt_type = match.group("type").lower()

            if gene not in approved_genes or gene in INVALID_GENE_TOKENS:
                continue

            if "exon" in alt_type and ("14" in alt_type or "splice" in alt_type):
                mutation_str = "exon14_skipping"
            else:
                mutation_str = alt_type.replace(" ", "_")

            candidates.append({
                "gene": gene,
                "mutation": mutation_str,
                "vaf": None,
                "requires_manual_vaf": True,
                "confidence": 0.90,
                "source_text": line,
                "source_section": current_section
            })

    return candidates

def _get_groq_candidates(text: str, api_key: str) -> List[Dict]:
    """
    Groq (Llama 3.1) acting as the high-speed extraction engine.
    """
    try:
        client = Groq(api_key=api_key)
        
        prompt = f"""
        You are a clinical genomics extraction tool.
        Extract ONLY explicit mutation records from the pathology report text.

        RULES:
        - Extract: "gene" (HGNC symbol), "mutation" (protein syntax like p.G12C), and "vaf" (0-1).
        - Provide the exact "source_text" for audit.
        - NEVER guess a VAF if missing.
        - IGNORE negative results, tested gene lists, and disclaimers.
        - Return ONLY valid JSON.

        JSON SCHEMA:
        {{ "mutations": [ {{"gene": "KRAS", "mutation": "p.G12C", "vaf": 0.238, "source_text": "KRAS p.G12C VAF: 23.8%"}} ] }}

        REPORT TEXT:
        {text[:10000]}
        """
        
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a clinical extraction tool that outputs JSON."},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.1-8b-instant",
            response_format={"type": "json_object"}
        )
        
        raw_output = chat_completion.choices[0].message.content
        data = json.loads(raw_output)
        return data.get("mutations", [])
        
    except Exception as e:
        logger.warning(f"Groq candidate extraction failed: {e}")
        return []

def _get_vision_candidates(pdf_file, api_key: str, approved_genes: List[str]) -> List[Dict]:
    """
    Gemini Vision acting as a high-fidelity Genomic OCR engine.
    """
    try:
        from .pdf_parser import convert_pdf_to_images
        logger.info("Converting PDF pages to images for vision fallback")
        images = convert_pdf_to_images(pdf_file)
        if not images:
            return []

        client = genai.Client(api_key=api_key)
        # Safety Cooldown to prevent quota hits
        logger.info("Applying 5s safety cooldown for Gemini Vision...")
        time.sleep(5)
        
        prompt = """
        You are a clinical genomics extraction system.
        Visually read the report image and extract ALL clinically relevant genomic findings as clean structured plain text.

        STRICT RULES:
        1. Extract ONLY text actually visible.
        2. NEVER hallucinate genes, mutations, or VAF values.
        3. Preserve mutation syntax EXACTLY (e.g., p.G12C, p.R331fs).
        4. Preserve VAF percentages EXACTLY as written (e.g., 23.8%).
        5. Ignore non-medical noise (logos, footers).
        6. Return ONLY clean extracted plain text. ONE mutation per line.
        7. Do NOT generate JSON.

        FOCUS ON: Genomic Variants, Somatic Variants, Actionable Mutations, VAF, Fusions.
        """
        
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[prompt, *images]
        )
        
        vision_text = response.text
        logger.info(f"Gemini Vision OCR extracted {len(vision_text)} characters of text.")
        
        results = _get_regex_candidates(vision_text, approved_genes)
        
        for r in results:
            r["extractor"] = "clinical_v4_vision_ocr"
            r["confidence"] = 0.85
            
        return results
        
    except Exception as e:
        logger.error(f"Gemini Vision OCR fallback failed: {e}")
        return []

def _validate_candidate(c: Dict, approved_genes: List[str]) -> Optional[Dict]:
    """
    Deterministic Safety Layer. 
    """
    try:
        gene = str(c.get("gene", "")).upper().strip()
        mutation = str(c.get("mutation", "")).strip()
        vaf_raw = c.get("vaf")
        vaf = float(vaf_raw) if vaf_raw is not None else 0.0
        source_text = str(c.get("source_text", "")).lower()

        is_known = gene in approved_genes
        structural_types = ["amplification", "loss", "fusion", "exon14_skipping", "splice_site"]
        is_structural = mutation.lower() in structural_types
        
        if not is_structural and not VALID_MUTATION_REGEX.match(mutation):
            logger.debug(f"❌ Validation Reject: Mutation {mutation} fails syntax regex.")
            return None
        
        if vaf_raw is not None:
            if not (0 <= vaf <= 1.0):
                logger.debug(f"❌ Validation Reject: VAF {vaf} out of bounds.")
                return None
        
        if any(word in source_text for word in NEGATION_WORDS):
            matching_negation = [w for w in NEGATION_WORDS if w in source_text]
            logger.warning(f"❌ Validation Reject: Negation {matching_negation} detected in: '{source_text}'")
            return None
            
        return {
            "gene": gene,
            "mutation": mutation,
            "vaf": round(vaf, 4) if vaf_raw is not None else None,
            "requires_manual_vaf": c.get("requires_manual_vaf", False),
            "confidence": c.get("confidence", 0.50),
            "validated": True,
            "is_core_panel": is_known,
            "extractor": c.get("extractor", "clinical_v4_foundation_ready")
        }
    except Exception as e:
        logger.debug(f"Validation Error: {e}")
        return None
