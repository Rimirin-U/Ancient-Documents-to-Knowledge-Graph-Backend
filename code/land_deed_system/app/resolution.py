import re
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from app.models import Document, Entity, Relation

class EntityResolver:
    def __init__(self, db: Session):
        self.db = db
        
    def _parse_year(self, year_str: str) -> Optional[int]:
        if not year_str:
            return None
        match = re.search(r"(\d+)", year_str)
        return int(match.group(1)) if match else None

    def _calculate_similarity(self, 
                            name: str, 
                            doc_year: int, 
                            doc_location: str, 
                            doc_middlemen: List[str], 
                            candidate: Entity) -> float:
        """
        Calculates probability that the person in the current doc is the candidate entity.
        Returns a score between 0.0 and 1.0.
        """
        score = 0.0
        weights = {
            "time": 0.3,
            "location": 0.3,
            "social": 0.4
        }
        
        # 1. Time Check (Hard Constraint: Must be within reasonable lifespan)
        # If no year data, assume possible but lower confidence
        if candidate.first_seen_year and doc_year:
            diff = abs(doc_year - candidate.first_seen_year)
            if diff > 60: # Unlikely to be the same active adult person > 60 years apart
                return 0.0
            # Closer in time = higher score
            time_score = max(0, 1 - (diff / 60))
        else:
            time_score = 0.5 # Neutral if time unknown

        # 2. Location Check (Simple keyword overlap)
        # Check if current location overlaps with any of candidate's previous locations
        loc_score = 0.0
        candidate_locs = [r.document.location for r in candidate.relations if r.document and r.document.location]
        if not candidate_locs:
             loc_score = 0.5
        else:
            # Very simple overlap: check if 2+ chars match (excluding common words like "田", "土")
            # In a real system, use TF-IDF or embedding similarity
            for prev_loc in candidate_locs:
                # Calculate Jaccard similarity of characters
                set1 = set(doc_location)
                set2 = set(prev_loc)
                intersection = len(set1.intersection(set2))
                union = len(set1.union(set2))
                if union > 0 and (intersection / union) > 0.1: # Threshold
                    loc_score = 1.0
                    break
        
        # 3. Social Network Check (Common Middlemen)
        # Check if any middleman in current doc appears in candidate's previous docs
        social_score = 0.0
        candidate_middlemen = set()
        for r in candidate.relations:
            # Find middlemen in the same document
            doc_relations = r.document.relations
            for dr in doc_relations:
                if "中人" in dr.role or "代笔" in dr.role:
                    candidate_middlemen.add(dr.entity.name)
        
        common = set(doc_middlemen).intersection(candidate_middlemen)
        if common:
            social_score = 1.0 # Strong indicator
        
        final_score = (weights["time"] * time_score + 
                       weights["location"] * loc_score + 
                       weights["social"] * social_score)
                       
        return final_score

    def resolve_and_link(self, doc: Document, role: str, name_str: str, all_middlemen: List[str]):
        """
        Resolves a name string to an Entity (existing or new) and creates a Relation.
        """
        if not name_str or name_str in ["未知", "None"]:
            return

        # Split multiple names if comma separated (e.g. for middlemen)
        names = [n.strip() for n in name_str.replace("，", ",").split(",") if n.strip()]
        
        for name in names:
            # 1. Search for candidates
            candidates = self.db.query(Entity).filter(Entity.name == name).all()
            
            best_match = None
            best_score = 0.0
            
            doc_year = doc.time_ad
            
            if not candidates:
                # No existing entity with this name -> Create New
                pass
            else:
                # Check against candidates
                for cand in candidates:
                    score = self._calculate_similarity(
                        name, doc_year, doc.location, all_middlemen, cand
                    )
                    if score > 0.6 and score > best_score: # Threshold 0.6
                        best_score = score
                        best_match = cand
            
            if best_match:
                entity = best_match
                # Update temporal range
                if doc_year:
                    if entity.first_seen_year is None or doc_year < entity.first_seen_year:
                        entity.first_seen_year = doc_year
                    if entity.last_seen_year is None or doc_year > entity.last_seen_year:
                        entity.last_seen_year = doc_year
            else:
                # Create new
                entity = Entity(
                    name=name,
                    type="Person", # Default
                    first_seen_year=doc_year,
                    last_seen_year=doc_year
                )
                self.db.add(entity)
                self.db.flush() # Get ID
            
            # Create Relation
            rel = Relation(
                document_id=doc.id,
                entity_id=entity.id,
                role=role
            )
            self.db.add(rel)

    def process_parsed_data(self, data: dict, filename: str):
        """
        Main entry point to process a parsed JSON object and update DB.
        """
        # 1. Create/Get Document
        existing_doc = self.db.query(Document).filter(Document.filename == filename).first()
        if existing_doc:
            return # Skip if already processed
            
        doc = Document(
            filename=filename,
            time_text=data.get("Time"),
            time_ad=self._parse_year(data.get("Time_AD")),
            location=data.get("Location"),
            price=data.get("Price"),
            subject=data.get("Subject"),
            translation=data.get("Translation")
        )
        self.db.add(doc)
        self.db.flush()
        
        # Extract all middlemen names for social network context
        middlemen_str = data.get("Middleman", "")
        middlemen_list = [n.strip() for n in middlemen_str.replace("，", ",").split(",") if n.strip()]
        
        # 2. Resolve Entities
        # Seller
        self.resolve_and_link(doc, "Seller", data.get("Seller"), middlemen_list)
        # Buyer
        self.resolve_and_link(doc, "Buyer", data.get("Buyer"), middlemen_list)
        # Middlemen
        self.resolve_and_link(doc, "Middleman", data.get("Middleman"), middlemen_list)
        
        self.db.commit()
