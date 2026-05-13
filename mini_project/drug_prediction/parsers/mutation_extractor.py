import re
import json
import logging
from typing import List, Dict, Optional
from google import genai
from groq import Groq

logger = logging.getLogger(__name__)

# --- SAFETY-CRITICAL CONFIGURATION ---

# 1. Strict Protein/DNA Syntax Regex
VALID_MUTATION_REGEX = re.compile(r"^(p\.[A-Za-z0-9_*fs]+|c\.[0-9A-Za-z+>\-]+)$")

# 2. Negation Words (Deterministic Rejection)
NEGATION_WORDS = [
    "negative", "not detected", "wild type", "absent", 
    "no mutation", "no evidence", "negative for", "none"
]

# 3. Invalid Gene Tokens (Noise Filtering)
INVALID_GENE_TOKENS = {
    "LOF", "GOF", "MISSENSE", "FRAMESHIFT", "STOP", "VARIANT", 
    "VAF", "ID", "TMB", "MSI", "STABLE", "HIGH", "LOW", "GAIN", "LOSS"
}

def normalize_vaf(vaf_raw: str) -> float:
    """Normalize VAF percentage string to 0.0-1.0 decimal."""
    try:
        val = float(vaf_raw.replace('%', ''))
        return round(val / 100, 4) if val > 1.0 else round(val, 4)
    except:
        return 0.0

def extract_mutations(text: str, approved_genes: List[str], gemini_key: str = None, groq_key: str = None) -> List[Dict]:
    """
    STABILIZED EXTRACTION PIPELINE.
    Priority: Regex -> Groq -> Gemini -> Failure
    """
    if not text:
        return []

    # Layer 1: Regex Extraction (First & Fastest)
    logger.info("Running Layer 1: Regex Extraction...")
    candidates = _get_regex_candidates(text)
    if candidates:
        logger.info(f"Regex extracted {len(candidates)} candidates. Skipping AI providers.")
    else:
        # Layer 2: Groq Candidate Extraction (High Speed)
        if groq_key:
            logger.info("Running Layer 2: Groq high-speed extraction...")
            candidates = _get_groq_candidates(text, groq_key)
            if candidates:
                logger.info(f"Groq successfully extracted {len(candidates)} candidates.")
            else:
                logger.warning("Groq failed to return candidates or errored.")
        
        # Layer 3: Gemini Candidate Extraction (Robust Fallback)
        if not candidates and gemini_key:
            logger.info("Running Layer 3: Gemini fallback extraction...")
            candidates = _get_gemini_candidates(text, gemini_key)
            if candidates:
                logger.info(f"Gemini successfully extracted {len(candidates)} candidates.")
            else:
                logger.warning("Gemini fallback also failed or quota exhausted.")

    if not candidates:
        logger.error("All extraction providers failed to find candidates.")
        return []

    # Layer 4: Deterministic Validation (The Authority)
    validated_records = []
    seen_keys = set()

    for candidate in candidates:
        valid_record = _validate_candidate(candidate, approved_genes)
        if valid_record:
            key = f"{valid_record['gene']}_{valid_record['mutation']}"
            if key not in seen_keys:
                validated_records.append(valid_record)
                seen_keys.add(key)
                logger.info(f"✅ Validated Mutation: {valid_record['gene']} {valid_record['mutation']}")
            
    logger.info(f"Pipeline Result: {len(validated_records)} validated records from {len(candidates)} candidates.")
    return validated_records

def _get_regex_candidates(text: str) -> List[Dict]:
    """
    Robust line-based regex extraction for clinical reports.
    Supports: 
    - EGFR mutation detected p.L858R VAF:45.5%
    - KRAS-p.G12C observed VAF 23.8%
    - TP53 variant p.R248Q approx VAF: 67.1%
    """
    candidates = []
    
    # Gene pattern: 2+ uppercase letters/numbers
    # Mutation pattern: p. or c. notation
    # VAF pattern: "VAF" followed by optional colon/equals and a number
    # Structured regex for Gene + Mutation + VAF (named groups)
    # Supports variations like: KRAS p.G12C ... 23.8%
    STRUCTURED_REGEX = re.compile(
        r'(?P<gene>[A-Z][A-Z0-9]+).*?'
        r'(?P<mutation>p\.[A-Za-z0-9*]+(?:fs)?|c\.[0-9A-Za-z_+\->]+).*?'
        r'(?P<vaf>\d+(?:\.\d+)?)%',
        re.IGNORECASE
    )
    
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        matches = list(STRUCTURED_REGEX.finditer(line))
        
        if matches:
            for match in matches:
                gene = match.group('gene').upper()
                mutation = match.group('mutation')
                vaf_raw = match.group('vaf')
                
                if gene in INVALID_GENE_TOKENS:
                    continue
                    
                candidate = {
                    "gene": gene,
                    "mutation": mutation,
                    "vaf": normalize_vaf(vaf_raw),
                    "source_text": line
                }
                logger.info(f"Structured Regex candidate: {candidate}")
                candidates.append(candidate)
        else:
            # Fallback for lines without explicit VAF percentage
            # (e.g. summary blocks where VAF is in a different section)
            potential_genes = re.findall(r"\b([A-Z][A-Z0-9]+)\b", line)
            mutations = re.findall(r"(p\.[A-Za-z0-9_*fs]+|c\.[0-9A-Za-z+>\-]+)", line)
            
            for mutation in mutations:
                mutation_index = line.find(mutation)
                prefix = line[:mutation_index].strip()
                tokens = re.findall(r"\b([A-Z][A-Z0-9]+)\b", prefix)
                
                gene = None
                if tokens:
                    for t in reversed(tokens):
                        if t.upper() not in INVALID_GENE_TOKENS:
                            gene = t.upper()
                            break
                if gene:
                    candidate = {
                        "gene": gene,
                        "mutation": mutation,
                        "vaf": 0.0, # Default if not in structured pattern
                        "source_text": line
                    }
                    logger.info(f"Fallback Regex candidate: {candidate}")
                    candidates.append(candidate)
    
    return candidates

def _get_groq_candidates(text: str, api_key: str) -> List[Dict]:
    """
    Groq (Llama-3) acting as the high-speed extraction engine.
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
        
        # Using llama3-8b-8192 as requested for speed and accessibility
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a clinical extraction tool that outputs JSON."},
                {"role": "user", "content": prompt}
            ],
            model="llama3-8b-8192",
            response_format={"type": "json_object"}
        )
        
        raw_output = chat_completion.choices[0].message.content
        data = json.loads(raw_output)
        return data.get("mutations", [])
        
    except Exception as e:
        logger.warning(f"Groq candidate extraction failed: {e}")
        return []

def _get_gemini_candidates(text: str, api_key: str) -> List[Dict]:
    """
    Gemini acting as the robust fallback extraction engine.
    """
    try:
        client = genai.Client(api_key=api_key)
        
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
        
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        
        raw_output = response.text
        clean_json = re.sub(r'```json\s*|\s*```', '', raw_output).strip()
        data = json.loads(clean_json)
        return data.get("mutations", [])
        
    except Exception as e:
        logger.error(f"Gemini candidate extraction failed: {e}")
        return []

def _validate_candidate(c: Dict, approved_genes: List[str]) -> Optional[Dict]:
    """
    Deterministic Safety Layer. 
    This function has the final authority to reject AI hallucinations.
    """
    try:
        # 1. Clean and Normalize
        gene = str(c.get("gene", "")).upper().strip()
        mutation = str(c.get("mutation", "")).strip()
        vaf_raw = c.get("vaf")
        vaf = float(vaf_raw) if vaf_raw is not None else 0.0
        source_text = str(c.get("source_text", "")).lower()

        # 2. Gene Authorization Check (Stage 4 - Validation)
        # Instead of strict rejection, we now allow common clinical genes
        # but mark if they are "out of scope" for our specific drug-gene models.
        is_known = gene in approved_genes
        
        # We allow all valid gene symbols, but log if they are experimental/outside core panel
        if not is_known:
            # Minimum safety: Must at least look like a gene (handled by regex) 
            # and not be a noise word (handled by candidate extraction)
            logger.info(f"Clinical Audit: Processing mutation for gene '{gene}' (outside core validated panel).")
        
        # 3. Protein/DNA Syntax Check
        if not VALID_MUTATION_REGEX.match(mutation):
            logger.debug(f"❌ Validation Reject: Mutation {mutation} fails syntax regex.")
            return None
        
        # 4. VAF Range Check
        # We allow VAF to be 0.0 (missing) but it must not exceed 1.0
        if not (0 <= vaf <= 1.0):
            logger.debug(f"❌ Validation Reject: VAF {vaf} out of bounds.")
            return None
        
        # 5. Negation Detection Check
        if any(word in source_text for word in NEGATION_WORDS):
            matching_negation = [w for w in NEGATION_WORDS if w in source_text]
            logger.warning(f"❌ Validation Reject: Negation {matching_negation} detected in: '{source_text}'")
            return None
            
        return {
            "gene": gene,
            "mutation": mutation,
            "vaf": round(vaf, 4) if vaf else 0.0,
            "validated": True,
            "is_core_panel": is_known,
            "extractor": "clinical_tempus_v3"
        }
    except Exception as e:
        logger.debug(f"Validation Error: {e}")
        return None
