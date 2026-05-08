import re
import os
import json
import logging
from typing import List, Dict
import google.generativeai as genai

logger = logging.getLogger(__name__)

# Common Gene Symbols regex (standard HUGO symbols)
GENE_REGEX = r'\b[A-Z][A-Z0-9]{1,10}\b'

# VAF patterns: 45%, 0.45, VAF: 45, etc.
VAF_REGEX = r'(\d+(\.\d+)?)\s*%'

def extract_mutations(text: str, available_genes: List[str] = None, api_key: str = None) -> List[Dict]:
    """
    Extracts mutations and VAFs from text using deterministic regex + AI cleanup.
    
    Args:
        text: Raw text from genomic report.
        available_genes: List of genes to look for (whitelist).
        api_key: Gemini API key for advanced extraction.
        
    Returns:
        List of dicts: [{"gene": "EGFR", "vaf": 0.45}, ...]
    """
    # 1. Deterministic Regex Extraction
    mutations = _regex_extract(text, available_genes)
    
    # 2. AI-Enhanced Cleanup (if key provided and text is large)
    if api_key and text.strip():
        try:
            ai_mutations = _ai_extract(text, api_key)
            # Merge results: AI is usually better at mapping VAF to Gene in messy text
            if ai_mutations:
                return ai_mutations
        except Exception as e:
            logger.error(f"AI extraction failed: {e}")
    
    return mutations

def _regex_extract(text: str, available_genes: List[str]) -> List[Dict]:
    """Simple regex based extraction for fallback."""
    found = []
    text_upper = text.upper()
    
    if not available_genes:
        return []

    for gene in available_genes:
        gene_upper = gene.upper()
        # Look for gene name
        if gene_upper in text_upper:
            # Look for percentage near the gene name (within 50 chars)
            pos = text_upper.find(gene_upper)
            context = text_upper[pos:pos+100]
            vaf_match = re.search(VAF_REGEX, context)
            
            vaf = 0.5 # Default
            if vaf_match:
                try:
                    val = float(vaf_match.group(1))
                    vaf = val / 100.0 if val > 1.0 else val
                except:
                    pass
            
            found.append({"gene": gene_upper, "vaf": round(vaf, 3)})
            
    return found

def _ai_extract(text: str, api_key: str) -> List[Dict]:
    """Uses Gemini to extract structured mutation data from raw text."""
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")
    
    prompt = f"""
    Extract genomic mutations and their Variant Allele Frequency (VAF) from the following text.
    Return ONLY a JSON object with a "mutations" key containing a list of objects with "gene" and "vaf" keys.
    VAF should be a float between 0.0 and 1.0. If VAF is given as percentage (e.g. 45%), convert to 0.45.
    If VAF is not found, use 0.5 as default.
    
    Text:
    {text[:4000]}  # Limit text to avoid prompt limits
    
    JSON format:
    {{
      "mutations": [
        {{"gene": "EGFR", "vaf": 0.45}},
        {{"gene": "TP53", "vaf": 0.20}}
      ]
    }}
    """
    
    response = model.generate_content(prompt)
    response_text = response.text
    
    # Clean up markdown code blocks if present
    response_text = re.sub(r'```json\s*|\s*```', '', response_text).strip()
    
    try:
        data = json.loads(response_text)
        return data.get("mutations", [])
    except Exception as e:
        logger.error(f"Failed to parse AI response: {e}")
        return []
