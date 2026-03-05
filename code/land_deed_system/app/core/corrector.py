from typing import List, Dict, Optional
from app.models.deed import OCRCorrection

# High-frequency conflict/error dictionary
# Key: Wrong Term, Value: Correct Term
COMMON_OCR_ERRORS = {
    "绝买": "绝卖",
    "杜绝买": "杜绝卖",
    "立契人": "立卖契人", # Context dependent, but common fix
    "中人": "凭中", # Sometimes interchange
    "代书": "代笔",
    "纹银": "纹银", # Just ensuring
    "洋银": "洋银",
}

# Semantic Conflict Rules
# (Term A, Term B) -> Conflict Description
CONFLICT_RULES = [
    ("绝卖", "回赎", "Irrevocable sale cannot have redemption clause"),
    ("杜绝", "找贴", "Irrevocable sale cannot have additional payment"),
    ("典契", "永不赎", "Mortgage must allow redemption"),
]

def detect_ocr_conflicts(text: str) -> List[OCRCorrection]:
    corrections = []
    
    # 1. Simple Keyword Replacement
    for wrong, right in COMMON_OCR_ERRORS.items():
        if wrong in text and right not in text: # Heuristic
            # Only correct if the context strongly suggests it? 
            # For now, we just list it as a potential correction
             pass
            
    return corrections

def check_semantic_consistency(text: str) -> List[str]:
    issues = []
    for term_a, term_b, msg in CONFLICT_RULES:
        if term_a in text and term_b in text:
            issues.append(f"Conflict: '{term_a}' and '{term_b}' found. {msg}")
    return issues

def suggest_correction_prompt(text: str, conflict_msg: str) -> str:
    return f"""
The following ancient land deed text contains a logical conflict: {conflict_msg}.
Text: "{text}"
Please identify the likely OCR error causing this conflict (e.g., "绝买" should be "绝卖") and provide the corrected text and the specific correction made.
"""
