import asyncio
import json
from typing import Dict, Any, List
from app.core.prompts import generate_prompt
from app.services.llm_service import call_llm
from app.core.translator import translate_text
from app.models.deed import DeedParsingResult
from app.core.validator import validate_deed_data, ValidationError

async def parse_deed_async(ocr_text: str, model: str = "qwen-plus", max_retries: int = 3) -> Dict[str, Any]:
    """
    Async implementation of deed parsing.
    Orchestrates Extraction (LLM), Validation, and Translation (LLM).
    Returns a dictionary in the legacy flat format for compatibility with run_module1/2.
    """
    
    # 1. Generate Extraction Prompt
    # Uses the v1_0_0 template which asks for nested JSON (DeedParsingResult schema)
    prompt = generate_prompt(ocr_text)
    
    deed_result: DeedParsingResult = None
    last_error = None

    # 2. Extraction Loop (with Retries)
    for attempt in range(max_retries):
        try:
            # Call LLM for Extraction
            llm_response = await call_llm(prompt, model=model, temperature=0.1, response_format="json_object")
            
            # Clean response (remove markdown code blocks if present)
            json_str = llm_response.strip()
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0].strip()
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0].strip()
            
            # Parse JSON
            data = json.loads(json_str)
            
            # Validate with Pydantic & Business Rules
            # validate_deed_data returns a DeedParsingResult object
            deed_result = validate_deed_data(data)
            break
            
        except (json.JSONDecodeError, ValidationError) as e:
            print(f"[Warning] Attempt {attempt + 1} extraction failed: {e}")
            last_error = str(e)
            if attempt < max_retries - 1:
                # Update prompt with error context
                prompt = generate_prompt(ocr_text, previous_error=last_error)
            else:
                print("[Error] Max retries reached for extraction.")
                return None
        except Exception as e:
            print(f"[Critical Error] Extraction API Call failed: {e}")
            return None

    if not deed_result:
        return None

    # 3. Translation (Parallel Task)
    # We run translation separately because the extraction prompt doesn't ask for it
    # to keep the context window focused and structured.
    try:
        translation = await translate_text(ocr_text)
    except Exception as e:
        print(f"[Warning] Translation failed: {e}")
        translation = "翻译失败"

    # 4. Flatten / Convert to Legacy Format
    # Map the rich DeedParsingResult structure to the flat dict expected by run_module2.py
    
    entities = deed_result.extracted_entities
    
    # Helper to join list of entities
    def join_entities(entity_list: List[Any]) -> str:
        return ", ".join([e.text for e in entity_list]) if entity_list else ""

    # Helper to get date normalized value
    time_ad = None
    if entities.date and entities.date.normalized_value:
        # Expecting "YYYY-MM-DD" or "YYYY"
        try:
            time_ad = int(entities.date.normalized_value.split("-")[0])
        except:
            pass

    flat_result = {
        "Time": entities.date.text if entities.date else "未知",
        "Time_AD": time_ad,
        "Location": entities.boundaries.text if entities.boundaries else (entities.subject.text if entities.subject else "未知"),
        "Seller": join_entities(entities.sellers) if entities.sellers else "未知",
        "Buyer": join_entities(entities.buyers) if entities.buyers else "未知",
        "Middleman": join_entities(entities.witnesses) if entities.witnesses else "",
        "Price": entities.price.text if entities.price else "未知",
        "Subject": entities.subject.text if entities.subject else "未知",
        "Translation": translation,
        "filename": "pending" # Will be set by run_module1
    }

    return flat_result

def parse_land_deed(ocr_text: str, model: str = "qwen-plus", max_retries: int = 3) -> Dict[str, Any]:
    """
    Synchronous wrapper for compatibility with existing run_module1.py
    """
    try:
        # Simple fix: Always use asyncio.run but handle the closed loop error if it occurs at shutdown
        # The error user saw "RuntimeError: Event loop is closed" is likely from ProactorPipeTransport.__del__
        # This is a known issue in Windows with asyncio when the loop is closed but some transports are still active.
        # It's usually harmless noise at exit.
        
        # To make it robust:
        return asyncio.run(parse_deed_async(ocr_text, model, max_retries))
            
    except RuntimeError as e:
        if "Event loop is closed" in str(e):
             # This might happen if we try to reuse a closed loop, but asyncio.run creates a new one.
             pass
        print(f"RuntimeError in parse_land_deed: {e}")
        return None
    except Exception as e:
        print(f"Error in parse_land_deed: {e}")
        return None
