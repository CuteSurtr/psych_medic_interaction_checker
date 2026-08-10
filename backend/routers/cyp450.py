from typing import Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from database.connection import get_db
from services.cyp450_analyzer import analyze_cyp450
router = APIRouter(prefix='/api/cyp450', tags=['cyp450'])

@router.get('/profile')
def cyp450_profile(medication_ids: str=Query(..., description='Comma-separated medication IDs'), cyp2d6_phenotype: str=Query('normal'), cyp2c19_phenotype: str=Query('normal'), db: Session=Depends(get_db)) -> dict[str, Any]:
    ids = [int(x.strip()) for x in medication_ids.split(',') if x.strip().isdigit()]
    return analyze_cyp450(db, ids, cyp2d6_phenotype=cyp2d6_phenotype, cyp2c19_phenotype=cyp2c19_phenotype)
