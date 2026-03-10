"""
Keyword lists for LOLER and pressure vessel document classification.

These keywords are derived from the actual legal text and standard
terminology used in UK LOLER and PSSR documentation.

The classifier scores documents against these lists to determine
document type before extraction begins.
"""

# Keywords strongly associated with LOLER certificates
# Source: LOLER 1998, ACOP L113, standard examiner report terminology
LOLER_KEYWORDS = [
    # Legal and regulatory terms
    "loler",
    "lifting operations",
    "lifting equipment",
    "thorough examination",
    "written scheme of examination",
    "regulation 9",
    "regulation 10",

    # Equipment types
    "crane",
    "hoist",
    "forklift",
    "fork lift",
    "fork-lift",
    "mewp",
    "mobile elevating work platform",
    "cherry picker",
    "scissor lift",
    "pallet truck",
    "overhead travelling crane",
    "patient hoist",
    "vehicle lift",
    "tail lift",
    "goods lift",
    "passenger lift",
    "lifting accessory",
    "chain sling",
    "wire rope sling",
    "shackle",
    "eyebolt",
    "spreader beam",

    # Certificate fields
    "safe working load",
    "swl",
    "wll",
    "working load limit",
    "rated capacity",
    "next thorough examination",
    "date of thorough examination",
    "examiner",
    "competent person",
]

# Keywords strongly associated with pressure vessel / PSSR certificates
# Source: PSSR 2000, HSE guidance, standard inspection terminology
PRESSURE_VESSEL_KEYWORDS = [
    # Legal and regulatory terms
    "pssr",
    "pressure systems safety regulations",
    "pressure vessel",
    "pressure system",
    "written scheme",
    "periodic inspection",
    "in-service inspection",

    # Equipment types
    "boiler",
    "steam boiler",
    "autoclave",
    "compressor",
    "air receiver",
    "compressed air",
    "heat exchanger",
    "pressure vessel",
    "pressurised pipeline",
    "safety valve",
    "relief valve",
    "pressure relief device",

    # Technical fields
    "maximum allowable working pressure",
    "mawp",
    "design pressure",
    "test pressure",
    "hydraulic test",
    "pneumatic test",
    "corrosion allowance",
    "wall thickness",
    "inspection interval",
    "next inspection due",
    "plant number",
    "vessel number",
]

# Keywords that suggest the document is neither LOLER nor PSSR
# Used to apply penalties to confidence scores
NEGATIVE_KEYWORDS = [
    "fire extinguisher",
    "pat test",
    "portable appliance",
    "electrical installation",
    "risk assessment",
    "method statement",
    "coshh",
    "manual handling",
]