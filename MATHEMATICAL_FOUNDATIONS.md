# NeuroTrace — Mathematical Foundations

> Formal derivations underlying the NeuroTrace implementation. This
> document was consolidated from the original `psychrx-guard` research
> codebase when the two projects were merged. For the implementation
> overview and API reference, see [README.md](README.md).
>
> Each section below derives the math behind a NeuroTrace feature: the
> ODE/PDE system in `backend/services/pk_simulator.py` and `tissue_pde.py`,
> the graph-theoretic analyses in `graph_analysis.py` / `bipartite_analysis.py`
> / `flow_analysis.py`, the stochastic solver in `sde_simulator.py`, the
> dynamic-programming taper in `optimal_control.py`, the entropy / Markov /
> TDA / game-theory modules, and the Bayesian MIPD engine in `bayesian_pk.py`.

---

## Table of Contents

1. [Pharmacokinetic Foundations](#i-pharmacokinetic-foundations)
2. [Enzyme Kinetics and Drug-Drug Interactions](#ii-enzyme-kinetics-and-drug-drug-interactions)
3. [Dynamic Enzyme Pool Theory](#iii-dynamic-enzyme-pool-theory)
4. [Multi-Drug Coupled ODE System](#iv-multi-drug-coupled-ode-system)
5. [Population and Bayesian Pharmacokinetics](#v-population-and-bayesian-pharmacokinetics)
6. [Spectral Graph Theory for Interaction Networks](#vi-spectral-graph-theory-for-interaction-networks)
7. [Bipartite Analysis and Combinatorics](#vii-bipartite-analysis-and-combinatorics)
8. [Stochastic Pharmacokinetics](#viii-stochastic-pharmacokinetics)
9. [Optimal Dose Control](#ix-optimal-dose-control)
10. [Information-Theoretic Metabolic Analysis](#x-information-theoretic-metabolic-analysis)
11. [Markov Chain Patient State Model](#xi-markov-chain-patient-state-model)
12. [Topological Data Analysis](#xii-topological-data-analysis)
13. [Algorithmic Game Theory](#xiii-algorithmic-game-theory)
14. [Tissue Distribution PDE](#xiv-tissue-distribution-pde)
15. [Receptor Occupancy](#xv-receptor-occupancy)
16. [Hepatic Extraction](#xvi-hepatic-extraction)
17. [Optimal Experimental Design](#xvii-optimal-experimental-design)
18. [References](#references)

---

## I. Pharmacokinetic Foundations

### 1.1 One-Compartment Oral Absorption

**Definition 1.1** (One-Compartment Model). *A one-compartment pharmacokinetic model represents the body as a single, kinetically homogeneous compartment of volume $V_d$ (apparent volume of distribution) with first-order absorption from the gastrointestinal tract at rate $k_a$ and first-order elimination at rate $k_e = CL / V_d$.*

**Theorem 1.1** (Bateman Equation). *Let a single oral dose $D$ of a drug with bioavailability $F$, absorption rate constant $k_a$, and elimination rate constant $k_e$ be administered at $t = 0$. Then the plasma concentration at time $t > 0$ is:*

$$C(t) = \frac{F \cdot D \cdot k_a}{V_d(k_a - k_e)} \left( e^{-k_e t} - e^{-k_a t} \right)$$

*Proof.* The system of ODEs governing the one-compartment oral model is:

$$\frac{dA_{gut}}{dt} = -k_a \cdot A_{gut}, \quad \frac{dA_{plasma}}{dt} = k_a \cdot A_{gut} - k_e \cdot A_{plasma}$$

with initial conditions $A_{gut}(0) = F \cdot D$ and $A_{plasma}(0) = 0$. The first equation gives $A_{gut}(t) = F \cdot D \cdot e^{-k_a t}$. Substituting into the second and solving the first-order linear ODE via the integrating factor $e^{k_e t}$:

$$A_{plasma}(t) = \frac{F \cdot D \cdot k_a}{k_a - k_e}\left(e^{-k_e t} - e^{-k_a t}\right)$$

Since $C(t) = A_{plasma}(t) / V_d$, the result follows. $\blacksquare$

**Corollary 1.1** (Half-Life). *The elimination half-life is:*

$$t_{1/2} = \frac{\ln 2}{k_e} = \frac{0.693 \cdot V_d}{CL}$$

*Proof.* At the terminal elimination phase ($t$ large, $e^{-k_a t} \approx 0$), $C(t) \propto e^{-k_e t}$. Setting $C(t + t_{1/2}) = C(t)/2$ gives $e^{-k_e \cdot t_{1/2}} = 1/2$, hence $t_{1/2} = \ln 2 / k_e$. $\blacksquare$

**Corollary 1.2** (Time to Peak). *The time to maximum concentration is:*

$$t_{max} = \frac{\ln(k_a / k_e)}{k_a - k_e}$$

*Proof.* Setting $dC/dt = 0$ and solving yields $k_e \cdot e^{-k_e t_{max}} = k_a \cdot e^{-k_a t_{max}}$, from which the result follows by taking logarithms. $\blacksquare$

### 1.2 Multiple Dose Superposition

**Theorem 1.2** (Steady-State Superposition). *For repeated oral dosing at interval $\tau$ hours, the steady-state concentration profile is obtained by superposition of the Bateman equation over all past doses. At steady state ($n \to \infty$), the peak and trough concentrations are:*

$$C_{ss,max} = \frac{F \cdot D \cdot k_a}{V_d(k_a - k_e)} \left( \frac{1}{1 - e^{-k_e \tau}} - \frac{1}{1 - e^{-k_a \tau}} \right)$$

$$C_{ss,min} = C_{ss,max} \cdot e^{-k_e \cdot \tau}$$

*Proof.* The concentration after the $n$-th dose is $C_n(t) = \sum_{i=0}^{n-1} C_{\text{single}}(t - i\tau)$. Applying the geometric series $\sum_{i=0}^{\infty} r^i = 1/(1-r)$ separately to the two exponential terms in the Bateman equation yields the result. $\blacksquare$

**Corollary 1.3** (Average Steady-State Concentration). *The time-averaged steady-state concentration depends only on dose, bioavailability, clearance, and dosing interval:*

$$\bar{C}_{ss} = \frac{F \cdot D}{CL \cdot \tau}$$

*Proof.* By definition, $\bar{C}_{ss} = \frac{1}{\tau}\int_0^\tau C_{ss}(t)\,dt$. The integral of $C_{ss}$ over one dosing interval equals the AUC of a single dose (by superposition), which is $F \cdot D / CL$ by the trapezoidal rule applied to the Bateman function. $\blacksquare$

**Lemma 1.1** (Time to Steady State). *The system reaches 90% of steady state after approximately $3.3 \times t_{1/2}$ and 97% after $5 \times t_{1/2}$.*

*Proof.* The accumulation factor after $n$ doses is $1 - e^{-n k_e \tau}$. Setting this to 0.9 gives $n \cdot k_e \cdot \tau = \ln 10 \approx 2.3$. Since $t = n\tau$ and $k_e = \ln 2 / t_{1/2}$, we get $t_{90\%} = 2.3 \cdot t_{1/2} / \ln 2 \approx 3.3 \cdot t_{1/2}$. Similarly, $t_{97\%} \approx 5 \times t_{1/2}$. $\blacksquare$

---

## II. Enzyme Kinetics and Drug-Drug Interactions

### 2.1 Michaelis-Menten Elimination

**Definition 2.1** (Saturable Elimination). *A Michaelis-Menten process describes enzyme-catalyzed metabolism where the rate is limited by enzyme capacity $V_{max}$.*

**Theorem 2.1** (Michaelis-Menten Rate Law). *The rate of enzymatic metabolism of a substrate at concentration $C$ is:*

$$v = \frac{V_{max} \cdot C}{K_m + C}$$

*where $V_{max}$ is the maximum metabolic rate and $K_m$ is the Michaelis constant (substrate concentration at half-maximal rate).*

*Proof.* Consider enzyme $E$ binding substrate $S$ to form complex $ES$ which yields product $P$: $E + S \xrightleftharpoons[k_{-1}]{k_1} ES \xrightarrow{k_2} E + P$. Under the quasi-steady-state assumption ($d[ES]/dt = 0$), $k_1[E][S] = (k_{-1} + k_2)[ES]$. With $[E]_{total} = [E] + [ES]$ and $K_m = (k_{-1} + k_2)/k_1$, substitution gives $v = k_2[ES] = V_{max} \cdot C / (K_m + C)$ where $V_{max} = k_2[E]_{total}$. $\blacksquare$

**Corollary 2.1** (Limiting Regimes).

*(i) When $C \ll K_m$: $v \approx (V_{max}/K_m) \cdot C$ (first-order kinetics).*

*(ii) When $C \gg K_m$: $v \approx V_{max}$ (zero-order kinetics).*

*(iii) When $C = K_m$: $v = V_{max}/2$ (half-maximal rate).*

*Proof.* Direct substitution into the Michaelis-Menten equation. $\blacksquare$

### 2.2 Competitive CYP450 Inhibition

**Theorem 2.2** (Competitive Inhibition). *When Drug B at concentration $C_B$ competitively inhibits the CYP enzyme metabolizing Drug A, the metabolic rate of Drug A becomes:*

$$v_A = \frac{V_{max,A} \cdot C_A}{K_{m,A}\left(1 + \displaystyle\frac{C_B}{K_{i,B}}\right) + C_A}$$

*where $K_{i,B}$ is the inhibition constant of Drug B. For $N$ simultaneous inhibitors:*

$$v_A = \frac{V_{max,A} \cdot C_A}{K_{m,A}\left(1 + \displaystyle\sum_{j=1}^{N}\frac{C_j}{K_{i,j}}\right) + C_A}$$

*Proof.* In competitive inhibition, the inhibitor binds the free enzyme: $E + I \xrightleftharpoons{K_i} EI$. The apparent Michaelis constant becomes $K_m^{app} = K_m(1 + [I]/K_i)$ because the inhibitor effectively reduces the available enzyme for substrate binding. With $N$ inhibitors each independently binding the free enzyme, the inhibition terms are additive: $K_m^{app} = K_m(1 + \sum_j C_j / K_{i,j})$. $\blacksquare$

**Lemma 2.1** (Dynamic Coupling). *In a multi-drug system, $C_B$ is not constant — it changes over time as Drug B is absorbed, distributed, and eliminated. Therefore, the system of metabolic equations for $N$ co-administered drugs forms a set of coupled nonlinear ODEs.*

*Proof.* Each drug's elimination rate depends on the concentrations of all other drugs (via the competitive inhibition term), and each drug's concentration is itself governed by an ODE. The coupling is nonlinear because the inhibition terms appear in the denominator. $\blacksquare$

**Theorem 2.3** (FDA Mechanistic Static AUC Ratio). *For a substrate metabolized fraction $f_m$ by an enzyme competitively inhibited by Drug B at unbound concentration $[I]_u$ with unbound inhibition constant $K_{i,u}$:*

$$\text{AUC ratio} = \frac{1}{1 - f_m\left(1 - \displaystyle\frac{1}{1 + [I]_u / K_{i,u}}\right)}$$

*Proof.* At steady state, $AUC = F \cdot D / CL$. With inhibition, the clearance via the affected enzyme is reduced by the factor $1/(1 + [I]_u/K_{i,u})$, while clearance via other routes is unchanged. The total clearance becomes $CL' = CL \cdot [f_m/(1 + [I]_u/K_{i,u}) + (1 - f_m)]$. The AUC ratio $= CL/CL'$ simplifies to the stated expression. $\blacksquare$

---

## III. Dynamic Enzyme Pool Theory

### 3.1 Mechanism-Based (Time-Dependent) Inhibition

**Definition 3.1** (Mechanism-Based Inhibition). *An inhibitor that irreversibly inactivates a CYP enzyme, requiring de novo enzyme synthesis for recovery. The enzyme pool is characterized by synthesis rate $k_{synth}$, degradation rate $k_{deg}$, and inactivation parameters $k_{inact}$ and $K_I$.*

**Theorem 3.1** (Enzyme Pool Dynamics with MBI). *The normalized enzyme pool level $E$ (baseline = 1) evolves according to:*

$$\frac{dE}{dt} = k_{synth} - k_{deg} \cdot E - \frac{k_{inact} \cdot C_I}{K_I + C_I} \cdot E$$

*where $k_{synth} = k_{deg}$ at baseline (since $E = 1$ at steady state without perturbation).*

*Proof.* At baseline, $dE/dt = 0$ implies $k_{synth} = k_{deg} \cdot 1 = k_{deg}$. With an inhibitor present, the inactivation term $k_{inact} \cdot C_I / (K_I + C_I)$ represents a Michaelis-Menten-type irreversible binding that depletes the enzyme pool. The total rate of change is synthesis minus natural degradation minus drug-induced inactivation. $\blacksquare$

**Corollary 3.1** (Steady-State Enzyme Level Under MBI). *With constant inhibitor concentration $C_I$:*

$$E_{ss} = \frac{k_{deg}}{k_{deg} + \displaystyle\frac{k_{inact} \cdot C_I}{K_I + C_I}}$$

*Proof.* Setting $dE/dt = 0$ and substituting $k_{synth} = k_{deg}$: $k_{deg} = (k_{deg} + k_{inact} C_I/(K_I + C_I)) \cdot E_{ss}$. Solving for $E_{ss}$ gives the result. Since $k_{inact} C_I/(K_I + C_I) > 0$, we have $E_{ss} < 1$, confirming enzyme depletion. $\blacksquare$

**Theorem 3.2** (Enzyme Recovery After Inhibitor Removal). *After discontinuation of an MBI drug (at $t = 0$ post-discontinuation), the enzyme pool recovers as:*

$$E(t) = 1 - (1 - E_{inhibited}) \cdot e^{-k_{deg} \cdot t}$$

*The recovery half-life equals the natural enzyme degradation half-life: $t_{1/2,recovery} = \ln 2 / k_{deg}$.*

*Proof.* With $C_I = 0$, the ODE becomes $dE/dt = k_{deg}(1 - E)$. This is a first-order linear ODE with solution $E(t) = 1 - (1 - E(0)) \cdot e^{-k_{deg} t}$. Setting $E(0) = E_{inhibited}$ yields the result. The half-life follows from the exponential recovery constant $k_{deg}$. $\blacksquare$

### 3.2 Enzyme Induction

**Theorem 3.3** (Enzyme Induction Kinetics). *An inducer at concentration $C_{ind}$ increases enzyme synthesis according to:*

$$\frac{dE}{dt} = k_{deg} \cdot \left(1 + \frac{E_{max} \cdot C_{ind}}{EC_{50} + C_{ind}}\right) - k_{deg} \cdot E$$

*Proof.* The inducer upregulates transcription, increasing the synthesis rate by a saturable Emax factor. With $k_{synth} = k_{deg}$ at baseline, the modified synthesis rate is $k_{deg}(1 + E_{max} C_{ind}/(EC_{50} + C_{ind}))$. Degradation remains first-order at rate $k_{deg}$. $\blacksquare$

**Corollary 3.2** (Induced Steady State). *With constant inducer concentration:*

$$E_{ss,ind} = 1 + \frac{E_{max} \cdot C_{ind,ss}}{EC_{50} + C_{ind,ss}}$$

*Proof.* Setting $dE/dt = 0$: $k_{deg} \cdot E_{ss} = k_{deg}(1 + E_{max} C_{ind}/(EC_{50} + C_{ind}))$. Dividing by $k_{deg}$ gives the result. Since $E_{max} > 0$ and $C_{ind} > 0$, we have $E_{ss,ind} > 1$, confirming increased enzyme activity. $\blacksquare$

### 3.3 Net Effect Model

**Theorem 3.4** (Net Fold-Change in Clearance). *When a perpetrator drug simultaneously causes reversible inhibition, mechanism-based inhibition, and induction on the same enzyme, the net fold-change in intrinsic clearance is $A \cdot B \cdot C$ where:*

$$A = \frac{1}{1 + [I]_u / K_{i,u}}, \quad B = \frac{k_{deg}}{k_{deg} + \displaystyle\frac{k_{inact} [I]_u}{K_{I,u} + [I]_u}}, \quad C = 1 + \frac{d \cdot E_{max} \cdot [I]_u}{EC_{50,u} + [I]_u}$$

*Proof.* Factor $A$ represents the instantaneous reduction in catalytic rate due to reversible competitive inhibition (Theorem 2.2). Factor $B$ represents the fractional enzyme remaining after mechanism-based depletion (Corollary 3.1). Factor $C$ represents the fold-increase in enzyme pool from induction (Corollary 3.2). Since these act on different aspects of enzyme function (active site occupancy, enzyme quantity via destruction, enzyme quantity via synthesis), their effects multiply. $\blacksquare$

---

## IV. Multi-Drug Coupled ODE System

**Theorem 4.1** (Multi-Drug PK System). *For $N$ drugs sharing $P$ enzymes with $M$ active metabolites, the complete system solved by `scipy.integrate.solve_ivp` has state dimension $2N + M + P$ and is defined by:*

**Drug compartments** ($i = 1, \ldots, N$):

$$\frac{dA_{gut,i}}{dt} = -k_{a,i} \cdot A_{gut,i} + \sum_{\text{doses}} D_i \cdot F_i \cdot \delta(t - t_{dose})$$

$$\frac{dA_{plasma,i}}{dt} = k_{a,i} A_{gut,i} - \sum_{j=1}^{P} \frac{V_{max,ij} \cdot C_i \cdot (E_j / E_{j,0})}{K_{m,ij}\left(1 + \displaystyle\sum_{k \neq i} \frac{C_k}{K_{i,kj}}\right) + C_i} - CL_{renal,i} \cdot C_i$$

**Metabolite compartments** ($m = 1, \ldots, M$):

$$\frac{dA_{met,m}}{dt} = f_{met,m} \cdot \sum_j v_{parent,j} - k_{e,m} \cdot A_{met,m}$$

**Enzyme pools** ($j = 1, \ldots, P$):

$$\frac{dE_j}{dt} = k_{deg,j}\left(1 + \sum_i \frac{E_{max,ij} C_i}{EC_{50,ij} + C_i}\right) - k_{deg,j} E_j - \sum_i \frac{k_{inact,ij} C_i}{K_{I,ij} + C_i} E_j$$

*where $C_i = A_{plasma,i} / V_{d,i}$.*

**Lemma 4.1** (Existence and Uniqueness). *For physiologically reasonable parameters ($k_a, k_e, V_{max}, K_m, K_i > 0$), the right-hand side of the ODE system is Lipschitz continuous on $\mathbb{R}_{\geq 0}^{2N + M + P}$, guaranteeing local existence and uniqueness of solutions by the Picard-Lindelöf theorem.*

*Proof.* Each term is a rational function of the state variables with strictly positive denominators (since $K_m, K_i, K_I, EC_{50} > 0$). Rational functions with non-vanishing denominators are locally Lipschitz. Dose events (Dirac deltas) are handled by restarting the solver with updated initial conditions at each dose time. $\blacksquare$

**Corollary 4.1** (Non-Negativity). *If the initial state satisfies $A_{gut,i}(0), A_{plasma,i}(0), A_{met,m}(0), E_j(0) \geq 0$ for all $i, m, j$, then the solution remains non-negative for all $t > 0$.*

*Proof.* When any state variable approaches 0, its rate of decrease vanishes (all outflow terms contain the state variable as a factor or are proportional to concentrations derived from it), while inflow terms remain non-negative. The boundary $\{x = 0\}$ is therefore invariant. $\blacksquare$

### 4.1 Active Metabolite Feedback

**Theorem 4.2** (Norfluoxetine CYP2D6 Persistence). *After discontinuation of fluoxetine, the effective CYP2D6 inhibition persists for a duration determined by three sequential time constants: (i) fluoxetine elimination ($t_{1/2} \approx 1$–$4$ days), (ii) norfluoxetine elimination ($t_{1/2} \approx 4$–$16$ days), and (iii) CYP2D6 enzyme resynthesis ($t_{1/2,deg} \approx 51$ h). The total recovery time is approximately $5 \times \max(t_{1/2,norfluox}, t_{1/2,CYP2D6})$.*

*Proof.* CYP2D6 inhibition depends on both the parent drug and metabolite concentrations through the competitive inhibition term. After fluoxetine discontinuation, norfluoxetine (with longer half-life) becomes the dominant inhibitor. Only after norfluoxetine clears can enzyme resynthesis begin. The convolution of these sequential processes gives total recovery $\approx 5 \times \max(16\text{ days}, 51/24\text{ days}) = 5 \times 16 = 80$ days in the worst case. $\blacksquare$

---

## V. Population and Bayesian Pharmacokinetics

### 5.1 Population PK Model

**Theorem 5.1** (Log-Normal Population Distribution). *Individual PK parameters follow log-normal distributions:*

$$\theta_i = \theta_{pop} \cdot e^{\eta_i}, \quad \eta_i \sim \mathcal{N}(0, \omega^2)$$

*where $\theta_{pop}$ is the population typical value and $\omega^2$ is the inter-individual variance.*

*Proof.* Log-normal distributions are the standard choice for PK parameters because: (1) they are strictly positive (volumes, clearances cannot be negative), (2) multiplicative biological processes produce log-normal outcomes by the central limit theorem applied to products, and (3) the coefficient of variation is approximately $\omega$ for small $\omega$. $\blacksquare$

**Corollary 5.1** (Monte Carlo Confidence Intervals). *For $K$ Monte Carlo iterations with sampled parameter sets $\{\theta^{(k)}\}_{k=1}^K$, the pointwise 95% confidence interval at time $t$ is:*

$$\text{CI}_{95}(t) = \left[C_{(\lfloor 0.025K \rfloor)}(t),\; C_{(\lceil 0.975K \rceil)}(t)\right]$$

*Proof.* By the Glivenko-Cantelli theorem, the empirical CDF of $\{C^{(k)}(t)\}$ converges uniformly to the true CDF as $K \to \infty$. The 2.5th and 97.5th empirical percentiles therefore converge to the true 95% CI bounds. $\blacksquare$

**Theorem 5.2** (Toxicity Probability). *The probability that concentration exceeds the toxic threshold at time $t$ is:*

$$P(\text{toxic at } t) = \frac{1}{K}\sum_{k=1}^{K} \mathbb{1}\left[C^{(k)}(t) > C_{toxic}\right]$$

*This is an unbiased, consistent estimator of the true toxicity probability with standard error $\sqrt{p(1-p)/K}$.*

*Proof.* Each indicator $\mathbb{1}[C^{(k)}(t) > C_{toxic}]$ is a Bernoulli random variable with parameter $p = P(C(t) > C_{toxic})$. The sample mean of $K$ i.i.d. Bernoulli variables is unbiased with variance $p(1-p)/K$. Consistency follows from the law of large numbers. $\blacksquare$

### 5.2 Bayesian MAP Estimation

**Theorem 5.3** (Bayesian MAP with TDM Data). *Given observed trough concentrations $C_{obs}$ from therapeutic drug monitoring, the MAP estimate of individual parameters is:*

$$\hat{\eta} = \arg\min_{\eta} \left[ \sum_j \frac{(C_{obs,j} - C_{pred,j}(\eta))^2}{\sigma^2} + \eta^T \Omega^{-1} \eta \right]$$

*Proof.* By Bayes' theorem, the posterior $p(\eta | C_{obs}) \propto p(C_{obs} | \eta) \cdot p(\eta)$. With Gaussian likelihood and Gaussian prior, the log-posterior is $-\frac{1}{2}[\sum_j (C_{obs,j} - C_{pred,j})^2/\sigma^2 + \eta^T \Omega^{-1} \eta] + \text{const}$. Maximizing the posterior (= minimizing the negative log-posterior) gives the MAP estimator. $\blacksquare$

### 5.3 Pharmacogenomic Adjustment

**Theorem 5.4** (CPIC Clearance Adjustment). *For a drug metabolized by multiple enzymes with fractional contributions $f_{m,j}$ and CYP activity scores $AS_j$:*

$$CL_{adj} = CL_{pop} \cdot \left[\sum_j f_{m,j} \cdot AS_j + \left(1 - \sum_j f_{m,j}\right)\right]$$

*Proof.* Total clearance is the sum of clearances via each route: $CL = \sum_j f_{m,j} \cdot CL_{pop} + (1 - \sum_j f_{m,j}) \cdot CL_{pop}$. The activity score $AS_j$ scales the clearance via enzyme $j$ relative to the normal metabolizer, giving $CL_{adj} = CL_{pop} \cdot [\sum_j f_{m,j} \cdot AS_j + (1 - \sum_j f_{m,j})]$. $\blacksquare$

**Corollary 5.2** (Aripiprazole CYP2D6 PM Example). *Aripiprazole: $f_{m,CYP3A4} = 0.65$, $f_{m,CYP2D6} = 0.35$. For a CYP2D6 poor metabolizer ($AS_{2D6} = 0.3$):*

$$CL_{adj} = CL \times (0.65 \times 1.0 + 0.35 \times 0.3) = 0.755 \times CL$$

*yielding $\sim$33% higher steady-state levels ($C_{ss} \propto 1/CL$).*

---

## VI. Spectral Graph Theory for Interaction Networks

### 6.1 Interaction Multigraph

**Definition 6.1** (Drug Interaction Graph). *Let $G = (V, E, w)$ be a weighted undirected graph where $V = \{d_1, \ldots, d_n\}$ represents medications, $E \subseteq \binom{V}{2}$ represents interacting pairs, and $w: E \to \{1, 2, 3, 4\}$ encodes severity (Minor=1, Moderate=2, Major=3, Critical=4). The weighted adjacency matrix $\mathbf{W} \in \mathbb{R}^{n \times n}$ is:*

$$W_{ij} = \begin{cases} w(d_i, d_j) & \text{if } (d_i, d_j) \in E \\ 0 & \text{otherwise} \end{cases}$$

**Lemma 6.1** (Symmetry). *Since drug interactions are bidirectional, $\mathbf{W}$ is symmetric: $W_{ij} = W_{ji}$ for all $i, j$.*

### 6.2 Algebraic Connectivity

**Definition 6.2** (Graph Laplacian). *The Laplacian matrix is $\mathbf{L} = \mathbf{D} - \mathbf{W}$ where $D_{ii} = \sum_j W_{ij}$ is the degree matrix.*

**Theorem 6.1** (Spectral Properties of the Laplacian). *The eigenvalues of $\mathbf{L}$ satisfy $0 = \lambda_1 \leq \lambda_2 \leq \cdots \leq \lambda_n$. The multiplicity of $\lambda_1 = 0$ equals the number of connected components of $G$.*

*Proof.* $\mathbf{L}$ is positive semi-definite since for any $\mathbf{x} \in \mathbb{R}^n$, $\mathbf{x}^T \mathbf{L} \mathbf{x} = \sum_{(i,j) \in E} w_{ij}(x_i - x_j)^2 \geq 0$. The vector $\mathbf{1} = (1, 1, \ldots, 1)^T$ satisfies $\mathbf{L}\mathbf{1} = \mathbf{0}$, so $\lambda_1 = 0$. If $G$ has $k$ components, then $k$ linearly independent vectors (indicators of each component) span the null space. $\blacksquare$

**Theorem 6.2** (Fiedler's Algebraic Connectivity). *The second-smallest eigenvalue $\lambda_2$ of $\mathbf{L}$ measures the connectivity of $G$:*

$$\lambda_2 = \min_{\mathbf{x} \perp \mathbf{1}, \|\mathbf{x}\|=1} \mathbf{x}^T \mathbf{L} \mathbf{x} = \min_{\mathbf{x} \perp \mathbf{1}, \|\mathbf{x}\|=1} \sum_{(i,j) \in E} w_{ij}(x_i - x_j)^2$$

*$\lambda_2 > 0$ if and only if $G$ is connected. The corresponding eigenvector $\mathbf{v}_2$ (Fiedler vector) provides an optimal bisection of $V$ by sign.*

*Proof.* $\lambda_2 > 0$ iff the null space of $\mathbf{L}$ is one-dimensional (i.e., spanned by $\mathbf{1}$), which is equivalent to $G$ being connected by the preceding theorem. The Rayleigh quotient characterization follows from the Courant-Fischer min-max principle for symmetric matrices. The sign partition of $\mathbf{v}_2$ approximately minimizes the ratio cut by the Cheeger inequality. $\blacksquare$

**Corollary 6.1** (Bridge Drug Identification). *The drug $d_i$ with the Fiedler vector component $(\mathbf{v}_2)_i$ closest to zero is the "bridge drug" — its removal maximally decouples the interaction network into two weakly interacting clusters.*

*Proof.* The Fiedler vector assigns each vertex a coordinate on the real line such that connected vertices are close. A vertex near zero sits at the boundary between the two clusters and mediates most inter-cluster interactions. $\blacksquare$

### 6.3 Spectral Radius and Centrality

**Theorem 6.3** (Perron-Frobenius). *For a non-negative irreducible matrix $\mathbf{W}$, the spectral radius $\rho(\mathbf{W}) = \max_i |\lambda_i(\mathbf{W})|$ is a simple eigenvalue, and the corresponding eigenvector $\mathbf{v}_{max}$ has strictly positive entries.*

*Proof.* This is the Perron-Frobenius theorem for non-negative irreducible matrices. $\blacksquare$

**Corollary 6.2** (Interaction Centrality). *The drug with the largest component in $\mathbf{v}_{max}$ is the most "interactionally central" drug in the regimen. $\rho(\mathbf{W})$ bounds the maximum cascading interaction intensity.*

### 6.4 Chromatic Number and Independence

**Definition 6.3** (Conflict Graph). *Define $G_c = (V, E_c)$ where $(d_i, d_j) \in E_c$ iff $w(d_i, d_j) \geq 3$ (Major or Critical interaction).*

**Theorem 6.4** (Chromatic Interpretation). *The chromatic number $\chi(G_c)$ is the minimum number of "compatibility phases" needed to partition the drugs such that no two drugs with a major/critical interaction share the same phase.*

*Proof.* This is precisely the definition of graph coloring — a valid $k$-coloring assigns each vertex a color from $\{1, \ldots, k\}$ such that adjacent vertices have different colors. The minimum such $k$ is $\chi(G_c)$. $\blacksquare$

**Theorem 6.5** (Maximum Independent Set). *$\alpha(G_c) = $ the size of the largest set of drugs with no pairwise major/critical interactions among them.*

**Theorem 6.6** (Ramsey Bound). *For any regimen of $n \geq R(3,3) = 6$ drugs, there must exist either 3 mutually interacting drugs or 3 mutually non-interacting drugs in $G_c$.*

*Proof.* By Ramsey's theorem, for any 2-coloring of the edges of $K_6$, there exists a monochromatic triangle. $\blacksquare$

---

## VII. Bipartite Analysis and Combinatorics

### 7.1 CYP450 Bipartite Graph

**Definition 7.1**. *The CYP450 drug-enzyme network is a bipartite graph $B = (V_D \cup V_E, E_B)$ where $V_D$ = drugs, $V_E$ = enzymes, and edges represent substrate/inhibitor/inducer relationships.*

**Theorem 7.1** (König's Theorem). *In a bipartite graph, the size of the maximum matching equals the size of the minimum vertex cover:*

$$\nu(B) = \tau(B)$$

*Proof.* This is König's theorem (1931). The proof proceeds by showing that an augmenting path exists iff the matching is not maximum, and constructing the minimum cover from the maximum matching via alternating paths. $\blacksquare$

**Corollary 7.1** (Minimum Conflict Resolution). *The minimum number of drugs that must be removed to eliminate all CYP450 substrate-inhibitor conflicts equals the maximum matching in the conflict subgraph.*

### 7.2 Metabolic Flow Network

**Theorem 7.2** (Max-Flow Min-Cut). *In the metabolic flow network with enzyme capacities $c(d_i, e_j) = V_{max,ij}$:*

$$\text{max flow} = \text{min cut}$$

*The minimum cut identifies the metabolic bottleneck — the enzyme(s) whose saturation most limits total metabolic throughput.*

*Proof.* Ford-Fulkerson theorem (1962). Every flow is bounded by every cut; the augmenting path algorithm finds a flow equal to some cut. $\blacksquare$

### 7.3 Independence Polynomial

**Theorem 7.3** (Independence Polynomial). *The independence polynomial of the conflict graph $G_c$ is:*

$$I(G_c, x) = \sum_{k=0}^{\alpha(G_c)} i_k \cdot x^k$$

*where $i_k$ counts independent sets of size $k$. For the complete graph $K_n$: $I(K_n, x) = 1 + nx$. For the empty graph $\bar{K}_n$: $I(\bar{K}_n, x) = (1 + x)^n$.*

*Proof.* In $K_n$, the only independent sets are $\emptyset$ (counted by $i_0 = 1$) and individual vertices (counted by $i_1 = n$), giving $I = 1 + nx$. In $\bar{K}_n$, every subset is independent, so $i_k = \binom{n}{k}$, and $\sum_k \binom{n}{k} x^k = (1+x)^n$ by the binomial theorem. $\blacksquare$

---

## VIII. Stochastic Pharmacokinetics

### 8.1 Itô SDE Formulation

**Definition 8.1** (SDE PK Model). *The stochastic PK model replaces deterministic ODEs with Itô SDEs:*

$$dC_i = \mu_i(C, t)\,dt + \sigma_i \cdot C_i \cdot dW_i(t)$$

*where $\mu_i$ is the deterministic drift, $\sigma_i$ is the volatility parameter, and $W_i(t)$ is a standard Wiener process.*

**Theorem 8.1** (Non-Negativity of Geometric Brownian Motion). *The multiplicative noise structure $\sigma_i \cdot C_i$ ensures $C_i(t) \geq 0$ for all $t$ whenever $C_i(0) \geq 0$.*

*Proof.* The solution of $dX = \mu X \, dt + \sigma X \, dW$ is $X(t) = X(0) \exp((\mu - \sigma^2/2)t + \sigma W(t))$, which is strictly positive for $X(0) > 0$. This geometric Brownian motion structure prevents negative concentrations. $\blacksquare$

### 8.2 Numerical Methods

**Theorem 8.2** (Euler-Maruyama Scheme). *The Euler-Maruyama discretization has strong order of convergence $1/2$:*

$$C_i^{n+1} = C_i^n + \mu_i^n \Delta t + \sigma_i C_i^n \sqrt{\Delta t}\, Z^n, \quad Z^n \sim \mathcal{N}(0,1)$$

**Theorem 8.3** (Milstein Scheme). *The Milstein method achieves strong order 1 by including the Itô-Taylor correction:*

$$C_i^{n+1} = C_i^n + \mu_i^n \Delta t + \sigma_i C_i^n \sqrt{\Delta t}\, Z^n + \tfrac{1}{2}\sigma_i^2 C_i^n \Delta t (Z_n^2 - 1)$$

*Proof.* The correction term $\frac{1}{2}\sigma^2 C \Delta t (Z^2 - 1)$ corresponds to the second-order Itô-Taylor expansion of the diffusion coefficient. Its inclusion eliminates the leading-order error term, improving convergence from $O(\Delta t^{1/2})$ to $O(\Delta t)$. $\blacksquare$

---

## IX. Optimal Dose Control

**Definition 9.1** (Dose Optimization Problem). *Given state variables $\mathbf{x}(t) = [C_1(t), \ldots, C_N(t)]$ and discrete control variables $\mathbf{u}(t) = [D_1(t), \ldots, D_N(t)]$ restricted to available tablet sizes, minimize:*

$$J[\mathbf{u}] = \sum_{t=0}^{T}\left[\alpha \max(0, C - C_{max})^2 + \beta \max(0, C_{min} - C)^2 + \delta |\Delta D|\right]$$

**Theorem 9.1** (Bellman Optimality Principle). *The optimal cost-to-go $V^*(s, t)$ from state $s$ at time $t$ satisfies:*

$$V^*(s, t) = \min_{u \in \mathcal{U}} \left[ c(s, u) + V^*(f(s, u), t+1) \right]$$

*where $c(s, u)$ is the one-step cost and $f(s, u)$ is the state transition function. The optimal policy is obtained by backward induction.*

*Proof.* Bellman's principle of optimality (1957): any sub-trajectory of an optimal trajectory must itself be optimal. The recursive decomposition follows by induction on the remaining time steps. $\blacksquare$

**Corollary 9.1** (Discrete Dose Constraint). *Since doses are restricted to available tablet sizes (e.g., fluoxetine $\in \{0, 10, 20, 40, 60\}$ mg), the action space at each step is finite, making exact dynamic programming computationally feasible for typical psychiatric regimens ($N \leq 5$ drugs, $T \leq 56$ days).*

---

## X. Information-Theoretic Metabolic Analysis

### 10.1 Shannon Entropy of Metabolic Load

**Definition 10.1** (Metabolic Load Distribution). *For $N$ drugs metabolized across $M$ enzymes, the metabolic load on enzyme $j$ is $L_j = \sum_i f_{m,ij} \cdot CL_i$, and the normalized distribution is $p_j = L_j / \sum_k L_k$.*

**Theorem 10.1** (CYP Diversification Index). *The CDI is the normalized Shannon entropy of the metabolic load distribution:*

$$\text{CDI} = \frac{H(\mathbf{p})}{\log_2 M}, \quad H(\mathbf{p}) = -\sum_{j=1}^{M} p_j \log_2 p_j$$

*$\text{CDI} \in [0, 1]$, with $\text{CDI} = 1$ iff metabolism is uniformly distributed across all enzymes, and $\text{CDI} = 0$ iff all metabolism goes through a single enzyme.*

*Proof.* Shannon entropy achieves its maximum $H_{max} = \log_2 M$ when $p_j = 1/M$ for all $j$ (uniform distribution), proven by Lagrange multipliers with the constraint $\sum p_j = 1$. It achieves its minimum $H = 0$ when one $p_j = 1$ and the rest are 0. Normalizing by $H_{max}$ maps the range to $[0, 1]$. $\blacksquare$

**Lemma 10.1** (KL Divergence from Ideal). *The Kullback-Leibler divergence from the uniform distribution measures deviation from the safest metabolic profile:*

$$D_{KL}(\mathbf{p} \| \mathbf{u}) = \sum_j p_j \log_2 \frac{p_j}{1/M} = \log_2 M - H(\mathbf{p})$$

*$D_{KL} = 0$ iff $\mathbf{p} = \mathbf{u}$ (perfectly diversified). $D_{KL}$ is always non-negative (Gibbs' inequality).*

*Proof.* Substituting $u_j = 1/M$: $D_{KL} = \sum_j p_j \log_2(M p_j) = \log_2 M + \sum_j p_j \log_2 p_j = \log_2 M - H(\mathbf{p})$. Non-negativity follows from Jensen's inequality applied to the convex function $-\log$. $\blacksquare$

---

## XI. Markov Chain Patient State Model

**Definition 11.1** (Clinical State Space). *$S = \{\text{Stable, Partial Response, Relapse, Adverse Event, Hospitalized, Remission}\}$ with transition matrix $\mathbf{P} \in \mathbb{R}^{6 \times 6}$ where $P_{ij} = P(X_{t+1} = j \mid X_t = i)$.*

**Theorem 11.1** (Stationary Distribution). *For an irreducible, aperiodic Markov chain with transition matrix $\mathbf{P}$, there exists a unique stationary distribution $\boldsymbol{\pi}$ satisfying:*

$$\boldsymbol{\pi} = \boldsymbol{\pi}\mathbf{P}, \quad \sum_i \pi_i = 1, \quad \pi_i > 0 \;\forall i$$

*$\pi_i$ gives the long-run proportion of time spent in state $i$.*

*Proof.* By the Perron-Frobenius theorem applied to the non-negative irreducible stochastic matrix $\mathbf{P}^T$, the eigenvalue 1 is simple with a strictly positive eigenvector. Normalizing this eigenvector to sum to 1 gives $\boldsymbol{\pi}$. Uniqueness follows from simplicity. $\blacksquare$

**Theorem 11.2** (Expected First Passage Time). *The expected number of steps to reach state $j$ from state $i$ satisfies:*

$$m_{ij} = 1 + \sum_{k \neq j} P_{ik} \cdot m_{kj}$$

*In matrix form: $\mathbf{m}_j = \mathbf{1} + \mathbf{Q} \cdot \mathbf{m}_j$ where $\mathbf{Q}$ is $\mathbf{P}$ with row and column $j$ removed, giving $\mathbf{m}_j = (\mathbf{I} - \mathbf{Q})^{-1}\mathbf{1}$.*

*Proof.* By the law of total expectation, conditioned on the first step: $m_{ij} = 1 + \sum_k P_{ik} \cdot m_{kj}$, with $m_{jj} = 0$. Separating the $k = j$ term (which contributes $P_{ij} \cdot 0 = 0$) yields the recurrence. Since $\mathbf{Q}$ is a sub-stochastic matrix (row sums < 1), $(\mathbf{I} - \mathbf{Q})$ is invertible with non-negative inverse (the fundamental matrix). $\blacksquare$

**Corollary 11.1** (Treatment Effect). *Drug class effects modify $\mathbf{P}$ additively: $\mathbf{P}(R) = \text{normalize}(\mathbf{P}_0 + \sum_{d \in R} \Delta\mathbf{P}_d)$. SSRIs increase $P[\text{Partial Response} \to \text{Stable}]$ and $P[\text{Stable} \to \text{Remission}]$; effective treatment decreases $m_{i,\text{Remission}}$.*

---

## XII. Topological Data Analysis

### 12.1 Persistent Homology

**Definition 12.1** (Interaction Distance). *Define $d(d_i, d_j) = 1/w(d_i, d_j)$ for interacting drugs (stronger interaction = shorter distance), and $d(d_i, d_j) = \infty$ otherwise.*

**Definition 12.2** (Vietoris-Rips Complex). *At filtration parameter $\epsilon$:*

$$\text{VR}_\epsilon = \{\sigma \subseteq V : d(v_i, v_j) \leq \epsilon \text{ for all } v_i, v_j \in \sigma\}$$

**Theorem 12.1** (Betti Number Interpretation).

*(i) $\beta_0(\epsilon)$ = number of connected components at filtration $\epsilon$. As $\epsilon$ increases from 0, components merge as edges are added.*

*(ii) $\beta_1(\epsilon)$ = number of independent 1-cycles (loops). A persistent $\beta_1$ feature indicates a circular interaction dependency.*

*Proof.* By definition, $\beta_k = \text{rank}\, H_k(\text{VR}_\epsilon)$ where $H_k$ is the $k$-th simplicial homology group. $H_0$ counts connected components and $H_1$ counts independent non-bounding 1-cycles. $\blacksquare$

**Lemma 12.1** (Persistence as Significance). *A topological feature with large persistence $|d - b|$ (death minus birth) represents a robust structural pattern in the interaction network. Features near the diagonal of the persistence diagram are noise.*

**Corollary 12.1** (Metabolic Feedback Loop Detection). *A persistent $\beta_1$ cycle $A \to B \to C \to A$ in the interaction network corresponds to a metabolic feedback loop: Drug A inhibits an enzyme metabolizing Drug B, Drug B inhibits an enzyme metabolizing Drug C, and Drug C affects Drug A's metabolism. Such loops may cause oscillating drug levels.*

---

## XIII. Algorithmic Game Theory

### 13.1 Enzyme Competition Game

**Definition 13.1** (Congestion Game). *Model CYP450 competition as an $N$-player congestion game where drugs are players, enzymes are resources, and each drug's metabolic "strategy" is its enzyme usage profile $\sigma_i = (f_{m,i1}, \ldots, f_{m,iM})$.*

**Definition 13.2** (Social Cost). *The total metabolic inefficiency of the regimen:*

$$SC(\mathbf{C}) = \sum_{i=1}^{N}\left(\frac{CL_{i,\text{ideal}}}{CL_{i,\text{eff}}} - 1\right)^2$$

*where $CL_{i,\text{ideal}}$ is the clearance if drug $i$ were the only drug, and $CL_{i,\text{eff}}$ is the clearance under competition.*

**Theorem 13.1** (Existence of Pure Nash Equilibrium). *Every congestion game possesses at least one pure-strategy Nash equilibrium.*

*Proof.* Rosenthal (1973) proved this by constructing a potential function $\Phi$ whose local minima correspond to Nash equilibria. Since the action space is finite, $\Phi$ achieves its minimum, guaranteeing existence. $\blacksquare$

**Definition 13.3** (Price of Anarchy). *The ratio of the worst-case Nash equilibrium social cost to the social optimum:*

$$\text{PoA} = \frac{SC(\text{Nash equilibrium})}{SC(\text{social optimum})}$$

*$\text{PoA} \geq 1$, with $\text{PoA} = 1$ indicating no efficiency loss from competition.*

**Theorem 13.2** (Substitution Optimality). *For drug $d_i$ with alternatives $\mathcal{A}_i$, the optimal substitution is:*

$$d_i^* = \arg\min_{d' \in \mathcal{A}_i} SC(\mathbf{C} \text{ with } d_i \to d')$$

*This is computable in $O(|\mathcal{A}_i| \cdot N \cdot M)$ time for each drug.*

*Proof.* For each alternative $d'$, recompute the effective clearances and social cost. The finite action space makes exhaustive evaluation feasible. $\blacksquare$

**Corollary 13.1** (Clinical Application). *Replacing fluoxetine (strong CYP2D6 inhibitor, $K_i \approx 0.17$ nM) with sertraline (negligible CYP2D6 inhibition) when aripiprazole is co-prescribed reduces $SC$ because aripiprazole's CYP2D6-mediated clearance is no longer impeded.*

---


---

## XIV. Tissue Distribution PDE

Plasma concentration is not what acts on the target. A drug must cross the
blood-brain barrier and diffuse through tissue, and that transport is what
separates a fast-equilibrating drug from one that lags plasma by hours.

### 14.1 Governing equation

Tissue is modelled as a one-dimensional slab of depth $L$, with $x = 0$ at the
capillary surface and $x = L$ deep tissue. Free drug concentration
$c(x, t)$ obeys a reaction-diffusion equation:

$$
\frac{\partial c}{\partial t} = D \frac{\partial^2 c}{\partial x^2} - k_e c
$$

$D$ is the effective tissue diffusivity (default $7.2 \times 10^{-3}$
cm$^2$/h for brain parenchyma) and $k_e$ is first-order local elimination.

### 14.2 Boundary conditions

The surface is a **flux (Robin) boundary**, not a fixed concentration. Only
unbound drug crosses, and the flux is proportional to the gradient across the
barrier with effective permeability $P_{\text{eff}}$:

$$
\left. -D \frac{\partial c}{\partial x} \right|_{x=0} = P_{\text{eff}}\left(f_u\, C_{\text{plasma}}(t) - c(0, t)\right)
$$

Deep tissue is a **no-flux (Neumann) boundary**, representing a symmetry plane
between capillaries:

$$
\left. \frac{\partial c}{\partial x} \right|_{x=L} = 0
$$

The $f_u$ factor matters: for a drug that is 99% protein-bound
(aripiprazole, $f_u = 0.01$) the driving concentration is a hundredth of the
measured plasma level, which is why total plasma concentration is a poor
predictor of central effect across drugs with different binding.

### 14.3 Discretisation

The slab is discretised on $n$ uniform nodes with spacing
$\Delta x = L/(n-1)$, giving the standard second-order interior stencil:

$$
\frac{dc_i}{dt} = \frac{D}{\Delta x^2}(c_{i+1} - 2c_i + c_{i-1}) - k_e c_i
$$

Both boundaries use the **ghost-node** construction so they retain second-order
accuracy rather than degrading to first order. Reflecting $c_{-1}$ through the
Robin condition and eliminating it gives

$$
\frac{dc_0}{dt} = \frac{2D}{\Delta x^2}(c_1 - c_0) + \frac{2P_{\text{eff}}}{\Delta x}\left(f_u C_{\text{plasma}}(t) - c_0\right) - k_e c_0
$$

and the no-flux condition at $x = L$ gives

$$
\frac{dc_{n-1}}{dt} = \frac{2D}{\Delta x^2}(c_{n-2} - c_{n-1}) - k_e c_{n-1}
$$

The factor of 2 in both is the signature of the ghost-node elimination; using
a one-sided difference instead would silently lose an order of accuracy at
exactly the point where the interesting physics lives.

The resulting system is a stiff linear ODE in $\mathbb{R}^n$ driven by the
plasma trajectory, integrated with an implicit solver. Plasma concentration
enters as a time-dependent forcing term interpolated from the PK simulation,
so the PDE is one-way coupled to the compartmental model: tissue uptake does
not deplete plasma, which is a good approximation when tissue is a small
fraction of the distribution volume.

### 14.4 Reported quantities

Surface, mean and deep concentrations are tracked separately, along with the
**time to 80% of the final deep concentration**. That statistic is the
practical output: it estimates how long after a dose change the target site
actually reflects the new regimen, which is the lag a prescriber is implicitly
guessing at when they decide how long to wait before judging a titration.

---

## XV. Receptor Occupancy

Concentration is an intermediate; occupancy is the quantity with a known
relationship to clinical effect.

### 15.1 Unit conversion

Binding constants are published in nM while concentrations are measured in
ng/mL, so a molar-mass conversion is required before any comparison:

$$
C[\text{nM}] = \frac{C[\text{ng/mL}] \times 1000}{MW\,[\text{g/mol}]}
$$

### 15.2 Fractional occupancy

Equilibrium binding to a single site follows the Langmuir isotherm, which is
the Hill equation with $n_H = 1$:

$$
\theta = \frac{C_u}{C_u + K_d}
$$

with $C_u = f_u C$ the unbound concentration. Occupancy is therefore
**saturating**: going from $K_d$ to $2K_d$ moves occupancy from 50% to 67%,
and from $4K_d$ to $8K_d$ moves it from 80% to 89%. This is the pharmacological
reason dose-response flattens, and why doubling a dose in the upper range buys
little additional effect while side-effect occupancy keeps climbing.

For graded responses the sigmoid $E_{\max}$ form is used:

$$
E = E_0 + \frac{E_{\max} C^\gamma}{EC_{50}^\gamma + C^\gamma}
$$

### 15.3 Clinical thresholds

The thresholds the interface annotates come from PET occupancy studies
(Kapur et al. 2000, first-episode schizophrenia, $[^{11}\text{C}]$raclopride):

| D2 occupancy | Consequence |
|---|---|
| $\geq 65\%$ | clinical response becomes likely |
| $\geq 72\%$ | hyperprolactinaemia risk rises |
| $\geq 78\%$ | extrapyramidal side effects rise |

The narrowness of that window, 65% to 78%, is the entire therapeutic problem
for typical antipsychotics: the separation between response and toxicity is
13 percentage points of occupancy, which given the saturating isotherm above
corresponds to a fairly small concentration band. Plotting an occupancy
trajectory against these lines shows directly how much of a dosing interval is
spent inside the window rather than above or below it.

---

## XVI. Hepatic Extraction

Clearance is not a free parameter. It is bounded by how fast blood can deliver
drug to the liver, and that bound determines whether an interaction matters.

### 16.1 Intrinsic clearance

Each metabolic pathway contributes intrinsic clearance from its
Michaelis-Menten parameters, in the linear (sub-saturating) regime:

$$
CL_{\text{int}} = \sum_j \frac{V_{\max,j}}{K_{m,j}}
$$

Competitive inhibition scales each pathway independently by its own inhibitor
burden:

$$
CL_{\text{int}}^{\text{inh}} = \sum_j \frac{V_{\max,j}/K_{m,j}}{1 + \sum_i [I_i]_u / K_{i,ij}}
$$

Summing $[I]/K_i$ across inhibitors within a pathway is what makes multiple
weak inhibitors on the same enzyme add up, which a per-drug severity label
cannot express.

### 16.2 The well-stirred model

Hepatic clearance follows Pang and Rowland (1977):

$$
CL_H = \frac{Q_H \cdot f_u \cdot CL_{\text{int}}}{Q_H + f_u \cdot CL_{\text{int}}}
$$

with $Q_H \approx 81$ L/h. The extraction ratio and first-pass survival are

$$
E_H = \frac{CL_H}{Q_H}, \qquad F_H = 1 - E_H
$$

### 16.3 Why the limiting behaviour is the whole point

The formula is a harmonic combination, so it has two regimes:

**Low extraction** ($f_u CL_{\text{int}} \ll Q_H$): $CL_H \approx f_u CL_{\text{int}}$.
Clearance tracks enzyme activity directly, so inhibiting the enzyme changes
exposure roughly proportionally. Most psychiatric drugs live here, which is
why CYP inhibition is clinically consequential for them.

**High extraction** ($f_u CL_{\text{int}} \gg Q_H$): $CL_H \approx Q_H$.
Clearance is perfusion-limited and nearly insensitive to enzyme activity, so
the same inhibitor produces little change in systemic clearance. The
interaction instead appears as increased **oral bioavailability**, because
$F_H = 1 - E_H$ rises when $CL_{\text{int}}$ falls.

The same inhibitor therefore acts through completely different mechanisms
depending on where the substrate sits on this curve, and the extraction ratio
is what tells you which. This is why the panel reports $E_H$ and its
classification alongside the clearance numbers rather than the clearance alone.

---

## XVII. Optimal Experimental Design

Bayesian estimation asks: given these levels, what are this patient's
parameters? This section asks the question that comes first: *when should the
levels be drawn?*

### 17.1 Sensitivity and the information matrix

Model the observation at time $t_i$ as

$$
y_i = c(t_i; \theta) + \varepsilon_i, \qquad
\operatorname{Var}(\varepsilon_i) = (\sigma_{\text{prop}} c_i)^2 + \sigma_{\text{add}}^2
$$

with $\theta = (\log CL, \log V_d, \log k_a)$. Log parameterisation matches the
Bayesian module and makes the matrix scale-free, so a determinant comparison is
not dominated by whichever parameter happens to have the largest units.

The sensitivity vector is $s_i = \partial c(t_i) / \partial \theta$, and for
independent observations the Fisher information matrix is

$$
\mathcal{I}(\theta) = \sum_i \frac{s_i s_i^{\!\top}}{\operatorname{Var}(\varepsilon_i)}
$$

Two structural facts follow immediately and are both asserted in the tests.
The sum makes information **additive** across samples, so adding an observation
can never reduce it. And each term is an outer product of rank one, so $n$
samples give a matrix of rank at most $n$: **fewer samples than parameters
leaves $\mathcal{I}$ singular**, and no amount of clever placement fixes it.

Dividing by the variance is what stops the optimiser from stacking every sample
at the concentration peak. The peak carries the largest signal, but under a
proportional error model it carries proportionally the largest noise, so it is
not automatically the most informative place to look. A consequence worth
noting: under purely proportional error the FIM is **independent of dose**, so
a larger dose buys no additional parameter information.

### 17.2 D-optimality

The asymptotic covariance of the maximum-likelihood estimate is
$\mathcal{I}^{-1}$, so the joint confidence ellipsoid has volume proportional
to $|\mathcal{I}|^{-1/2}$. Minimising that volume means

$$
\xi^\star = \arg\max_{\xi} \; \log \det \mathcal{I}(\theta, \xi)
$$

over sampling schedules $\xi$. Reported alongside it are the per-parameter
relative standard errors $100\sqrt{(\mathcal{I}^{-1})_{jj}}$, which are already
relative because the parameters are logs, the parameter correlation matrix, and
the condition number of $\mathcal{I}$. A large condition number is the warning
sign: it means some direction in parameter space is nearly uninformed, which is
the same pathology section XVIII treats as practical non-identifiability.

Designs are compared with **D-efficiency**, normalised per parameter so the
number is interpretable:

$$
\text{Eff}_D = \left( \frac{|\mathcal{I}_{\text{ref}}|}{|\mathcal{I}^\star|} \right)^{1/p}
$$

### 17.3 Why this matters clinically

Routine therapeutic drug monitoring collects a trough level. For the
three-parameter model a trough-only schedule scores a D-efficiency **under 5%**
against the optimal design; for the seeded fluoxetine parameters it rounds to
zero. The reason is structural rather than numerical: at trough the profile is
a single decaying exponential, so the absorption sensitivity has essentially
vanished and the clearance and volume sensitivities have become nearly
collinear. The samples are real, the needle is real, and the information is
close to nil.

The optimal three-point design instead spreads across distinct kinetic phases,
one sample in absorption, one near the peak, one deep in elimination, because
each phase is where a different parameter's sensitivity is largest. This is the
practical payoff: **two well-placed samples can identify parameters that six
badly placed samples cannot.**

The search is exhaustive over a discrete grid of candidate times. That is
$\binom{|\text{grid}|}{n}$ determinant evaluations, so the grid is coarsened
automatically when the count would exceed the budget, and the step actually
used is reported rather than hidden.

---

## References

### Core PK/PD
1. Gibaldi M, Perrier D. *Pharmacokinetics*. 2nd ed. Marcel Dekker; 1982.
2. Rowland M, Tozer TN. *Clinical Pharmacokinetics and Pharmacodynamics*. 4th ed. Lippincott; 2011.
3. Stahl SM. *Stahl's Essential Psychopharmacology*. 5th ed. Cambridge University Press; 2021.

### Enzyme Kinetics & DDI
4. Michaelis L, Menten ML. *Biochem Z*. 1913;49:333-369.
5. FDA Guidance. *In Vitro Drug Interaction Studies*. January 2020.
6. ICH M12 Guideline. *Drug Interaction Studies*. May 2024.
7. Fahmi OA et al. *Drug Metab Dispos*. 2008;36(8):1698-1708.
8. Yang J et al. *Curr Drug Metab*. 2008;9(5):384-394.
9. Mayhew BS et al. *Drug Metab Dispos*. 2000;28(9):1031-1037.
10. Rostami-Hodjegan A, Tucker GT. *Nat Rev Drug Discov*. 2007;6:140-148.

### Population PK & Pharmacogenomics
11. Sheiner LB, Beal SL. *J Pharmacokinet Biopharm*. 1980;8(6):553-571.
12. Mould DR, Upton RN. *CPT Pharmacometrics Syst Pharmacol*. 2013;2:e38.
13. Caudle KE et al. *Clin Transl Sci*. 2020;13(1):116-124.
14. Hicks JK et al. *Clin Pharmacol Ther*. 2015;98(2):127-134.

### Specific Drug PK
15. Altamura AC et al. *Clin Pharmacokinet*. 1994;26(3):201-214.
16. Hiemke C et al. *Pharmacopsychiatry*. 2018;51(01/02):9-62.

### Graph Theory
17. Fiedler M. *Czechoslovak Math J*. 1973;23(2):298-305.
18. Cvetković D et al. *Theory of Graph Spectra*. Cambridge; 2010.
19. König D. *Matematikai és Fizikai Lapok*. 1931;38:116-119.
20. Ford LR, Fulkerson DR. *Flows in Networks*. Princeton; 1962.
21. Ramsey FP. *Proc London Math Soc*. 1930;s2-30(1):264-286.
22. Birkhoff GD. *Ann Math*. 1912;14(1/4):42-46.
23. Gutman I, Harary F. *Utilitas Math*. 1983;24:97-106.

### Stochastic Analysis & Control
24. Kloeden PE, Platen E. *Numerical Solution of SDEs*. Springer; 1992.
25. Donnet S, Samson A. *Adv Drug Deliv Rev*. 2013;65(7):929-939.
26. Nestorov I. *Expert Opin Drug Metab Toxicol*. 2007;3(2):235-249.
27. Pontryagin LS et al. *Mathematical Theory of Optimal Processes*. 1962.
28. Bellman R. *Dynamic Programming*. Princeton; 1957.

### Information Theory & Stochastic Processes
29. Shannon CE. *Bell System Technical Journal*. 1948;27(3):379-423.
30. Norris JR. *Markov Chains*. Cambridge; 1997.

### Topological Data Analysis
31. Edelsbrunner H, Harer J. *Computational Topology*. AMS; 2010.
32. Carlsson G. *Bull Amer Math Soc*. 2009;46(2):255-308.

### Game Theory
33. Roughgarden T. *Twenty Lectures on Algorithmic Game Theory*. Cambridge; 2016.
34. Rosenthal RW. *Int J Game Theory*. 1973;2:65-67.

---

