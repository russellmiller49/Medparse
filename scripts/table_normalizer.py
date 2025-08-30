from typing import Dict, Any

UNIT_MAP = {"mg/dL": "mg/dL", "mmol/L": "mmol/L", "×10^3/µL": "x10^3/uL"}

def normalize_table(tbl: Dict[str, Any]) -> None:
    # Extend with rules as needed
    return