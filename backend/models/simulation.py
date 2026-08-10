from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship as sa_relationship
from sqlalchemy.sql import func
from database.connection import Base
from models.types import GUID

class Simulation(Base):
    __tablename__ = 'simulations'
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(GUID, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    patient_age = Column(Integer)
    patient_weight_kg = Column(Numeric(5, 1), default=70)
    smoking_status = Column(Boolean, default=False)
    egfr = Column(Numeric(10, 2))
    hepatic_impairment = Column(String(20), default='none')
    pregnancy_status = Column(Boolean, default=False)
    cyp2d6_phenotype = Column(String(30), default='normal')
    cyp2c19_phenotype = Column(String(30), default='normal')
    horizon_days = Column(Integer, default=56)
    dose_schedules = sa_relationship('DoseSchedule', back_populates='simulation', cascade='all, delete-orphan')

class DoseSchedule(Base):
    __tablename__ = 'dose_schedules'
    id = Column(Integer, primary_key=True, index=True)
    simulation_id = Column(Integer, ForeignKey('simulations.id'), nullable=False)
    medication_id = Column(Integer, ForeignKey('medications.id'), nullable=False)
    event_type = Column(String(20), nullable=False)
    event_day = Column(Integer, nullable=False)
    dose_mg = Column(Numeric(10, 2), nullable=False)
    frequency = Column(String(50), nullable=False)
    simulation = sa_relationship('Simulation', back_populates='dose_schedules')
    medication = sa_relationship('Medication')
