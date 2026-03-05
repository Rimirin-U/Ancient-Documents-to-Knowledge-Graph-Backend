import json
import os
from pathlib import Path
from sqlalchemy.orm import Session
from app.database import engine, Base, SessionLocal
from app.models import Document, Entity, Relation
from app.resolution import EntityResolver

def init_db():
    print("Initializing database...")
    Base.metadata.create_all(bind=engine)
    print("Database tables created.")

def load_parsed_data(json_path: str):
    if not os.path.exists(json_path):
        print(f"Error: File {json_path} not found. Please run Module 1 first.")
        return []
    
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)

def main():
    # 1. Initialize DB
    init_db()
    
    # 2. Load Data
    # Determine base directory (project root: land_deed_system)
    base_dir = Path(__file__).resolve().parent.parent
    
    output_dir = base_dir.parent / "output"
    if not output_dir.exists():
         output_dir = base_dir / "output"

    json_path = output_dir / "parsed_deeds.json"
    data = load_parsed_data(json_path)
    
    if not data:
        print("No data to process.")
        return

    # 3. Process each document
    db = SessionLocal()
    resolver = EntityResolver(db)
    
    try:
        print(f"Processing {len(data)} documents...")
        for entry in data:
            filename = entry.get("filename", "unknown.txt")
            print(f"Resolving entities for {filename}...")
            resolver.process_parsed_data(entry, filename)
        
        print("Coreference resolution complete.")
        
        # 4. Verify results
        doc_count = db.query(Document).count()
        entity_count = db.query(Entity).count()
        relation_count = db.query(Relation).count()
        
        print("\n=== Database Statistics ===")
        print(f"Documents: {doc_count}")
        print(f"Entities: {entity_count}")
        print(f"Relations: {relation_count}")
        
        print("\n=== Sample Entities ===")
        for entity in db.query(Entity).limit(5).all():
            print(f"ID: {entity.id}, Name: {entity.name}, Type: {entity.type}, Years: {entity.first_seen_year}-{entity.last_seen_year}")
            
    except Exception as e:
        print(f"An error occurred: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    main()
