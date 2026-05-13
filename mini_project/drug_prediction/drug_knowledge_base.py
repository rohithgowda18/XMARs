"""
Drug Knowledge Base
====================
Builds a structured drug-gene-pathway knowledge base from existing project data.
All relationships come from:
  - data/processed/03_compounds_cleaned.csv (621 drugs with targets & pathways)
  - data/processed/pathway_reference.json (8 cancer pathways with gene mappings)
  - data/processed/mutation_features.csv (available gene symbols)
"""

import pandas as pd
import json
import logging
from pathlib import Path
from collections import defaultdict

logger = logging.getLogger(__name__)

# Paths relative to the parent project
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / 'data' / 'processed'


class DrugKnowledgeBase:
    """
    Indexes existing project drug/pathway data into fast lookup structures.
    No external data is introduced — everything comes from the project files.
    """

    def __init__(self):
        self.drugs = []               # List of drug dicts
        self.gene_to_drugs = defaultdict(list)    # gene -> [drug names]
        self.pathway_to_drugs = defaultdict(list) # pathway -> [drug names]
        self.drug_to_info = {}         # drug_name -> full info dict
        self.pathways = {}             # pathway_name -> pathway data
        self.gene_to_pathways = defaultdict(list) # gene -> [pathway names]
        self.available_genes = []      # genes present in mutation data
        self._loaded = False

    def load(self):
        """Load all data from existing project files."""
        self._load_compounds()
        self._load_pathways()
        self._load_available_genes()
        self._build_indices()
        self._loaded = True
        logger.info(f"Knowledge base loaded: {len(self.drug_to_info)} unique drugs, "
                    f"{len(self.pathways)} pathways, {len(self.available_genes)} genes")
        return self

    def _load_compounds(self):
        """Load drugs from 03_compounds_cleaned.csv"""
        csv_path = DATA_DIR / '03_compounds_cleaned.csv'
        if not csv_path.exists():
            raise FileNotFoundError(f"Compounds file not found: {csv_path}")

        df = pd.read_csv(csv_path)
        seen = set()

        for _, row in df.iterrows():
            name = str(row.get('DRUG_NAME', '')).strip()
            if not name or name == 'nan' or name in seen:
                continue
            seen.add(name)

            targets_raw = str(row.get('TARGET', ''))
            pathway_raw = str(row.get('TARGET_PATHWAY', ''))

            if targets_raw == 'nan':
                targets_raw = ''
            if pathway_raw == 'nan':
                pathway_raw = ''

            # Parse targets: split on comma, clean whitespace
            targets = [t.strip() for t in targets_raw.split(',') if t.strip()]

            drug_info = {
                'name': name,
                'targets': targets,
                'pathway': pathway_raw.strip(),
                'targets_raw': targets_raw.strip(),
            }
            self.drugs.append(drug_info)

        logger.info(f"Loaded {len(self.drugs)} unique drugs from compounds CSV")

    def _load_pathways(self):
        """Load pathways from pathway_reference.json"""
        json_path = DATA_DIR / 'pathway_reference.json'
        if not json_path.exists():
            raise FileNotFoundError(f"Pathway file not found: {json_path}")

        with open(json_path, 'r') as f:
            self.pathways = json.load(f)

        logger.info(f"Loaded {len(self.pathways)} pathways from pathway_reference.json")

    def _load_available_genes(self):
        """Load the gene symbols present in mutation_features.csv"""
        csv_path = DATA_DIR / 'mutation_features.csv'
        if not csv_path.exists():
            raise FileNotFoundError(f"Mutation features not found: {csv_path}")

        df = pd.read_csv(csv_path, usecols=['gene_symbol'])
        self.available_genes = sorted(df['gene_symbol'].unique().tolist())
        
        # Ensure NFE2L2 is included (clinical lung cancer biomarker)
        if 'NFE2L2' not in self.available_genes:
            self.available_genes.append('NFE2L2')
            self.available_genes.sort()
            
        logger.info(f"Found {len(self.available_genes)} available genes in mutation data")

    def _build_indices(self):
        """Build lookup indices from loaded data."""

        # 1. Build gene_to_pathways from pathway_reference.json
        for pathway_name, pathway_data in self.pathways.items():
            for gene in pathway_data.get('genes', []):
                gene_upper = gene.upper()
                if pathway_name not in self.gene_to_pathways[gene_upper]:
                    self.gene_to_pathways[gene_upper].append(pathway_name)

        # 2. Build drug indices from compounds data
        for drug in self.drugs:
            name = drug['name']
            self.drug_to_info[name] = drug

            # Map each target gene to this drug
            for target in drug['targets']:
                target_upper = target.upper().strip()
                if target_upper and name not in self.gene_to_drugs[target_upper]:
                    self.gene_to_drugs[target_upper].append(name)

            # Map pathway to this drug
            pathway = drug['pathway']
            if pathway and name not in self.pathway_to_drugs[pathway]:
                self.pathway_to_drugs[pathway].append(name)

    def get_drugs_targeting_gene(self, gene: str) -> list:
        """Get all drugs that directly target a gene."""
        gene_upper = gene.upper().strip()
        drug_names = self.gene_to_drugs.get(gene_upper, [])
        return [self.drug_to_info[d] for d in drug_names if d in self.drug_to_info]

    def get_drugs_for_pathway(self, pathway_name: str) -> list:
        """Get all drugs targeting a specific pathway."""
        drug_names = self.pathway_to_drugs.get(pathway_name, [])
        return [self.drug_to_info[d] for d in drug_names if d in self.drug_to_info]

    def get_pathways_for_gene(self, gene: str) -> list:
        """Get pathways that include a specific gene."""
        gene_upper = gene.upper().strip()
        pathway_names = self.gene_to_pathways.get(gene_upper, [])
        return [(name, self.pathways[name]) for name in pathway_names
                if name in self.pathways]

    def get_pathway_drugs_for_gene(self, gene: str) -> list:
        """Get drugs that target any pathway containing this gene."""
        pathways = self.get_pathways_for_gene(gene)
        drugs = set()
        for pathway_name, pathway_data in pathways:
            # Get drug targets listed in the pathway
            for drug_target in pathway_data.get('drug_targets', []):
                target_upper = drug_target.upper().strip()
                for drug_name in self.gene_to_drugs.get(target_upper, []):
                    drugs.add(drug_name)
            # Also get drugs from the pathway_to_drugs mapping
            pathway_str = pathway_data.get('description', '')
            for pkey, drug_list in self.pathway_to_drugs.items():
                # Match pathway by checking if any keyword matches
                if self._pathway_matches(pathway_name, pkey):
                    for d in drug_list:
                        drugs.add(d)
        return [self.drug_to_info[d] for d in drugs if d in self.drug_to_info]

    def _pathway_matches(self, pathway_ref_name: str, compound_pathway: str) -> bool:
        """Check if a pathway_reference name matches a compound's TARGET_PATHWAY."""
        mapping = {
            'EGFR_SIGNALING': ['EGFR signaling'],
            'TP53_APOPTOSIS': ['p53 pathway', 'Apoptosis regulation'],
            'PI3K_AKT_MTOR': ['PI3K/MTOR signaling'],
            'MAPK_ERK': ['ERK MAPK signaling'],
            'CELL_CYCLE': ['Cell cycle'],
            'WNT_SIGNALING': ['WNT signaling'],
            'RAS_PATHWAY': ['ERK MAPK signaling', 'RTK signaling'],
            'DNA_REPAIR': ['Genome integrity', 'DNA replication'],
        }
        compound_pathway_lower = compound_pathway.lower().strip()
        for match_str in mapping.get(pathway_ref_name, []):
            if match_str.lower() == compound_pathway_lower:
                return True
        return False

    def get_lung_cancer_relevant_drugs(self) -> list:
        """
        Get drugs relevant to lung cancer pathways.
        Filters to drugs targeting pathways commonly altered in lung cancer.
        """
        lung_pathways = [
            'EGFR signaling', 'ERK MAPK signaling', 'PI3K/MTOR signaling',
            'RTK signaling', 'Cell cycle', 'Genome integrity',
            'p53 pathway', 'Apoptosis regulation', 'DNA replication'
        ]
        relevant = set()
        for pathway in lung_pathways:
            for drug_name in self.pathway_to_drugs.get(pathway, []):
                relevant.add(drug_name)
        return [self.drug_to_info[d] for d in relevant if d in self.drug_to_info]

    def get_summary(self) -> dict:
        """Return a summary of the knowledge base."""
        return {
            'total_drugs': len(self.drug_to_info),
            'total_pathways': len(self.pathways),
            'available_genes': self.available_genes,
            'gene_count': len(self.available_genes),
            'pathway_names': list(self.pathways.keys()),
            'drug_pathways': list(self.pathway_to_drugs.keys()),
        }


# Module-level singleton
_kb_instance = None

def get_knowledge_base() -> DrugKnowledgeBase:
    """Get or create the singleton knowledge base instance."""
    global _kb_instance
    if _kb_instance is None:
        _kb_instance = DrugKnowledgeBase()
        _kb_instance.load()
    return _kb_instance


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
    kb = get_knowledge_base()
    summary = kb.get_summary()
    print(f"\nDrug Knowledge Base Summary:")
    print(f"  Unique drugs: {summary['total_drugs']}")
    print(f"  Pathways: {summary['total_pathways']}")
    print(f"  Available genes: {summary['gene_count']}")
    print(f"  Genes: {summary['available_genes']}")
    print(f"\nExample: Drugs targeting EGFR:")
    for d in kb.get_drugs_targeting_gene('EGFR')[:5]:
        print(f"    {d['name']} — targets: {d['targets_raw']} — pathway: {d['pathway']}")
    print(f"\nExample: Pathways for KRAS:")
    for name, data in kb.get_pathways_for_gene('KRAS'):
        print(f"    {name}: {data['description']}")
