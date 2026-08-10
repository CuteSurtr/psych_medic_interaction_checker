from __future__ import annotations
import uuid
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from database.connection import SessionLocal, get_db
from models import DoseSchedule, Medication, Simulation
router = APIRouter(prefix='/api/simulation', tags=['simulation'])

class DoseEventIn(BaseModel):
    medication_id: int
    event_type: str
    event_day: int
    dose_mg: float
    frequency: str = 'daily'

class SimulationCreateBody(BaseModel):
    patient_age: int | None = None
    patient_weight_kg: float = 70
    smoking_status: bool = False
    egfr: float | None = None
    hepatic_impairment: str = 'none'
    pregnancy_status: bool = False
    cyp2d6_phenotype: str = 'normal'
    cyp2c19_phenotype: str = 'normal'
    dose_schedules: list[DoseEventIn] = Field(default_factory=list)
    horizon_days: int = 56

@router.post('/create')
def create_simulation(body: SimulationCreateBody, db: Session=Depends(get_db)) -> dict[str, Any]:
    sid = uuid.uuid4()
    sim = Simulation(session_id=sid, patient_age=body.patient_age, patient_weight_kg=body.patient_weight_kg, smoking_status=body.smoking_status, egfr=body.egfr, hepatic_impairment=body.hepatic_impairment, pregnancy_status=body.pregnancy_status, cyp2d6_phenotype=body.cyp2d6_phenotype, cyp2c19_phenotype=body.cyp2c19_phenotype, horizon_days=body.horizon_days)
    db.add(sim)
    db.flush()
    for ev in body.dose_schedules:
        db.add(DoseSchedule(simulation_id=sim.id, medication_id=ev.medication_id, event_type=ev.event_type, event_day=ev.event_day, dose_mg=ev.dose_mg, frequency=ev.frequency))
    db.commit()
    db.refresh(sim)
    return {'simulation_id': sim.id, 'session_id': str(sid)}

def _simulate(db: Session, dose_events: list[dict[str, Any]], *, horizon_days: int, cyp2d6_phenotype: str, cyp2c19_phenotype: str, smoking: bool, patient_weight_kg: float) -> dict[str, Any]:
    """Run the PK simulation from plain dose events.

    Shared by the stateless `/run` endpoint and the persisted `/{sim_id}/run`
    endpoint. Only reads medications and CYP profiles, which are static
    reference data, so nothing here needs a writable database.
    """
    from services.pk_simulator import run_simulation
    from services.simulation_builder import build_config_from_dose_events, serialize_result
    try:
        config = build_config_from_dose_events(db, dose_events, horizon_days=horizon_days, cyp2d6_phenotype=cyp2d6_phenotype, cyp2c19_phenotype=cyp2c19_phenotype, smoking=smoking, patient_weight_kg=patient_weight_kg)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return serialize_result(run_simulation(config))

@router.post('/run')
def run_simulation_stateless(body: SimulationCreateBody) -> dict[str, Any]:
    """Configure and run a simulation in a single request.

    The create-then-run pair below needs the simulation row to survive between
    two HTTP calls, which a serverless deployment cannot guarantee. This
    endpoint takes the same body and returns the result directly, so it works
    identically on Vercel and under Docker.
    """
    db = SessionLocal()
    try:
        return _simulate(db, [e.model_dump() for e in body.dose_schedules], horizon_days=body.horizon_days, cyp2d6_phenotype=body.cyp2d6_phenotype, cyp2c19_phenotype=body.cyp2c19_phenotype, smoking=body.smoking_status, patient_weight_kg=body.patient_weight_kg)
    finally:
        db.close()

@router.get('/{sim_id}/run')
def run_simulation_endpoint(sim_id: int, db: Session=Depends(get_db)) -> dict[str, Any]:
    sim = db.query(Simulation).filter(Simulation.id == sim_id).first()
    if not sim:
        raise HTTPException(status_code=404, detail='Simulation not found')
    schedules_db = db.query(DoseSchedule).filter(DoseSchedule.simulation_id == sim_id).order_by(DoseSchedule.event_day).all()
    dose_events = [{'medication_id': s.medication_id, 'event_type': s.event_type, 'event_day': s.event_day, 'dose_mg': float(s.dose_mg), 'frequency': s.frequency} for s in schedules_db]
    return _simulate(db, dose_events, horizon_days=sim.horizon_days, cyp2d6_phenotype=sim.cyp2d6_phenotype, cyp2c19_phenotype=sim.cyp2c19_phenotype, smoking=bool(sim.smoking_status), patient_weight_kg=sim.patient_weight_kg)

@router.get('/templates')
def list_templates() -> list[dict[str, Any]]:
    from database.seed_data import SCENARIO_ROWS
    return [{'id': i, 'name': s['name'], 'description': s['description']} for i, s in enumerate(SCENARIO_ROWS)]

@router.get('/templates/{template_id}')
def get_template(template_id: int) -> dict[str, Any]:
    from database.seed_data import SCENARIO_ROWS
    if template_id < 0 or template_id >= len(SCENARIO_ROWS):
        raise HTTPException(status_code=404, detail='Template not found')
    return SCENARIO_ROWS[template_id]
