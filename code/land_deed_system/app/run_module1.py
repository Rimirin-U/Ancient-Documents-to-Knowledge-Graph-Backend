import os
import json
from pathlib import Path
from app.parser import parse_land_deed

def main():
    # Configuration
    # Determine base directory (project root: land_deed_system)
    base_dir = Path(__file__).resolve().parent.parent
    
    # Data directory (check if data exists in project root or parent)
    data_dir = base_dir.parent / "data"
    if not data_dir.exists():
        data_dir = base_dir / "data"
        
    output_dir = base_dir.parent / "output"
    if not output_dir.parent.exists():
         output_dir = base_dir / "output"
         
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Check for API Key
    if not os.environ.get("OPENAI_API_KEY"):
        print("Warning: OPENAI_API_KEY environment variable not set. Please set it to run the parser.")
        # For demonstration purposes, we might skip actual API calls if key is missing, 
        # or let it fail gracefully in the parser.
    
    files = sorted(list(data_dir.glob("*.txt")))
    print(f"Found {len(files)} files in {data_dir}")

    results = []

    for file_path in files:
        print(f"Processing {file_path.name}...")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                ocr_text = f.read().strip()
            
            if not ocr_text:
                print(f"Skipping empty file: {file_path.name}")
                continue

            # Call the parser
            # Note: This requires a valid OpenAI API key.
            # If you don't have one set, this will fail or you can mock it.
            result = parse_land_deed(ocr_text)
            
            if result:
                result["filename"] = file_path.name
                results.append(result)
                print(f"Successfully parsed {file_path.name}")
                print(f"  Time: {result.get('Time')} -> {result.get('Time_AD')}")
                print(f"  Seller: {result.get('Seller')}")
                print(f"  Buyer: {result.get('Buyer')}")
            else:
                print(f"Failed to parse {file_path.name}")

        except Exception as e:
            print(f"Error processing {file_path.name}: {e}")

    # Save all results to JSON
    output_file = output_dir / "parsed_deeds.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"All processing complete. Results saved to {output_file}")

if __name__ == "__main__":
    main()
