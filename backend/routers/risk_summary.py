from typing import Any
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from database.connection import get_db
from services.risk_calculator import compute_risk_summary
router = APIRouter(prefix='/api', tags=['risk'])

class RiskSummaryBody(BaseModel):
    medication_ids: list[int] = Field(default_factory=list)
    age: int | None = None
    smoking_status: bool = False
    egfr: float | None = None
    hepatic_impairment: str = 'none'
    pregnancy_status: bool = False
    cyp2d6_phenotype: str = 'normal'
    cyp2c19_phenotype: str = 'normal'

@router.post('/risk-summary')
def risk_summary(body: RiskSummaryBody, db: Session=Depends(get_db)) -> dict[str, Any]:
    return compute_risk_summary(db, body.medication_ids, age=body.age, smoking=body.smoking_status, egfr=body.egfr, hepatic=body.hepatic_impairment, pregnancy=body.pregnancy_status, cyp2d6=body.cyp2d6_phenotype, cyp2c19=body.cyp2c19_phenotype)
