
from typing import Dict, Any
from app.services.llm_service import call_llm

TRANSLATION_PROMPT_TEMPLATE = """
You are an expert translator of ancient Chinese legal documents.
Translate the following Land Deed into Modern Chinese.

Requirements:
1.  **Preserve Structure**: Keep the original paragraphing and clause order.
2.  **Terminology**: 
    -   Do NOT translate proper nouns (Place names, Person names).
    -   Annotate ancient measurements (e.g., "三亩" -> "三亩(约X平方米)").
    -   Explain legal terms in brackets if obscure.
3.  **Tone**: Formal legal modern Chinese.

Input Text:
{text}

Output Translation:
"""

async def translate_text(text: str) -> str:
    """
    Translates ancient Chinese text to modern Chinese using LLM.
    """
    if not text:
        return ""
        
    prompt = TRANSLATION_PROMPT_TEMPLATE.format(text=text)
    
    try:
        # Call the LLM service
        # Default model is qwen-plus, temperature 0.3 for a bit more creativity in translation
        translation = await call_llm(prompt=prompt, temperature=0.3)
        return translation.strip()
    except Exception as e:
        print(f"Translation Error: {e}")
        return f"[Translation Failed: {str(e)}]"
