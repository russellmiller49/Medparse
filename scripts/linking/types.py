# scripts/linking/types.py
"""Type definitions and constants for entity linking."""

# UMLS Semantic Types (TUIs) to keep
# These are clinically meaningful types we want to extract
VALID_TUIS = {
    # Disorders
    "T047",  # Disease or Syndrome
    "T191",  # Neoplastic Process
    "T048",  # Mental or Behavioral Dysfunction
    "T046",  # Pathologic Function
    "T184",  # Sign or Symptom
    
    # Chemicals & Drugs
    "T121",  # Pharmacologic Substance
    "T200",  # Clinical Drug
    "T195",  # Antibiotic
    "T123",  # Biologically Active Substance
    "T122",  # Biomedical or Dental Material
    "T103",  # Chemical
    "T120",  # Chemical Viewed Functionally
    "T104",  # Chemical Viewed Structurally
    
    # Procedures
    "T061",  # Therapeutic or Preventive Procedure
    "T060",  # Diagnostic Procedure
    "T063",  # Molecular Biology Research Technique
    "T062",  # Research Activity
    "T065",  # Educational Activity
    
    # Anatomy
    "T023",  # Body Part, Organ, or Organ Component
    "T024",  # Tissue
    "T025",  # Cell
    "T026",  # Cell Component
    "T029",  # Body Location or Region
    "T030",  # Body Space or Junction
    
    # Devices
    "T074",  # Medical Device
    "T075",  # Research Device
    
    # Findings
    "T033",  # Finding
    "T034",  # Laboratory or Test Result
    
    # Living Beings
    "T016",  # Human
    "T017",  # Anatomical Structure
    
    # Genes and Molecular
    "T028",  # Gene or Genome
    "T116",  # Amino Acid, Peptide, or Protein
    "T126",  # Enzyme
    "T125",  # Hormone
    "T129",  # Immunologic Factor
    "T192",  # Receptor
}

# Minimum confidence score for entity linking
MIN_SCORE = 0.90

# Maximum length for entity text (avoid matching entire sentences)
MAX_ENTITY_LENGTH = 100

# Minimum length for entity text (avoid single letters)
MIN_ENTITY_LENGTH = 2