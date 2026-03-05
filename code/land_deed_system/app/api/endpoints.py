from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List

from app.core.prompts import generate_prompt
from app.services.llm_service import call_llm
from app.core.validator import validate_deed_data, ValidationError
from app.core.normalizer import normalize_date, normalize_currency
from app.core.translator import translate_text
from app.core.corrector import detect_ocr_conflicts, check_semantic_consistency, suggest_correction_prompt
from app.models.deed import DeedParsingResult, OCRCorrection

import json

router = APIRouter()

class ParseRequest(BaseModel):
    text: str
    temperature: float = 0.1

class ParseResponse(BaseModel):
    parsed_data: DeedParsingResult
    validation_warnings: List[str] = []

@router.post("/parse", response_model=ParseResponse)
async def parse_deed(request: ParseRequest):
    """
    Parses an ancient land deed text using Few-Shot Prompt Engineering.
    Includes auto-retry mechanism for validation failures.
    """
    current_temp = request.temperature
    prompt = generate_prompt(request.text)
    
    max_retries = 3
    last_error = None
    
    for attempt in range(max_retries):
        try:
            # 1. Call LLM
            llm_response = await call_llm(prompt, temperature=current_temp, response_format="json_object")
            
            # 2. Extract JSON from response (simple strip for now)
            # In real scenario, might need regex to find JSON block
            json_str = llm_response.strip()
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0].strip()
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0].strip()
                
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError:
                raise ValidationError("Invalid JSON format from LLM")

            # 3. Validate
            validated_result = validate_deed_data(data)
            
            # 4. Check for Semantic Conflicts (Business Rules)
            # This is already partly done in validate_deed_data, but let's add extra check
            semantic_issues = check_semantic_consistency(request.text)
            
            return ParseResponse(
                parsed_data=validated_result,
                validation_warnings=semantic_issues
            )
            
        except ValidationError as e:
            last_error = str(e)
            # Adjust prompt for retry
            prompt = generate_prompt(request.text, previous_error=last_error)
            current_temp = max(0.0, current_temp - 0.1) # Reduce temp
            continue
            
    raise HTTPException(status_code=422, detail=f"Failed to parse after {max_retries} attempts. Last error: {last_error}")

class NormalizeDateRequest(BaseModel):
    date_str: str

class NormalizeDateResponse(BaseModel):
    original: str
    normalized: str
    confidence: float

@router.post("/normalize/date", response_model=NormalizeDateResponse)
async def normalize_date_endpoint(request: NormalizeDateRequest):
    orig, norm, conf = normalize_date(request.date_str)
    return NormalizeDateResponse(original=orig, normalized=norm, confidence=conf)

class NormalizeCurrencyRequest(BaseModel):
    amount_str: str

class NormalizeCurrencyResponse(BaseModel):
    original: str
    normalized: str
    confidence: float

@router.post("/normalize/currency", response_model=NormalizeCurrencyResponse)
async def normalize_currency_endpoint(request: NormalizeCurrencyRequest):
    orig, norm, conf = normalize_currency(request.amount_str)
    return NormalizeCurrencyResponse(original=orig, normalized=norm, confidence=conf)

class TranslateRequest(BaseModel):
    text: str

class TranslateResponse(BaseModel):
    original: str
    translation: str

@router.post("/translate", response_model=TranslateResponse)
async def translate_endpoint(request: TranslateRequest):
    translation = await translate_text(request.text)
    return TranslateResponse(original=request.text, translation=translation)

class CorrectionRequest(BaseModel):
    text: str

class CorrectionResponse(BaseModel):
    ocr_corrections: List[OCRCorrection]
    semantic_conflicts: List[str]
    suggested_fix_prompt: Optional[str] = None

@router.post("/correct", response_model=CorrectionResponse)
async def correct_endpoint(request: CorrectionRequest):
    ocr_fixes = detect_ocr_conflicts(request.text)
    semantic_issues = check_semantic_consistency(request.text)
    
    fix_prompt = None
    if semantic_issues:
        fix_prompt = suggest_correction_prompt(request.text, "; ".join(semantic_issues))
        
    return CorrectionResponse(
        ocr_corrections=ocr_fixes,
        semantic_conflicts=semantic_issues,
        suggested_fix_prompt=fix_prompt
    )
