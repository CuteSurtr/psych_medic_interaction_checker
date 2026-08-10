"""Treatment MDP: policy iteration, value iteration and optimality guarantees.

The MDP reuses the transition structure of the existing patient-state chain, so
what needs pinning here is the decision layer: that the two solvers agree, that
the returned value function actually satisfies the Bellman optimality equation,
and that the optimal policy dominates every constant policy state by state.
"""

import numpy as np
import pytest
from fastapi.testclient import TestClient

from main import app
from services.markov_model import STATES
from services.treatment_mdp import (
    ACTIONS,
    build_action_transitions,
    build_reward_matrix,
    policy_evaluation,
    policy_iteration,
    solve_treatment_mdp,
    value_iteration,
)

GAMMA = 0.95


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def mdp():
    return build_action_transitions(ACTIONS), build_reward_matrix(ACTIONS)


# --------------------------------------------------------------- transitions


def test_every_action_gives_a_stochastic_matrix(mdp):
    P, _ = mdp
    for a, M in P.items():
        assert M.shape == (len(STATES), len(STATES))
        assert np.allclose(M.sum(axis=1), 1.0), a
        assert (M >= 0).all(), a


def test_actions_produce_distinct_transition_models(mdp):
    P, _ = mdp
    assert not np.allclose(P["none"], P["SSRI"])


def test_reward_matrix_penalises_treatment_burden(mdp):
    _, R = mdp
    j_none = ACTIONS.index("none")
    j_apz = ACTIONS.index("atypical_antipsychotic")
    assert (R[:, j_apz] < R[:, j_none]).all()


# ---------------------------------------------------------------- optimality


def test_value_function_satisfies_bellman_optimality(mdp):
    """The defining property: V(s) = max_a [ R(s,a) + gamma * sum_s' P V(s') ]."""
    P, R = mdp
    V, _, _, converged = policy_iteration(P, R, ACTIONS, GAMMA)
    assert converged
    stacked = np.stack([P[a] for a in ACTIONS])
    Q = R + GAMMA * np.einsum("asx,x->sa", stacked, V)
    assert np.allclose(V, Q.max(axis=1), atol=1e-8)


def test_policy_is_greedy_with_respect_to_its_own_value(mdp):
    P, R = mdp
    V, policy, _, _ = policy_iteration(P, R, ACTIONS, GAMMA)
    stacked = np.stack([P[a] for a in ACTIONS])
    Q = R + GAMMA * np.einsum("asx,x->sa", stacked, V)
    assert np.array_equal(policy, Q.argmax(axis=1))


def test_two_solvers_reach_the_same_fixed_point(mdp):
    """Independent routes to the same unique solution; disagreement would mean
    one of them is wrong."""
    P, R = mdp
    V_pi, pol_pi, _, _ = policy_iteration(P, R, ACTIONS, GAMMA)
    V_vi, pol_vi, _, converged = value_iteration(P, R, ACTIONS, GAMMA)
    assert converged
    assert np.allclose(V_pi, V_vi, atol=1e-6)
    assert np.array_equal(pol_pi, pol_vi)


def test_optimal_policy_dominates_every_constant_policy_state_by_state(mdp):
    P, R = mdp
    V_star, _, _, _ = policy_iteration(P, R, ACTIONS, GAMMA)
    for j, a in enumerate(ACTIONS):
        V_fixed = policy_evaluation(np.full(len(STATES), j), P, R, ACTIONS, GAMMA)
        assert (V_star >= V_fixed - 1e-8).all(), f"{a} beat the optimum somewhere"


def test_policy_iteration_terminates_quickly(mdp):
    """Exact evaluation over finitely many policies terminates, rather than
    only converging asymptotically."""
    P, R = mdp
    _, _, n_iter, converged = policy_iteration(P, R, ACTIONS, GAMMA)
    assert converged and n_iter <= 10


# ----------------------------------------------------------------- behaviour


def test_raising_a_state_reward_raises_its_value():
    base = solve_treatment_mdp(gamma=GAMMA)
    bumped = solve_treatment_mdp(gamma=GAMMA, state_rewards={"Remission": 50.0})
    assert bumped.value_function["Remission"] > base.value_function["Remission"]


def test_making_an_action_cheaper_never_makes_it_less_used():
    costly = solve_treatment_mdp(gamma=GAMMA, action_costs={"atypical_antipsychotic": 50.0})
    free = solve_treatment_mdp(gamma=GAMMA, action_costs={"atypical_antipsychotic": 0.0})
    n_costly = sum(1 for a in costly.policy.values() if a == "atypical_antipsychotic")
    n_free = sum(1 for a in free.policy.values() if a == "atypical_antipsychotic")
    assert n_free >= n_costly


def test_prohibitive_costs_drive_the_policy_to_watchful_waiting():
    res = solve_treatment_mdp(
        gamma=GAMMA, action_costs={a: 1000.0 for a in ACTIONS if a != "none"}
    )
    assert set(res.policy.values()) == {"none"}


def test_larger_discount_lengthens_the_effective_horizon():
    near = solve_treatment_mdp(gamma=0.5)
    far = solve_treatment_mdp(gamma=0.99)
    assert abs(np.mean(list(far.value_function.values()))) > abs(
        np.mean(list(near.value_function.values()))
    )


def test_state_dependent_policy_beats_the_best_constant_one():
    res = solve_treatment_mdp(gamma=GAMMA)
    assert res.advantage_over_best_fixed > 0
    assert res.best_fixed_action in ACTIONS


def test_solvers_agree_across_a_range_of_discounts():
    for gamma in (0.5, 0.8, 0.95, 0.99):
        assert solve_treatment_mdp(gamma=gamma).value_iteration_agrees, gamma


def test_invalid_discount_is_rejected():
    for bad in (0.0, 1.0, -0.5, 1.5):
        with pytest.raises(ValueError):
            solve_treatment_mdp(gamma=bad)


def test_unknown_action_is_rejected():
    with pytest.raises(ValueError):
        solve_treatment_mdp(actions=["none", "not_a_drug_class"])


# ------------------------------------------------------------------ endpoint


def test_endpoint_returns_a_policy_for_every_state(client):
    r = client.post("/api/advanced/treatment-policy", json={"discount": 0.95})
    assert r.status_code == 200
    body = r.json()
    assert set(body["policy"]) == set(STATES)
    assert all(a in body["actions"] for a in body["policy"].values())
    assert body["converged"] and body["value_iteration_agrees"]


def test_endpoint_reports_the_gain_over_a_constant_regimen(client):
    body = client.post("/api/advanced/treatment-policy", json={}).json()
    assert body["advantage_over_best_constant"] > 0
    assert body["best_constant_action"] in body["constant_policy_values"]


def test_endpoint_rejects_a_bad_discount(client):
    assert client.post(
        "/api/advanced/treatment-policy", json={"discount": 1.0}
    ).status_code == 400
