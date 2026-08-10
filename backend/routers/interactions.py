from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from database.connection import get_db
from services.interaction_engine import resolve_regimen_interactions
router = APIRouter(prefix='/api/interactions', tags=['interactions'])

class InteractionCheckBody(BaseModel):
    medication_ids: list[int] = Field(default_factory=list)
    cyp2d6_phenotype: str = 'normal'
    cyp2c19_phenotype: str = 'normal'

@router.post('/check')
def check_interactions(body: InteractionCheckBody, db: Session=Depends(get_db)) -> dict[str, Any]:
    try:
        items = resolve_regimen_interactions(db, body.medication_ids, cyp2d6_phenotype=body.cyp2d6_phenotype, cyp2c19_phenotype=body.cyp2c19_phenotype)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {'interactions': items}
