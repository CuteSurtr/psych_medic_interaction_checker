"""Treatment policy as a Markov decision process.

The Markov chain module is descriptive: given a fixed regimen, where does the
patient end up? This module makes it prescriptive. Adding a choice of action at
each state and a reward turns the same transition structure into an MDP, and
solving it yields a *policy* - which class to use in which clinical state -
rather than a prediction for one fixed regimen.

The transition model is reused unchanged from `markov_model`, so the MDP
inherits whatever the chain already encodes about drug-class effects. Only the
decision layer is new.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from services.markov_model import DRUG_CLASS_EFFECTS, IDX, STATES, PatientStateMarkovModel

# "none" is watchful waiting: no drug effect applied to the baseline chain. It
# has to be available, otherwise the optimal policy cannot ever be "do nothing",
# which is a real clinical answer in remission.
ACTIONS: list[str] = ["none"] + sorted(DRUG_CLASS_EFFECTS.keys())

# Weekly reward for occupying a state. The ordering is the clinically
# meaningful part; the magnitudes set how much short-term risk is worth
# tolerating for a better steady state.
DEFAULT_STATE_REWARDS: dict[str, float] = {
    "Remission": 10.0,
    "Stable": 5.0,
    "Partial Response": 1.0,
    "Relapse": -5.0,
    "Adverse Event": -8.0,
    "Hospitalized": -20.0,
}

# Per-week burden of being on each option: monitoring, side-effect load and
# tolerability. Without this the optimiser would always prescribe the most
# aggressive agent, because in this model more treatment never costs anything.
DEFAULT_ACTION_COSTS: dict[str, float] = {
    "none": 0.0,
    "SSRI": 0.5,
    "SNRI": 0.6,
    "mood_stabilizer": 0.8,
    "benzodiazepine": 1.2,
    "atypical_antipsychotic": 1.5,
}


@dataclass
class MDPResult:
    states: list[str]
    actions: list[str]
    policy: dict[str, str]
    value_function: dict[str, float]
    q_values: dict[str, dict[str, float]]
    n_iterations: int
    converged: bool
    discount: float
    value_iteration_agrees: bool
    policy_values_vs_fixed: dict[str, float]
    advantage_over_best_fixed: float
    best_fixed_action: str


def build_action_transitions(actions=None) -> dict[str, np.ndarray]:
    """P(s' | s, a) for each action, reusing the existing chain construction."""
    model = PatientStateMarkovModel()
    acts = list(actions) if actions else ACTIONS
    out: dict[str, np.ndarray] = {}
    for a in acts:
        classes = [] if a == "none" else [a]
        out[a] = model.build_transition_matrix(classes)
    return out


def build_reward_matrix(
    actions: list[str],
    state_rewards: dict[str, float] | None = None,
    action_costs: dict[str, float] | None = None,
) -> np.ndarray:
    """R[s, a] = value of state s minus the weekly burden of action a."""
    sr = {**DEFAULT_STATE_REWARDS, **(state_rewards or {})}
    ac = {**DEFAULT_ACTION_COSTS, **(action_costs or {})}
    R = np.zeros((len(STATES), len(actions)))
    for i, s in enumerate(STATES):
        for j, a in enumerate(actions):
            R[i, j] = sr.get(s, 0.0) - ac.get(a, 0.0)
    return R


def policy_evaluation(
    policy_idx: np.ndarray, P: dict[str, np.ndarray], R: np.ndarray,
    actions: list[str], gamma: float,
) -> np.ndarray:
    """Exact value of a fixed policy by solving (I - gamma P_pi) V = R_pi.

    Direct solve rather than iterating to a fixed point: the state space is
    tiny, and an exact evaluation makes policy iteration terminate in a
    provably finite number of steps.
    """
    n = len(STATES)
    P_pi = np.zeros((n, n))
    R_pi = np.zeros(n)
    for s in range(n):
        a = actions[policy_idx[s]]
        P_pi[s] = P[a][s]
        R_pi[s] = R[s, policy_idx[s]]
    return np.linalg.solve(np.eye(n) - gamma * P_pi, R_pi)


def value_iteration(
    P: dict[str, np.ndarray], R: np.ndarray, actions: list[str],
    gamma: float = 0.95, tol: float = 1e-10, max_iter: int = 10000,
) -> tuple[np.ndarray, np.ndarray, int, bool]:
    """Standard Bellman backup to the fixed point.

    The Bellman operator is a gamma-contraction in the sup norm, so this
    converges geometrically from any start and the limit is unique.
    """
    n = len(STATES)
    V = np.zeros(n)
    stacked = np.stack([P[a] for a in actions])  # (A, S, S)
    for it in range(1, max_iter + 1):
        Q = R + gamma * np.einsum("asx,x->sa", stacked, V)
        V_new = Q.max(axis=1)
        delta = float(np.max(np.abs(V_new - V)))
        V = V_new
        if delta < tol:
            return V, Q.argmax(axis=1), it, True
    return V, (R + gamma * np.einsum("asx,x->sa", stacked, V)).argmax(axis=1), max_iter, False


def policy_iteration(
    P: dict[str, np.ndarray], R: np.ndarray, actions: list[str],
    gamma: float = 0.95, max_iter: int = 1000,
) -> tuple[np.ndarray, np.ndarray, int, bool]:
    """Alternate exact evaluation and greedy improvement.

    Each improvement step strictly increases the value of at least one state
    unless the policy is already optimal, and there are finitely many policies,
    so this terminates exactly rather than asymptotically.
    """
    n = len(STATES)
    policy = np.zeros(n, dtype=int)
    stacked = np.stack([P[a] for a in actions])
    for it in range(1, max_iter + 1):
        V = policy_evaluation(policy, P, R, actions, gamma)
        Q = R + gamma * np.einsum("asx,x->sa", stacked, V)
        new_policy = Q.argmax(axis=1)
        if np.array_equal(new_policy, policy):
            return V, policy, it, True
        policy = new_policy
    return policy_evaluation(policy, P, R, actions, gamma), policy, max_iter, False


def solve_treatment_mdp(
    gamma: float = 0.95,
    state_rewards: dict[str, float] | None = None,
    action_costs: dict[str, float] | None = None,
    actions: list[str] | None = None,
) -> MDPResult:
    """Optimal treatment policy, with both solvers cross-checked."""
    if not 0.0 < gamma < 1.0:
        raise ValueError("discount must lie strictly between 0 and 1")
    acts = list(actions) if actions else ACTIONS
    unknown = [a for a in acts if a != "none" and a not in DRUG_CLASS_EFFECTS]
    if unknown:
        raise ValueError(f"unknown actions: {unknown}")

    P = build_action_transitions(acts)
    R = build_reward_matrix(acts, state_rewards, action_costs)

    V_pi, policy, n_iter, converged = policy_iteration(P, R, acts, gamma)
    V_vi, policy_vi, _, _ = value_iteration(P, R, acts, gamma)
    # Two independent algorithms for the same fixed point. Agreement is a real
    # check on both, so it is reported rather than assumed.
    agrees = bool(np.allclose(V_pi, V_vi, atol=1e-6) and np.array_equal(policy, policy_vi))

    stacked = np.stack([P[a] for a in acts])
    Q = R + gamma * np.einsum("asx,x->sa", stacked, V_pi)

    # Compare against every constant policy: the value of committing to one
    # class regardless of state, which is closer to how regimens are actually
    # chosen than a state-dependent rule.
    fixed_values: dict[str, float] = {}
    for j, a in enumerate(acts):
        V_fixed = policy_evaluation(np.full(len(STATES), j), P, R, acts, gamma)
        fixed_values[a] = float(V_fixed.mean())
    best_fixed = max(fixed_values, key=fixed_values.get)
    advantage = float(V_pi.mean() - fixed_values[best_fixed])

    return MDPResult(
        states=list(STATES),
        actions=acts,
        policy={s: acts[policy[IDX[s]]] for s in STATES},
        value_function={s: float(V_pi[IDX[s]]) for s in STATES},
        q_values={
            s: {a: float(Q[IDX[s], j]) for j, a in enumerate(acts)} for s in STATES
        },
        n_iterations=n_iter,
        converged=converged,
        discount=gamma,
        value_iteration_agrees=agrees,
        policy_values_vs_fixed=fixed_values,
        advantage_over_best_fixed=advantage,
        best_fixed_action=best_fixed,
    )
