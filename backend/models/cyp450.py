from sqlalchemy import Column, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship as sa_relationship
from database.connection import Base

class CYP450Profile(Base):
    __tablename__ = 'cyp450_profiles'
    id = Column(Integer, primary_key=True, index=True)
    medication_id = Column(Integer, ForeignKey('medications.id'), nullable=False)
    enzyme = Column(String(20), nullable=False)
    role = Column('relationship', String(20), nullable=False)
    potency = Column(String(20), default='moderate')
    fraction_metabolized = Column(Numeric(6, 4))
    ki_nm = Column(Numeric(12, 2))
    vmax_nmol_per_h = Column(Numeric(12, 2))
    km_nm = Column(Numeric(12, 2))
    medication = sa_relationship('Medication', back_populates='cyp450_profiles')
