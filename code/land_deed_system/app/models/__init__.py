from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), unique=True, index=True)
    
    # Parsed content
    time_text = Column(String(255))
    time_ad = Column(Integer, index=True) # AD Year
    location = Column(Text)
    price = Column(String(255))
    subject = Column(Text)
    translation = Column(Text)
    
    # One document has many relations (and thus many entities involved)
    relations = relationship("Relation", back_populates="document", cascade="all, delete-orphan")

class Entity(Base):
    __tablename__ = "entities"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), index=True)
    type = Column(String(50)) # Person, Organization, Location
    
    # Metadata for resolution
    first_seen_year = Column(Integer, nullable=True)
    last_seen_year = Column(Integer, nullable=True)
    
    # One entity can be involved in many relations
    relations = relationship("Relation", back_populates="entity", cascade="all, delete-orphan")

class Relation(Base):
    __tablename__ = "relations"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"))
    entity_id = Column(Integer, ForeignKey("entities.id"))
    role = Column(String(50)) # Seller, Buyer, Middleman
    
    document = relationship("Document", back_populates="relations")
    entity = relationship("Entity", back_populates="relations")
