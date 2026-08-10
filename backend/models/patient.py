from sqlalchemy import Boolean, Column, DateTime, Integer, Numeric, String
from sqlalchemy.sql import func
from database.connection import Base
from models.types import GUID

class PatientProfile(Base):
    __tablename__ = 'patient_profiles'
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(GUID, nullable=False, index=True)
    age = Column(Integer)
    weight_kg = Column(Numeric(5, 1), default=70)
    smoking_status = Column(Boolean, default=False)
    egfr = Column(Numeric(10, 2))
    hepatic_impairment = Column(String(20), default='none')
    pregnancy_status = Column(Boolean, default=False)
    cyp2d6_phenotype = Column(String(30), default='normal')
    cyp2c19_phenotype = Column(String(30), default='normal')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
