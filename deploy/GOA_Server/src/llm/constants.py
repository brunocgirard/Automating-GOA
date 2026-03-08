"""
Shared constants and types for the LLM module.

This module contains:
- FieldWithConfidence: Pydantic model for field extraction with confidence scoring
- Confidence thresholds: Constants for categorizing confidence levels
- FIELD_DEPENDENCIES: Cross-field validation rules for related fields
- FIELD_GROUPS: Field categorization for divide-and-conquer extraction strategy

These constants and types are used across the LLM extraction pipeline to maintain
consistency in field processing, validation, and confidence scoring.
"""

from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field, validator


# Model for fields with confidence scoring
class FieldWithConfidence(BaseModel):
    """Model for a field extraction result with confidence scoring."""
    value: Optional[str] = Field(default=None, description="The extracted value for the field")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Confidence score from 0.0 to 1.0")

    @validator('confidence', pre=True, always=True)
    def clamp_confidence(cls, v):
        """Ensure confidence is within valid range."""
        if v is None:
            return 0.5
        try:
            v = float(v)
            return max(0.0, min(1.0, v))
        except (ValueError, TypeError):
            return 0.5


# Constants for confidence thresholds
CONFIDENCE_HIGH = 0.8  # Green indicator
CONFIDENCE_MEDIUM = 0.5  # Yellow indicator
CONFIDENCE_LOW = 0.3  # Red indicator - needs review


# Field dependency rules for cross-field validation
FIELD_DEPENDENCIES = {
    # Voltage-Frequency relationship
    "hz": {
        "depends_on": "voltage",
        "rules": [
            {"if_value_contains": ["480", "460", "440"], "suggest_value": "60", "suggest_hz": True},
            {"if_value_contains": ["400", "380", "415"], "suggest_value": "50", "suggest_hz": True},
            {"if_value_contains": ["230", "220", "240"], "suggest_value": "50", "suggest_hz": True},  # Typically EU
            {"if_value_contains": ["120", "110", "115"], "suggest_value": "60", "suggest_hz": True},  # Typically NA
        ]
    },
    # Country-Voltage relationship
    "voltage": {
        "depends_on": "country_destination",
        "rules": [
            {"if_value_contains": ["USA", "United States", "Canada", "Mexico"], "suggest_value": "480V", "suggest_hz": False},
            {"if_value_contains": ["UK", "United Kingdom", "EU", "Europe", "Germany", "France"], "suggest_value": "400V", "suggest_hz": False},
        ]
    },
    # Pneumatic fields should be consistent
    "psi": {
        "depends_on": None,
        "related_fields": ["cfm"],
        "validation": "if_psi_filled_check_cfm"
    }
}


# Field groups for Divide and Conquer strategy
FIELD_GROUPS = {
    "General & Utility": {
        "prefixes": ["ce_", "conformity_", "wi_", "sk_", "stpc_", "pt_", "vd_", "wrts_", "op_"],
        "exact": ["machine", "customer", "quote", "production_speed", "options_listing", "voltage", "hz", "amps", "psi", "cfm", "phases", "country"]
    },
    "Controls & Electrical": {
        "prefixes": ["plc_", "hmi_", "cps_", "cpp_", "blt_", "batch_", "etr_", "rts_", "lan_", "ci_", "eg_", "el_"],
        "exact": []
    },
    "Liquid Filling & Handling": {
        "prefixes": ["lf_", "gp_", "tb_", "sf_", "c_", "d_"],
        "exact": []
    },
    "Capping, Labeling & Other": {
        "prefixes": ["cs_", "bs_", "ps_", "ls_", "rj_", "plug_", "cap_", "bot_"],
        "exact": []
    }
}
