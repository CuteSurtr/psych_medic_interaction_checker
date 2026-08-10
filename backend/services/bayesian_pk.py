from __future__ import annotations
import numpy as np
from dataclasses import dataclass, field
from scipy.optimize import minimize

@dataclass
class DoseHistory:
    time_h: float
    dose_mg: float

@dataclass
class Observation:
    time_h: float
    concentration_ng_ml: float

@dataclass
class PopulationPrior:
    mu_log_cl: float
    sigma_log_cl: float
    mu_log_vd: float
    sigma_log_vd: float
    ka_per_h: float = 1.0
    bioavailability: float = 1.0
    sigma_obs: float = 0.2

@dataclass
class BayesianPKResult:
    map_cl_l_per_h: float
    map_vd_l: float
    posterior_mean_log: list[float]
    posterior_cov_log: list[list[float]]
    ci95_cl_l_per_h: tuple[float, float]
    ci95_vd_l: tuple[float, float]
    n_observations: int
    converged: bool
    prediction_time_hours: np.ndarray = field(default_factory=lambda: np.array([]))
    prediction_ng_ml: np.ndarray = field(default_factory=lambda: np.array([]))
    prediction_ci_low_ng_ml: np.ndarray = field(default_factory=lambda: np.array([]))
    prediction_ci_high_ng_ml: np.ndarray = field(default_factory=lambda: np.array([]))

def predict_concentration(times_h: np.ndarray, doses: list[DoseHistory], cl_l_per_h: float, vd_l: float, ka_per_h: float, bioavailability: float) -> np.ndarray:
    times = np.asarray(times_h, dtype=float)
    if cl_l_per_h <= 0.0 or vd_l <= 0.0 or ka_per_h <= 0.0:
        return np.zeros_like(times)
    k_el = cl_l_per_h / vd_l
    if abs(ka_per_h - k_el) < 1e-09:
        ka_per_h = k_el * 1.001
    conc_mg_l = np.zeros_like(times)
    prefactor = bioavailability * ka_per_h / (vd_l * (ka_per_h - k_el))
    for d in doses:
        dt = times - d.time_h
        active = dt >= 0.0
        if not np.any(active):
            continue
        dt_active = dt[active]
        contribution = d.dose_mg * prefactor * (np.exp(-k_el * dt_active) - np.exp(-ka_per_h * dt_active))
        conc_mg_l[active] += contribution
    conc_mg_l = np.maximum(conc_mg_l, 0.0)
    return conc_mg_l * 1000.0

def _log_predictions(theta: np.ndarray, times_h: np.ndarray, doses: list[DoseHistory], ka_per_h: float, bioavailability: float) -> np.ndarray:
    cl = float(np.exp(theta[0]))
    vd = float(np.exp(theta[1]))
    pred = predict_concentration(times_h, doses, cl, vd, ka_per_h, bioavailability)
    return np.log(np.maximum(pred, 0.0001))

def _neg_log_posterior(theta: np.ndarray, observations: list[Observation], doses: list[DoseHistory], prior: PopulationPrior) -> float:
    z_cl = (theta[0] - prior.mu_log_cl) / prior.sigma_log_cl
    z_vd = (theta[1] - prior.mu_log_vd) / prior.sigma_log_vd
    prior_term = 0.5 * (z_cl * z_cl + z_vd * z_vd)
    if not observations:
        return prior_term
    t_obs = np.array([o.time_h for o in observations])
    y_obs = np.array([max(o.concentration_ng_ml, 0.0001) for o in observations])
    log_pred = _log_predictions(theta, t_obs, doses, prior.ka_per_h, prior.bioavailability)
    resid = np.log(y_obs) - log_pred
    lik_term = 0.5 * np.sum(resid * resid) / (prior.sigma_obs * prior.sigma_obs)
    return prior_term + lik_term

def estimate_individual_pk(observations: list[Observation], doses: list[DoseHistory], prior: PopulationPrior, prediction_time_hours: np.ndarray | None=None) -> BayesianPKResult:
    if prior.sigma_log_cl <= 0.0 or prior.sigma_log_vd <= 0.0 or prior.sigma_obs <= 0.0:
        raise ValueError('Prior and observation SDs must be strictly positive')
    theta0 = np.array([prior.mu_log_cl, prior.mu_log_vd])
    result = minimize(_neg_log_posterior, theta0, args=(observations, doses, prior), method='BFGS', options={'gtol': 1e-06, 'disp': False})
    theta_map = result.x
    cov = np.asarray(result.hess_inv)
    cov = 0.5 * (cov + cov.T)
    eigvals = np.linalg.eigvalsh(cov)
    if np.any(eigvals <= 0.0):
        cov = cov + np.eye(2) * (abs(float(eigvals.min())) + 1e-06)
    cl_map = float(np.exp(theta_map[0]))
    vd_map = float(np.exp(theta_map[1]))
    sd_log_cl = float(np.sqrt(cov[0, 0]))
    sd_log_vd = float(np.sqrt(cov[1, 1]))
    ci95_cl = (float(np.exp(theta_map[0] - 1.96 * sd_log_cl)), float(np.exp(theta_map[0] + 1.96 * sd_log_cl)))
    ci95_vd = (float(np.exp(theta_map[1] - 1.96 * sd_log_vd)), float(np.exp(theta_map[1] + 1.96 * sd_log_vd)))
    if prediction_time_hours is None and observations:
        t_max = max((o.time_h for o in observations)) * 1.5
        prediction_time_hours = np.linspace(0.0, max(t_max, 24.0), 201)
    elif prediction_time_hours is None:
        prediction_time_hours = np.linspace(0.0, 24.0, 25)
    prediction_time_hours = np.asarray(prediction_time_hours, dtype=float)
    pred_mean = predict_concentration(prediction_time_hours, doses, cl_map, vd_map, prior.ka_per_h, prior.bioavailability)
    rng = np.random.default_rng(seed=0)
    draws = rng.multivariate_normal(theta_map, cov, size=500)
    all_preds = np.array([predict_concentration(prediction_time_hours, doses, float(np.exp(th[0])), float(np.exp(th[1])), prior.ka_per_h, prior.bioavailability) for th in draws])
    ci_low = np.percentile(all_preds, 2.5, axis=0)
    ci_high = np.percentile(all_preds, 97.5, axis=0)
    return BayesianPKResult(map_cl_l_per_h=cl_map, map_vd_l=vd_map, posterior_mean_log=theta_map.tolist(), posterior_cov_log=cov.tolist(), ci95_cl_l_per_h=ci95_cl, ci95_vd_l=ci95_vd, n_observations=len(observations), converged=bool(result.success), prediction_time_hours=prediction_time_hours, prediction_ng_ml=pred_mean, prediction_ci_low_ng_ml=ci_low, prediction_ci_high_ng_ml=ci_high)
