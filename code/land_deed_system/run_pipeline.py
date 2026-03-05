import os
import sys
import asyncio
from pathlib import Path

# Add the project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

# Import modules
from app.run_module1 import main as module1_main
from app.run_module2 import main as module2_main
from app.run_module3 import main as module3_main

def run_step(step_name, func):
    print(f"\n{'='*20} Running {step_name} {'='*20}")
    try:
        # Check if the function is async
        if asyncio.iscoroutinefunction(func):
            asyncio.run(func())
        else:
            func()
        print(f"{step_name} completed successfully.")
    except Exception as e:
        print(f"Error in {step_name}: {e}")
        # Depending on requirements, we might want to stop here
        # sys.exit(1)

def main():
    print("Starting Land Deed System Pipeline...")
    
    # Check for data directory
    data_dir = BASE_DIR.parent / "data"
    if not data_dir.exists():
        data_dir = BASE_DIR / "data"
        if not data_dir.exists():
            print(f"Error: Data directory not found at {data_dir} or {BASE_DIR.parent / 'data'}")
            print("Please create a 'data' folder and put your text files in it.")
            return

    # Check for .env
    env_file = BASE_DIR / ".env"
    if not env_file.exists():
        print("Warning: .env file not found. API calls might fail.")
    
    # Step 1: Parse Deeds (LLM Extraction & Translation)
    # Note: run_module1.main() is synchronous wrapper around async parser
    run_step("Module 1: Parsing & Translation", module1_main)
    
    # Step 2: Coreference Resolution
    run_step("Module 2: Entity Resolution", module2_main)
    
    # Step 3: Social Network Analysis
    run_step("Module 3: Social Network Analysis", module3_main)
    
    print("\nAll steps completed!")
    print(f"Check the output directory for results.")

if __name__ == "__main__":
    main()
