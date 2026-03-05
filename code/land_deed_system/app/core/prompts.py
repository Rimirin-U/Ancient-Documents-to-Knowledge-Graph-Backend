import os
from jinja2 import Template
from app.core.examples import few_shot_examples

PROMPT_DIR = os.path.join(os.path.dirname(__file__), "..", "prompts")
DEFAULT_VERSION = "v1_0_0"

def load_template(version: str = DEFAULT_VERSION) -> str:
    path = os.path.join(PROMPT_DIR, f"{version}.jinja2")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Prompt template {version} not found.")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def generate_prompt(input_text: str, version: str = DEFAULT_VERSION, previous_error: str = None) -> str:
    template_str = load_template(version)
    template = Template(template_str)
    
    rendered = template.render(examples=few_shot_examples, input_text=input_text)
    
    if previous_error:
        rendered += f"\n\n!!! PREVIOUS ATTEMPT ERROR: {previous_error} !!!\nPlease fix the JSON format or schema validation error."
        
    return rendered
