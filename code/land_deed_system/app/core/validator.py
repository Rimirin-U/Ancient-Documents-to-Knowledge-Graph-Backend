from typing import Dict, Any, List
from app.models.deed import DeedParsingResult

class ValidationError(Exception):
    def __init__(self, message: str, details: Any = None):
        self.message = message
        self.details = details
        super().__init__(self.message)

def validate_business_rules(data: DeedParsingResult) -> List[str]:
    errors = []
    
    # Extract special terms text
    special_terms = [term.text for term in data.extracted_entities.special_terms]
    special_terms_str = " ".join(special_terms)

    # Rule 1: "绝卖" (Irrevocable Sale) cannot contain "回赎" (Redemption)
    if "杜绝卖" in special_terms_str or "绝卖" in special_terms_str:
        if "回赎" in special_terms_str or "取赎" in special_terms_str:
            errors.append("Conflict detected: Deed is marked as 'Irrevocable Sale' (绝卖) but contains 'Redemption' (回赎) terms.")

    # Rule 2: "典契" (Mortgage) usually implies redemption
    if "典契" in special_terms_str:
        if not any(term in special_terms_str for term in ["回赎", "取赎", "限"]):
            # This is a warning, not necessarily an error, but for strict validation we can flag it
            pass 

    return errors

def validate_deed_data(raw_data: Dict[str, Any]) -> DeedParsingResult:
    try:
        # 1. Pydantic Validation (Schema & Types)
        deed_result = DeedParsingResult(**raw_data)
        
        # 2. Business Logic Validation
        rule_violations = validate_business_rules(deed_result)
        if rule_violations:
            raise ValidationError(f"Business Rule Violations: {'; '.join(rule_violations)}", details=rule_violations)
            
        return deed_result
        
    except Exception as e:
        raise ValidationError(f"Validation Failed: {str(e)}")
