
import os
import dashscope
from dashscope import Generation
import asyncio
from functools import partial

# Initialize DashScope API Key
dashscope.api_key = os.getenv("DASHSCOPE_API_KEY", "sk-293d49ac3daf4fd58b643b1542a4c89f")

async def call_llm(prompt: str, model: str = "qwen-plus", temperature: float = 0.1, response_format: str = "text") -> str:
    """
    Calls the DashScope LLM API asynchronously using run_in_executor.
    """
    try:
        # Construct messages
        messages = [{'role': 'user', 'content': prompt}]
        
        # Prepare the synchronous call
        call_func = partial(
            Generation.call,
            model=model,
            messages=messages,
            result_format='message',
            temperature=temperature
        )
        
        # Run in a separate thread to avoid blocking the event loop
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(None, call_func)
        
        if response.status_code == 200:
            return response.output.choices[0].message.content
        else:
            raise Exception(f"DashScope API Error: {response.code} - {response.message}")
            
    except Exception as e:
        print(f"LLM Call Error: {e}")
        raise e
