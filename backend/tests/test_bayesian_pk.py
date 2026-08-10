from __future__ import annotations
import math
import numpy as np
import pytest
from services.bayesian_pk import DoseHistory, Observation, PopulationPrior, estimate_individual_pk, predict_concentration

def _default_prior() -> PopulationPrior:
    return PopulationPrior(mu_log_cl=math.log(5.0), sigma_log_cl=0.3, mu_log_vd=math.log(50.0), sigma_log_vd=0.3, ka_per_h=1.0, bioavailability=0.8, sigma_obs=0.2)

class TestBatemanModel:

    def test_peak_time_matches_analytical(self):
        cl, vd, ka, f = (5.0, 50.0, 1.0, 1.0)
        k_el = cl / vd
        t_max_expected = math.log(ka / k_el) / (ka - k_el)
        t = np.linspace(0.0, 48.0, 481)
        doses = [DoseHistory(time_h=0.0, dose_mg=100.0)]
        conc = predict_concentration(t, doses, cl, vd, ka, f)
        t_max_sim = t[int(np.argmax(conc))]
        assert math.isclose(t_max_sim, t_max_expected, rel_tol=0.05)

    def test_zero_before_first_dose(self):
        t = np.linspace(-5.0, 10.0, 31)
        doses = [DoseHistory(time_h=0.0, dose_mg=100.0)]
        conc = predict_concentration(t, doses, 5.0, 50.0, 1.0, 1.0)
        assert np.all(conc[t < 0] == 0.0)

    def test_linear_superposition(self):
        cl, vd, ka, f = (5.0, 50.0, 1.0, 1.0)
        t = np.linspace(0.0, 200.0, 2001)
        single = predict_concentration(t, [DoseHistory(0.0, 100.0)], cl, vd, ka, f)
        double = predict_concentration(t, [DoseHistory(0.0, 100.0), DoseHistory(100.0, 100.0)], cl, vd, ka, f)
        auc_single = np.trapezoid(single, t)
        auc_double = np.trapezoid(double, t)
        assert math.isclose(auc_double, 2.0 * auc_single, rel_tol=0.001)

class TestMAPWithoutObservations:

    def test_map_equals_prior_mean_with_no_obs(self):
        prior = _default_prior()
        doses = [DoseHistory(time_h=0.0, dose_mg=20.0)]
        result = estimate_individual_pk([], doses, prior)
        assert math.isclose(result.map_cl_l_per_h, math.exp(prior.mu_log_cl), rel_tol=0.0001)
        assert math.isclose(result.map_vd_l, math.exp(prior.mu_log_vd), rel_tol=0.0001)

class TestMAPWithObservations:

    def test_observations_shift_map_toward_data(self):
        prior = _default_prior()
        doses = [DoseHistory(time_h=0.0, dose_mg=100.0)]
        t_obs = np.array([2.0, 6.0, 12.0, 24.0])
        true_conc = predict_concentration(t_obs, doses, cl_l_per_h=10.0, vd_l=50.0, ka_per_h=prior.ka_per_h, bioavailability=prior.bioavailability)
        obs = [Observation(t, float(c)) for t, c in zip(t_obs, true_conc)]
        result = estimate_individual_pk(obs, doses, prior)
        assert result.map_cl_l_per_h > math.exp(prior.mu_log_cl) * 1.1

    def test_posterior_sd_smaller_than_prior_sd(self):
        prior = _default_prior()
        doses = [DoseHistory(0.0, 100.0)]
        t_obs = np.linspace(1.0, 48.0, 10)
        true_conc = predict_concentration(t_obs, doses, 6.0, 55.0, prior.ka_per_h, prior.bioavailability)
        obs = [Observation(t, float(c)) for t, c in zip(t_obs, true_conc)]
        result = estimate_individual_pk(obs, doses, prior)
        sd_log_cl = math.sqrt(result.posterior_cov_log[0][0])
        sd_log_vd = math.sqrt(result.posterior_cov_log[1][1])
        assert sd_log_cl < prior.sigma_log_cl
        assert sd_log_vd < prior.sigma_log_vd

    def test_ci_brackets_map(self):
        prior = _default_prior()
        doses = [DoseHistory(0.0, 100.0)]
        t_obs = np.array([4.0, 12.0, 24.0])
        true_conc = predict_concentration(t_obs, doses, 5.0, 50.0, prior.ka_per_h, prior.bioavailability)
        obs = [Observation(t, float(c)) for t, c in zip(t_obs, true_conc)]
        result = estimate_individual_pk(obs, doses, prior)
        lo, hi = result.ci95_cl_l_per_h
        assert lo < result.map_cl_l_per_h < hi
        lo_v, hi_v = result.ci95_vd_l
        assert lo_v < result.map_vd_l < hi_v

class TestPredictiveOutput:

    def test_predictive_shape_and_envelope(self):
        prior = _default_prior()
        doses = [DoseHistory(0.0, 100.0)]
        t_obs = np.array([4.0, 12.0, 24.0])
        true_conc = predict_concentration(t_obs, doses, 5.0, 50.0, prior.ka_per_h, prior.bioavailability)
        obs = [Observation(t, float(c)) for t, c in zip(t_obs, true_conc)]
        t_pred = np.linspace(0.0, 72.0, 73)
        result = estimate_individual_pk(obs, doses, prior, prediction_time_hours=t_pred)
        assert result.prediction_ng_ml.shape == t_pred.shape
        assert np.all(result.prediction_ci_low_ng_ml <= result.prediction_ng_ml + 1e-09)
        assert np.all(result.prediction_ci_high_ng_ml >= result.prediction_ng_ml - 1e-09)

    def test_converges(self):
        prior = _default_prior()
        doses = [DoseHistory(0.0, 100.0)]
        obs = [Observation(12.0, 2000.0)]
        result = estimate_individual_pk(obs, doses, prior)
        assert result.converged

class TestValidation:

    def test_rejects_zero_sigma(self):
        doses = [DoseHistory(0.0, 50.0)]
        with pytest.raises(ValueError):
            estimate_individual_pk([Observation(2.0, 500.0)], doses, PopulationPrior(mu_log_cl=math.log(5.0), sigma_log_cl=0.0, mu_log_vd=math.log(50.0), sigma_log_vd=0.3))
