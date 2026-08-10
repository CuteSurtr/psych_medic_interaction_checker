from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import CORS_ORIGINS
from database.seed_db import create_tables, seed_if_empty
from routers import advanced_analysis, analysis, cyp450, interactions, medications, risk_summary, simulation

@asynccontextmanager
async def lifespan(_: FastAPI):
    create_tables()
    seed_if_empty()
    yield
app = FastAPI(title='NeuroTrace API', description='Psychiatric pharmacokinetic simulator and interaction engine.', version='1.0.0', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=True, allow_methods=['*'], allow_headers=['*'])
app.include_router(medications.router)
app.include_router(interactions.router)
app.include_router(cyp450.router)
app.include_router(risk_summary.router)
app.include_router(simulation.router)
app.include_router(analysis.router)
app.include_router(advanced_analysis.router)

@app.get('/health')
def health() -> dict[str, str]:
    return {'status': 'ok'}
