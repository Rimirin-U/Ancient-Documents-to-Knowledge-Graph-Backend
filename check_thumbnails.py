import sys
import os

# Ensure we can import from app
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from database import SessionLocal, MultiTask, MultiTaskStructuredResult, StructuredResult, OcrResult, Image

db = SessionLocal()
multi_tasks = db.query(MultiTask).all()

for task in multi_tasks:
    print(f"Task ID: {task.id}")
    preview_images = (
        db.query(OcrResult.image_id)
        .join(StructuredResult, StructuredResult.ocr_result_id == OcrResult.id)
        .join(MultiTaskStructuredResult, MultiTaskStructuredResult.structured_result_id == StructuredResult.id)
        .filter(MultiTaskStructuredResult.multi_task_id == task.id)
        .limit(3)
        .all()
    )
    print(f"  Preview Image IDs: {[img[0] for img in preview_images]}")
    
    # Let's manually check the associations
    associations = db.query(MultiTaskStructuredResult).filter(MultiTaskStructuredResult.multi_task_id == task.id).all()
    print(f"  Associations SR IDs: {[a.structured_result_id for a in associations]}")
    for a in associations:
        sr = db.query(StructuredResult).filter(StructuredResult.id == a.structured_result_id).first()
        if sr:
            ocr = db.query(OcrResult).filter(OcrResult.id == sr.ocr_result_id).first()
            if ocr:
                print(f"    SR ID {sr.id} -> OCR ID {ocr.id} -> Image ID {ocr.image_id}")
            else:
                print(f"    SR ID {sr.id} -> No OCR found!")
        else:
            print(f"    SR ID {a.structured_result_id} -> Not found!")
