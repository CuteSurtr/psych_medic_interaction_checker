from sqlalchemy import Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship as sa_relationship
from database.connection import Base
from models.types import StringArray

class Interaction(Base):
    __tablename__ = 'interactions'
    id = Column(Integer, primary_key=True, index=True)
    drug_a_id = Column(Integer, ForeignKey('medications.id'), nullable=False)
    drug_b_id = Column(Integer, ForeignKey('medications.id'), nullable=False)
    severity = Column(String(20), nullable=False)
    mechanism_type = Column(String(30), nullable=False)
    mechanism_detail = Column(Text, nullable=False)
    clinical_effect = Column(Text, nullable=False)
    recommendation = Column(Text, nullable=False)
    evidence_level = Column(String(20))
    literature_references = Column('references', StringArray)
    drug_a = sa_relationship('Medication', foreign_keys=[drug_a_id], back_populates='interactions_a')
    drug_b = sa_relationship('Medication', foreign_keys=[drug_b_id], back_populates='interactions_b')
