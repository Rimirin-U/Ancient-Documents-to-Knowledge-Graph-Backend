import os
import json
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

# Initialize OpenAI client
# Ensure OPENAI_API_KEY is set in environment variables or .env file
# Ensure OPENAI_BASE_URL is set for DashScope (https://dashscope.aliyuncs.com/compatible-mode/v1)

async def call_llm(prompt: str, model: str = "qwen-plus", temperature: float = 0.1, response_format: str = "text") -> str:
    """
    Calls the LLM API asynchronously.
    """
    client = AsyncOpenAI(
        api_key=os.environ.get("OPENAI_API_KEY"),
        base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    )
    
    try:
        messages = [{"role": "user", "content": prompt}]
        
        params = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        
        if response_format == "json_object":
            params["response_format"] = {"type": "json_object"}
            
        response = await client.chat.completions.create(**params)
        return response.choices[0].message.content
        
    except Exception as e:
        print(f"LLM Call Error: {e}")
        raise e
    finally:
        await client.close()
