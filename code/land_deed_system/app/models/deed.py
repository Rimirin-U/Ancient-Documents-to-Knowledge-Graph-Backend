from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator

class Entity(BaseModel):
    text: str = Field(..., description="The original text of the entity")
    normalized_value: Optional[str] = Field(None, description="Normalized value if applicable (e.g., date, currency)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score for this extraction")

class Relationship(BaseModel):
    source: str = Field(..., description="Source entity")
    target: str = Field(..., description="Target entity")
    type: str = Field(..., description="Type of relationship (e.g., 'buys_from', 'sells_to', 'witnessed_by')")

class ExtractedEntities(BaseModel):
    date: Optional[Entity] = Field(None, description="立契时间")
    buyers: List[Entity] = Field(default_factory=list, description="买方")
    sellers: List[Entity] = Field(default_factory=list, description="卖方")
    subject: Optional[Entity] = Field(None, description="标的物")
    boundaries: Optional[Entity] = Field(None, description="四至")
    price: Optional[Entity] = Field(None, description="价格")
    witnesses: List[Entity] = Field(default_factory=list, description="见证人")
    special_terms: List[Entity] = Field(default_factory=list, description="特殊条款")

class OCRCorrection(BaseModel):
    original: str = Field(..., description="Original OCR text segment")
    corrected: str = Field(..., description="Corrected text")
    reason: str = Field(..., description="Reason for correction")

class DeedParsingResult(BaseModel):
    extracted_entities: ExtractedEntities
    relationships: List[Relationship]
    confidence_scores: Dict[str, float] = Field(..., description="Overall confidence scores for different sections")
    raw_text: str = Field(..., description="The input raw text")
    ocr_corrections: List[OCRCorrection] = Field(default_factory=list, description="List of OCR corrections made")

    @validator('relationships')
    def validate_relationships(cls, v, values):
        # Basic validation can be added here
        return v
