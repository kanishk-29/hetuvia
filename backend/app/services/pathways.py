"""DEMONSTRATION pathway catalogue. These are placeholders, not Abu Dhabi guidance."""

PATHWAY_STATUS = "demonstration"

# care-gap rule id -> (pathway code, pathway title)
SERVICE_PATHWAYS = {
    "DEMO-WCV": ("DEMO-PATHWAY-WCV", "Well-Child Visit (demonstration)"),
    "DEMO-ADULT-SCREEN": ("DEMO-PATHWAY-ADULT", "Adult Comprehensive Screening (demonstration)"),
}
INFORMATION_PATHWAY_CODE = "DEMO-PATHWAY-INFO"
INFORMATION_PATHWAY_TITLE = "Resolve missing information first (demonstration)"
INFORMATION_RULE_ID = "DATA-QUALITY"
# Data-quality rules that block a confident recommendation: missing date of birth, family-history gap.
BLOCKING_DATA_QUALITY_RULES = ("DQ-001", "DQ-003")