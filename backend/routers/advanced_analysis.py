from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from database.connection import get_db
router = APIRouter(prefix='/api/advanced', tags=['advanced-analysis'])

class TaperRequest(BaseModel):
    drug_name: str
    start_dose: float
    target_dose: float
    duration_days: int = 56
    constraints: dict | None = None

class MarkovRequest(BaseModel):
    drug_classes: list[str]
    initial_state: str = 'Partial Response'
    n_weeks: int = 52

class SDERequest(BaseModel):
    drugs: list[dict]
    dose_schedules: dict[str, list[list[float]]]
    duration_days: int = 56
    n_paths: int = 200
    method: str = 'milstein'

class GameTheoryRequest(BaseModel):
    medication_ids: list[int]

class InlineSimulation(BaseModel):
    """A simulation spec sent with the request instead of referenced by id.

    Lets these endpoints work without a durable database: a serverless
    deployment cannot guarantee that a simulation created in one invocation is
    visible from the next.
    """
    patient_weight_kg: float = 70
    smoking_status: bool = False
    cyp2d6_phenotype: str = 'normal'
    cyp2c19_phenotype: str = 'normal'
    horizon_days: int = 56
    dose_schedules: list[dict] = Field(default_factory=list)

class TissuePDERequest(BaseModel):
    simulation_id: int | None = None
    simulation: InlineSimulation | None = None
    p_eff_cm_per_h: dict[str, float] | None = None
    f_unbound: dict[str, float] | None = None
    slab_depth_cm: float = 1.0
    n_nodes: int = 41

class ReceptorOccupancyRequest(BaseModel):
    simulation_id: int | None = None
    simulation: InlineSimulation | None = None
    use_f_unbound: bool = True

class HepaticExtractionRequest(BaseModel):
    medication_ids: list[int]
    simulation_id: int | None = None
    simulation: InlineSimulation | None = None
    q_hepatic_l_per_h: float = 81.0

class MonteCarloRequest(BaseModel):
    simulation_id: int | None = None
    simulation: InlineSimulation | None = None
    n_iterations: int = 200
    seed: int = 42

class OptimalDesignRequest(BaseModel):
    """Where to place TDM samples. PK parameters come from the formulary when a
    medication_id is given, and any explicit value overrides it."""
    medication_id: int | None = None
    dose_mg: float = 20.0
    cl_l_per_h: float | None = None
    vd_l: float | None = None
    ka_per_h: float | None = None
    n_samples: int = 3
    horizon_h: float = 24.0
    grid_step_h: float = 0.5
    sigma_prop: float = 0.2
    reference_times_h: list[float] | None = None

class SensitivityRequest(BaseModel):
    """Which parameter's uncertainty drives the predicted exposure."""
    medication_id: int | None = None
    dose_mg: float = 20.0
    cl_l_per_h: float | None = None
    vd_l: float | None = None
    ka_per_h: float | None = None
    cv_cl_pct: float | None = None
    cv_vd_pct: float | None = None
    cv_ka_pct: float = 40.0
    metric: str = 'cmax'
    horizon_h: float = 24.0
    n_base: int = 2048

class BayesianObservation(BaseModel):
    time_h: float
    concentration_ng_ml: float

class BayesianDose(BaseModel):
    time_h: float
    dose_mg: float

class BayesianPKRequest(BaseModel):
    observations: list[BayesianObservation]
    doses: list[BayesianDose]
    mu_log_cl: float
    sigma_log_cl: float
    mu_log_vd: float
    sigma_log_vd: float
    ka_per_h: float = 1.0
    bioavailability: float = 1.0
    sigma_obs: float = 0.2

def _load_regimen_data(db: Session, medication_ids: list[int]) -> dict:
    from models import CYP450Profile, Interaction, Medication
    meds = db.query(Medication).filter(Medication.id.in_(medication_ids)).all()
    med_map = {m.id: m for m in meds}
    drug_names = [med_map[mid].generic_name for mid in medication_ids if mid in med_map]
    interactions_raw = db.query(Interaction).filter(Interaction.drug_a_id.in_(medication_ids), Interaction.drug_b_id.in_(medication_ids)).all()
    interactions = []
    for ix in interactions_raw:
        a = med_map.get(ix.drug_a_id)
        b = med_map.get(ix.drug_b_id)
        if a and b:
            interactions.append({'drug_a_name': a.generic_name, 'drug_b_name': b.generic_name, 'severity': ix.severity})
    cyp_profiles = []
    drug_data = []
    for mid in medication_ids:
        med = med_map.get(mid)
        if not med:
            continue
        drug_data.append({'name': med.generic_name, 'clearance_l_per_h': float(med.clearance_l_per_h or 1.0)})
        profiles = db.query(CYP450Profile).filter(CYP450Profile.medication_id == mid).all()
        for cp in profiles:
            cyp_profiles.append({'drug_name': med.generic_name, 'enzyme': cp.enzyme, 'role': cp.role, 'potency': cp.potency or 'moderate', 'fraction_metabolized': float(cp.fraction_metabolized or 0.0)})
    return {'drug_names': drug_names, 'drug_data': drug_data, 'interactions': interactions, 'cyp_profiles': cyp_profiles}

@router.post('/optimizer/taper')
def optimize_taper(req: TaperRequest) -> dict[str, Any]:
    from services.optimal_control import TaperOptimizer
    opt = TaperOptimizer()
    plan = opt.optimize(drug_name=req.drug_name, start_dose=req.start_dose, target_dose=req.target_dose, duration_days=req.duration_days, constraints=req.constraints)
    return {'steps': [{'day': s.day, 'doses': s.doses, 'description': s.description} for s in plan.steps], 'recommendations': plan.recommendations, 'total_cost': plan.total_cost, 'risk_timeline': plan.risk_timeline}

@router.post('/simulation/stochastic')
def run_stochastic_simulation(req: SDERequest) -> dict[str, Any]:
    from services.sde_simulator import SDESimulator
    sim = SDESimulator(method=req.method, dt_hours=0.5)
    schedules = {k: [tuple(pair) for pair in v] for k, v in req.dose_schedules.items()}
    result = sim.simulate(drug_configs=req.drugs, dose_schedules=schedules, duration_days=req.duration_days, n_paths=min(req.n_paths, 500))
    return {'time_hours': result.time_hours, 'paths': result.paths, 'n_paths': result.n_paths, 'method': result.method}

@router.get('/entropy')
def get_metabolic_entropy(medication_ids: str=Query(..., description='Comma-separated medication IDs'), db: Session=Depends(get_db)) -> dict[str, Any]:
    from services.entropy_analysis import MetabolicEntropyAnalyzer
    ids = [int(x.strip()) for x in medication_ids.split(',') if x.strip()]
    if not ids:
        raise HTTPException(400, 'At least 1 medication ID required.')
    data = _load_regimen_data(db, ids)
    analyzer = MetabolicEntropyAnalyzer()
    result = analyzer.compute(data['drug_data'], data['cyp_profiles'])
    return {'cdi': result.cdi, 'entropy_bits': result.entropy_bits, 'max_entropy': result.max_entropy, 'kl_divergence': result.kl_divergence, 'load_distribution': result.load_distribution, 'dominant_enzyme': result.dominant_enzyme, 'dominant_enzyme_pct': result.dominant_enzyme_pct, 'interpretation': result.interpretation}

@router.post('/markov')
def run_markov_model(req: MarkovRequest) -> dict[str, Any]:
    from services.markov_model import PatientStateMarkovModel, STATES
    model = PatientStateMarkovModel()
    if req.initial_state not in STATES:
        raise HTTPException(400, f'Invalid state. Must be one of: {STATES}')
    result = model.compute_all(req.drug_classes, req.initial_state, req.n_weeks)
    return {'transition_matrix': result.transition_matrix, 'stationary_distribution': result.stationary_distribution, 'first_passage_times': result.first_passage_times, 'trajectory_summary': result.trajectory_summary}

@router.get('/topology')
def get_topology(medication_ids: str=Query(..., description='Comma-separated medication IDs'), db: Session=Depends(get_db)) -> dict[str, Any]:
    from services.tda_analysis import TopologicalAnalyzer
    ids = [int(x.strip()) for x in medication_ids.split(',') if x.strip()]
    if len(ids) < 2:
        raise HTTPException(400, 'At least 2 medication IDs required.')
    data = _load_regimen_data(db, ids)
    analyzer = TopologicalAnalyzer(data['drug_names'], data['interactions'])
    result = analyzer.compute_persistence()
    return {'persistence_features': result.persistence_features, 'betti_0': result.betti_0_at_threshold, 'betti_1': result.betti_1_count, 'has_feedback_loops': result.has_feedback_loops, 'total_persistence': result.total_persistence}

@router.post('/game-theory')
def run_game_theory(req: GameTheoryRequest, db: Session=Depends(get_db)) -> dict[str, Any]:
    from services.game_theory import EnzymeCompetitionGame
    data = _load_regimen_data(db, req.medication_ids)
    game = EnzymeCompetitionGame(data['drug_data'], data['cyp_profiles'])
    metrics = game.compute_all()
    return {'ideal_clearances': metrics.ideal_clearances, 'effective_clearances': metrics.effective_clearances, 'clearance_reduction_pct': metrics.clearance_reduction_pct, 'social_cost': metrics.social_cost, 'price_of_anarchy': metrics.price_of_anarchy, 'enzyme_competition_matrix': metrics.enzyme_competition_matrix, 'substitution_recommendations': metrics.substitution_recommendations}

def _run_pk_for_simulation(db: Session, simulation_id: int):
    from models import DoseSchedule, Simulation
    from services.pk_simulator import run_simulation
    from services.simulation_builder import build_config_from_dose_events
    sim = db.query(Simulation).filter(Simulation.id == simulation_id).first()
    if not sim:
        raise HTTPException(404, f'Simulation {simulation_id} not found')
    schedules_db = db.query(DoseSchedule).filter(DoseSchedule.simulation_id == simulation_id).order_by(DoseSchedule.event_day).all()
    dose_events = [{'medication_id': s.medication_id, 'event_type': s.event_type, 'event_day': s.event_day, 'dose_mg': float(s.dose_mg), 'frequency': s.frequency} for s in schedules_db]
    try:
        config = build_config_from_dose_events(db, dose_events, horizon_days=sim.horizon_days, cyp2d6_phenotype=sim.cyp2d6_phenotype, cyp2c19_phenotype=sim.cyp2c19_phenotype, smoking=bool(sim.smoking_status), patient_weight_kg=sim.patient_weight_kg)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return run_simulation(config)

def _run_pk_inline(db: Session, spec: 'InlineSimulation'):
    from services.pk_simulator import run_simulation
    from services.simulation_builder import build_config_from_dose_events
    try:
        config = build_config_from_dose_events(db, spec.dose_schedules, horizon_days=spec.horizon_days, cyp2d6_phenotype=spec.cyp2d6_phenotype, cyp2c19_phenotype=spec.cyp2c19_phenotype, smoking=spec.smoking_status, patient_weight_kg=spec.patient_weight_kg)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return run_simulation(config)

def _resolve_pk(db: Session, req):
    """Run the PK model from whichever simulation source the request carries.

    Prefers an inline spec, which is the stateless path, and falls back to a
    persisted simulation id for callers using a durable database.
    """
    spec = getattr(req, 'simulation', None)
    if spec is not None:
        return _run_pk_inline(db, spec)
    sim_id = getattr(req, 'simulation_id', None)
    if sim_id is not None:
        return _run_pk_for_simulation(db, sim_id)
    raise HTTPException(400, 'provide either `simulation` (inline spec) or `simulation_id`')

@router.post('/tissue-pde')
def run_tissue_pde(req: TissuePDERequest, db: Session=Depends(get_db)) -> dict[str, Any]:
    from services.tissue_pde import TissuePDEParams, solve_tissue_pde_for_regimen
    pk = _resolve_pk(db, req)
    concentrations_mg_l = {name: series / 1000.0 for name, series in pk.concentrations.items()}
    drug_params: dict[str, TissuePDEParams] = {}
    for name in concentrations_mg_l:
        base = TissuePDEParams.for_drug(name)
        if req.p_eff_cm_per_h and name in req.p_eff_cm_per_h:
            base = TissuePDEParams(drug_name=base.drug_name, p_eff_cm_per_h=req.p_eff_cm_per_h[name], f_unbound=base.f_unbound, d_tissue_cm2_per_h=base.d_tissue_cm2_per_h, k_e_tissue_per_h=base.k_e_tissue_per_h, slab_depth_cm=req.slab_depth_cm, n_nodes=req.n_nodes)
        if req.f_unbound and name in req.f_unbound:
            base = TissuePDEParams(drug_name=base.drug_name, p_eff_cm_per_h=base.p_eff_cm_per_h, f_unbound=req.f_unbound[name], d_tissue_cm2_per_h=base.d_tissue_cm2_per_h, k_e_tissue_per_h=base.k_e_tissue_per_h, slab_depth_cm=req.slab_depth_cm, n_nodes=req.n_nodes)
        drug_params[name] = base
    result = solve_tissue_pde_for_regimen(pk.time_hours, concentrations_mg_l, drug_params)
    per_drug: dict[str, dict[str, Any]] = {}
    for name, res in result.per_drug.items():
        per_drug[name] = {'surface_ng_ml': (res.surface_concentration * 1000.0).tolist(), 'mean_ng_ml': (res.mean_concentration * 1000.0).tolist(), 'deep_ng_ml': (res.deep_concentration * 1000.0).tolist(), 'plasma_unbound_ng_ml': (res.plasma_unbound * 1000.0).tolist(), 'time_to_80pct_h': res.time_to_80pct_h, 'p_eff_cm_per_h': drug_params[name].p_eff_cm_per_h, 'f_unbound': drug_params[name].f_unbound}
    return {'time_hours': result.time_hours.tolist(), 'x_cm': result.x_cm.tolist(), 'per_drug': per_drug}

@router.post('/receptor-occupancy')
def run_receptor_occupancy(req: ReceptorOccupancyRequest, db: Session=Depends(get_db)) -> dict[str, Any]:
    from services.receptor_occupancy import _BINDING_PROFILES, compute_regimen_occupancy
    from services.tissue_pde import _DEFAULT_F_UNBOUND
    pk = _resolve_pk(db, req)
    f_u: dict[str, float] = {}
    if req.use_f_unbound:
        for name in pk.concentrations:
            f_u[name] = _DEFAULT_F_UNBOUND.get(name.lower(), 1.0)
    occ_by_drug = compute_regimen_occupancy(pk.time_hours, pk.concentrations, fraction_unbound=f_u)
    serialized: dict[str, Any] = {}
    for name, result in occ_by_drug.items():
        trajectories = []
        for traj in result.trajectories:
            trajectories.append({'target': traj.target, 'k_d_nm': traj.k_d_nm, 'mechanism': traj.mechanism, 'occupancy_pct': traj.occupancy_pct.tolist(), 'peak_occupancy_pct': traj.peak_occupancy_pct, 'trough_occupancy_pct': traj.trough_occupancy_pct, 'time_to_threshold_h': traj.time_to_threshold_h, 'steady_state_label': traj.steady_state_label})
        serialized[name] = {'mw_g_per_mol': result.mw_g_per_mol, 'has_profile': name.lower() in _BINDING_PROFILES, 'trajectories': trajectories}
    return {'time_hours': pk.time_hours.tolist(), 'per_drug': serialized}

@router.post('/hepatic-extraction')
def run_hepatic_extraction(req: HepaticExtractionRequest, db: Session=Depends(get_db)) -> dict[str, Any]:
    from models import CYP450Profile, Medication
    from services.hepatic_extraction import EnzymePathway, compute_regimen_hepatic_extraction
    from services.tissue_pde import _DEFAULT_F_UNBOUND
    if not req.medication_ids:
        raise HTTPException(400, 'medication_ids must not be empty')
    meds = {m.id: m for m in db.query(Medication).filter(Medication.id.in_(req.medication_ids)).all()}
    if not meds:
        raise HTTPException(404, 'None of the requested medications were found')
    drug_pathways: dict[str, list[EnzymePathway]] = {}
    drug_inhibitor_targets: dict[str, list[tuple[str, float]]] = {}
    f_unbound: dict[str, float] = {}
    from services.pk_simulator import _MW_APPROX
    for mid in req.medication_ids:
        med = meds.get(mid)
        if med is None:
            continue
        gn = (med.generic_name or '').lower()
        mw = _MW_APPROX.get(gn, 350.0)
        cl_total = float(med.clearance_l_per_h or 5.0)
        profiles = db.query(CYP450Profile).filter(CYP450Profile.medication_id == mid).all()
        pathways: list[EnzymePathway] = []
        inh_targets: list[tuple[str, float]] = []
        for cp in profiles:
            if cp.role == 'substrate' and cp.km_nm:
                km_mg_l = float(cp.km_nm) * mw / 1000000.0
                vmax = cl_total * km_mg_l
                pathways.append(EnzymePathway(enzyme=cp.enzyme, vmax_mg_per_h=vmax, km_mg_per_l=km_mg_l))
            elif cp.role == 'inhibitor' and cp.ki_nm:
                ki_mg_l = float(cp.ki_nm) * mw / 1000000.0
                inh_targets.append((cp.enzyme, ki_mg_l))
        if pathways:
            drug_pathways[med.generic_name] = pathways
        if inh_targets:
            drug_inhibitor_targets[med.generic_name] = inh_targets
        f_unbound[med.generic_name] = _DEFAULT_F_UNBOUND.get(gn, 0.2)
    if not drug_pathways:
        raise HTTPException(400, 'No drug has enzyme-substrate pathways on file; nothing to compute')
    inhibitor_plasma: dict[str, float] = {}
    if req.simulation_id is not None or req.simulation is not None:
        pk = _resolve_pk(db, req)
        for name, series in pk.concentrations.items():
            if len(series) == 0:
                continue
            horizon_h = float(pk.time_hours[-1]) if pk.time_hours.size else 24.0
            tail_mask = pk.time_hours >= horizon_h - 24.0
            tail = series[tail_mask] if tail_mask.any() else series
            inhibitor_plasma[name] = float(tail.mean()) / 1000.0
    regimen = compute_regimen_hepatic_extraction(drug_pathways, f_unbound, inhibitor_plasma_mg_per_l=inhibitor_plasma, drug_inhibitor_targets=drug_inhibitor_targets, q_hepatic_l_per_h=req.q_hepatic_l_per_h)
    serialized = {}
    for name, res in regimen.per_drug.items():
        serialized[name] = {'cl_intrinsic_l_per_h': res.cl_intrinsic_l_per_h, 'cl_intrinsic_inhibited_l_per_h': res.cl_intrinsic_inhibited_l_per_h, 'cl_hepatic_l_per_h': res.cl_hepatic_l_per_h, 'cl_hepatic_inhibited_l_per_h': res.cl_hepatic_inhibited_l_per_h, 'extraction_ratio': res.extraction_ratio, 'extraction_ratio_inhibited': res.extraction_ratio_inhibited, 'first_pass_fraction': res.first_pass_fraction, 'first_pass_fraction_inhibited': res.first_pass_fraction_inhibited, 'pathway_contributions_pct': res.pathway_contributions, 'classification': res.classification, 'f_unbound': res.f_unbound}
    return {'q_hepatic_l_per_h': req.q_hepatic_l_per_h, 'used_simulation_id': req.simulation_id, 'per_drug': serialized}

@router.post('/bayesian-pk')
def run_bayesian_pk(req: BayesianPKRequest) -> dict[str, Any]:
    from services.bayesian_pk import DoseHistory, Observation, PopulationPrior, estimate_individual_pk
    if not req.observations:
        raise HTTPException(400, 'At least one observation is required')
    if not req.doses:
        raise HTTPException(400, 'At least one dose must be supplied')
    prior = PopulationPrior(mu_log_cl=req.mu_log_cl, sigma_log_cl=req.sigma_log_cl, mu_log_vd=req.mu_log_vd, sigma_log_vd=req.sigma_log_vd, ka_per_h=req.ka_per_h, bioavailability=req.bioavailability, sigma_obs=req.sigma_obs)
    obs = [Observation(time_h=o.time_h, concentration_ng_ml=o.concentration_ng_ml) for o in req.observations]
    doses = [DoseHistory(time_h=d.time_h, dose_mg=d.dose_mg) for d in req.doses]
    try:
        result = estimate_individual_pk(obs, doses, prior)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {'map_cl_l_per_h': result.map_cl_l_per_h, 'map_vd_l': result.map_vd_l, 'ci95_cl_l_per_h': list(result.ci95_cl_l_per_h), 'ci95_vd_l': list(result.ci95_vd_l), 'posterior_cov_log': result.posterior_cov_log, 'n_observations': result.n_observations, 'converged': result.converged, 'prediction_time_hours': result.prediction_time_hours.tolist(), 'prediction_ng_ml': result.prediction_ng_ml.tolist(), 'prediction_ci_low_ng_ml': result.prediction_ci_low_ng_ml.tolist(), 'prediction_ci_high_ng_ml': result.prediction_ci_high_ng_ml.tolist()}

# Roughly the per-iteration cost of one forward simulation, in seconds per
# simulated day, measured on the deployment target. Used to keep a request
# inside the platform's function timeout instead of letting it die at 60s.
_MC_SECONDS_PER_ITER_DAY = 0.008
_MC_TIME_BUDGET_S = 25.0


def _monte_carlo_iteration_cap(horizon_days: int) -> int:
    """Largest iteration count that should finish inside the time budget."""
    per_iter = max(_MC_SECONDS_PER_ITER_DAY * max(horizon_days, 1), 1e-6)
    return max(25, min(1000, int(_MC_TIME_BUDGET_S / per_iter)))


@router.post('/monte-carlo')
def run_monte_carlo(req: MonteCarloRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Population variability envelope for a regimen.

    Resamples clearance, volume of distribution and absorption rate per virtual
    subject from lognormal inter-individual distributions, runs the full PK
    model for each, and reports percentile bands plus the probability of
    sitting below, inside or above the therapeutic window at each time point.
    """
    from models import Medication
    from services.monte_carlo import MonteCarloSimulator
    from services.simulation_builder import build_config_from_dose_events

    spec = req.simulation
    if spec is not None:
        events = spec.dose_schedules
        horizon = spec.horizon_days
        kwargs = dict(
            horizon_days=spec.horizon_days,
            cyp2d6_phenotype=spec.cyp2d6_phenotype,
            cyp2c19_phenotype=spec.cyp2c19_phenotype,
            smoking=spec.smoking_status,
            patient_weight_kg=spec.patient_weight_kg,
        )
    elif req.simulation_id is not None:
        from models import DoseSchedule, Simulation
        sim = db.query(Simulation).filter(Simulation.id == req.simulation_id).first()
        if not sim:
            raise HTTPException(404, f'Simulation {req.simulation_id} not found')
        rows = db.query(DoseSchedule).filter(
            DoseSchedule.simulation_id == req.simulation_id
        ).order_by(DoseSchedule.event_day).all()
        events = [
            {'medication_id': s.medication_id, 'event_type': s.event_type,
             'event_day': s.event_day, 'dose_mg': float(s.dose_mg),
             'frequency': s.frequency}
            for s in rows
        ]
        horizon = sim.horizon_days or 56
        kwargs = dict(
            horizon_days=sim.horizon_days,
            cyp2d6_phenotype=sim.cyp2d6_phenotype,
            cyp2c19_phenotype=sim.cyp2c19_phenotype,
            smoking=bool(sim.smoking_status),
            patient_weight_kg=sim.patient_weight_kg,
        )
    else:
        raise HTTPException(400, 'provide either `simulation` (inline spec) or `simulation_id`')

    try:
        config = build_config_from_dose_events(db, events, **kwargs)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    # Therapeutic windows come from the curated formulary, so the probability
    # bands are anchored to published ranges rather than invented ones.
    med_ids = list({int(e['medication_id']) for e in events})
    therapeutic: dict[str, tuple[float, float]] = {}
    toxic: dict[str, float] = {}
    for m in db.query(Medication).filter(Medication.id.in_(med_ids)).all():
        if m.therapeutic_min_ng_ml is not None and m.therapeutic_max_ng_ml is not None:
            therapeutic[m.generic_name] = (
                float(m.therapeutic_min_ng_ml), float(m.therapeutic_max_ng_ml)
            )
        if m.toxic_threshold_ng_ml is not None:
            toxic[m.generic_name] = float(m.toxic_threshold_ng_ml)

    cap = _monte_carlo_iteration_cap(horizon or 56)
    requested = max(1, int(req.n_iterations))
    n = min(requested, cap)

    result = MonteCarloSimulator(n_iterations=n, seed=req.seed).run(
        config, therapeutic_ranges=therapeutic, toxic_thresholds=toxic
    )
    return {
        'time_hours': result.time_hours,
        'drug_stats': result.drug_stats,
        'n_iterations': n,
        'requested_iterations': requested,
        'iteration_cap': cap,
        'capped': n < requested,
        'therapeutic_ranges': {k: list(v) for k, v in therapeutic.items()},
        'toxic_thresholds': toxic,
    }


@router.post('/optimal-design')
def run_optimal_design(req: OptimalDesignRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    """D-optimal therapeutic drug monitoring schedule.

    Answers the question that precedes Bayesian estimation: given this drug,
    when should the levels actually be drawn? Compares the optimal schedule
    against a reference (trough-only by default, which is what routine TDM
    usually collects).
    """
    from models import Medication
    from services.optimal_design import optimize_sampling_times

    cl, vd, ka, name = req.cl_l_per_h, req.vd_l, req.ka_per_h, None
    if req.medication_id is not None:
        med = db.query(Medication).filter(Medication.id == req.medication_id).first()
        if not med:
            raise HTTPException(404, f'Medication {req.medication_id} not found')
        name = med.generic_name
        cl = cl if cl is not None else float(med.clearance_l_per_h or 0) or None
        vd = vd if vd is not None else float(med.volume_of_distribution_l or 0) or None
        ka = ka if ka is not None else float(med.absorption_rate_constant or 0) or None

    missing = [n for n, v in (('cl_l_per_h', cl), ('vd_l', vd), ('ka_per_h', ka)) if not v or v <= 0]
    if missing:
        raise HTTPException(
            400,
            f'missing positive PK parameters {missing}; supply them directly or '
            'choose a medication_id whose formulary entry has them',
        )

    # Trough-only is the default comparator because it is the schedule the
    # optimal design is meant to argue against.
    reference = req.reference_times_h or [req.horizon_h] * max(req.n_samples, 1)

    try:
        res = optimize_sampling_times(
            dose_mg=req.dose_mg, cl=cl, vd=vd, ka=ka,
            n_samples=req.n_samples, horizon_h=req.horizon_h,
            grid_step_h=req.grid_step_h, sigma_prop=req.sigma_prop,
            reference_times_h=reference,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    return {
        'drug_name': name,
        'pk_parameters': {'cl_l_per_h': cl, 'vd_l': vd, 'ka_per_h': ka, 'dose_mg': req.dose_mg},
        'optimal_times_h': res.sampling_times_h,
        'reference_times_h': res.reference_times_h,
        'd_efficiency_of_reference_pct': res.d_efficiency_vs_reference_pct,
        'log_det_fim': res.log_det_fim,
        'd_criterion': res.d_criterion,
        'fisher_information': res.fisher_information,
        'parameter_names': res.parameter_names,
        'relative_standard_errors_pct': res.relative_standard_errors_pct,
        'correlation_matrix': res.correlation_matrix,
        'condition_number': res.condition_number,
        'grid_step_h': res.grid_step_h,
    }


_SENSITIVITY_METRICS = ('cmax', 'auc', 'trough', 'tmax')


@router.post('/sensitivity')
def run_sensitivity(req: SensitivityRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Sobol global sensitivity of exposure to PK parameter uncertainty.

    Monte Carlo says how wide the prediction is; this says which parameter is
    responsible, and how much of that responsibility is carried through
    interactions rather than alone.
    """
    import numpy as np

    from models import Medication
    from services.optimal_design import concentration
    from services.sensitivity_analysis import sobol_indices

    metric = req.metric.lower()
    if metric not in _SENSITIVITY_METRICS:
        raise HTTPException(400, f'metric must be one of {_SENSITIVITY_METRICS}')

    cl, vd, ka = req.cl_l_per_h, req.vd_l, req.ka_per_h
    cv_cl, cv_vd, name = req.cv_cl_pct, req.cv_vd_pct, None
    if req.medication_id is not None:
        med = db.query(Medication).filter(Medication.id == req.medication_id).first()
        if not med:
            raise HTTPException(404, f'Medication {req.medication_id} not found')
        name = med.generic_name
        cl = cl if cl is not None else float(med.clearance_l_per_h or 0) or None
        vd = vd if vd is not None else float(med.volume_of_distribution_l or 0) or None
        ka = ka if ka is not None else float(med.absorption_rate_constant or 0) or None
        cv_cl = cv_cl if cv_cl is not None else float(med.cl_cv_pct or 0) or None
        cv_vd = cv_vd if cv_vd is not None else float(med.vd_cv_pct or 0) or None

    missing = [n for n, v in (('cl_l_per_h', cl), ('vd_l', vd), ('ka_per_h', ka)) if not v or v <= 0]
    if missing:
        raise HTTPException(400, f'missing positive PK parameters {missing}')

    cv_cl = cv_cl or 35.0
    cv_vd = cv_vd or 25.0

    def fold(cv_pct: float) -> float:
        """95% fold-range of a lognormal with the given coefficient of variation."""
        sigma = float(np.sqrt(np.log(1.0 + (cv_pct / 100.0) ** 2)))
        return float(np.exp(1.96 * sigma))

    point = {'CL': cl, 'Vd': vd, 'ka': ka}
    cvs = {'CL': cv_cl, 'Vd': cv_vd, 'ka': req.cv_ka_pct}
    names = ['CL', 'Vd', 'ka']
    bounds = [(point[n] / fold(cvs[n]), point[n] * fold(cvs[n])) for n in names]

    t_grid = np.linspace(0.0, req.horizon_h, 241)

    def model(X: np.ndarray) -> np.ndarray:
        # Evaluated for every sampled parameter set at once. Sobol needs
        # n_base*(k+2) evaluations, so a Python loop here is the difference
        # between a fast request and a slow one.
        cl_s, vd_s, ka_s = X[:, 0:1], X[:, 1:2], X[:, 2:3]
        ke = cl_s / vd_s
        gap = ka_s - ke
        gap = np.where(np.abs(gap) < 1e-9, 1e-9, gap)
        tt = t_grid[None, :]
        c = (req.dose_mg * ka_s) / (vd_s * gap) * (np.exp(-ke * tt) - np.exp(-ka_s * tt))
        if metric == 'cmax':
            return c.max(axis=1)
        if metric == 'auc':
            return np.trapezoid(c, t_grid, axis=1)
        if metric == 'trough':
            return c[:, -1]
        return t_grid[np.argmax(c, axis=1)]

    n_base = int(np.clip(req.n_base, 128, 16384))
    res = sobol_indices(model, names, bounds, n_base=n_base, log_scale=True)

    ranked = sorted(names, key=lambda n: res.total_order[n], reverse=True)
    return {
        'drug_name': name,
        'metric': metric,
        'pk_parameters': {'cl_l_per_h': cl, 'vd_l': vd, 'ka_per_h': ka, 'dose_mg': req.dose_mg},
        'coefficients_of_variation_pct': cvs,
        'sampled_bounds': {n: list(b) for n, b in zip(names, bounds)},
        'parameter_names': res.parameter_names,
        'first_order': res.first_order,
        'total_order': res.total_order,
        'interaction': res.interaction,
        'first_order_ci95': {k: list(v) for k, v in res.first_order_ci95.items()},
        'total_order_ci95': {k: list(v) for k, v in res.total_order_ci95.items()},
        'output_mean': res.output_mean,
        'output_variance': res.output_variance,
        'sum_first_order': res.sum_first_order,
        'dominant_parameter': ranked[0],
        'ranking': ranked,
        'n_base_samples': res.n_base_samples,
        'n_model_evaluations': res.n_model_evaluations,
        'converged': res.converged,
        'warnings': res.warnings,
    }
