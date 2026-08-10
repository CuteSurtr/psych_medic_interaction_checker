# NeuroTrace

> *A computational pharmacokinetic engine for psychiatric drug-drug interaction modeling*

**Psychiatric medication changes are blind decisions.** When a prescriber switches a patient from fluoxetine to venlafaxine, they know the transition matters — but they can't *see* what happens. Fluoxetine's active metabolite (norfluoxetine, $t_{1/2} = 4$–$16$ days) lingers for weeks, silently inhibiting CYP2D6 and elevating co-prescribed drug levels long after the last pill. A patient stops smoking during an inpatient admission, and their clozapine levels double within days as CYP1A2 induction disappears — but no one rechecks the level until seizures start.

**NeuroTrace makes the invisible visible.**

It simulates multi-drug pharmacokinetic interactions in real time using a system of coupled nonlinear ordinary differential equations with Michaelis-Menten enzyme kinetics, dynamic enzyme pool modeling (synthesis, degradation, mechanism-based inhibition, and induction), competitive CYP450 inhibition, active metabolite tracking, and Bayesian parameter estimation. Built for psychiatric mental health nurse practitioners and psychiatrists managing complex medication regimens.

> **Disclaimer:** NeuroTrace is an **educational and research tool**. It does **not** constitute medical advice and should not be used as a sole basis for clinical decision-making. Always verify findings with current FDA labeling, clinical references, and independent clinical judgment.

> **Primary literature** backing every model - enzyme kinetics, mechanism-based inhibition, Hunter serotonin criteria, ACB scale, Beers criteria, CPIC phenotypes, D2 occupancy thresholds, Bayesian individualisation - is cited with DOIs in [REFERENCES.md](REFERENCES.md), mapped to the module that implements it.

> **Formal mathematical derivations** — definitions, theorems, proofs, and references underlying every model in NeuroTrace — live in [MATHEMATICAL_FOUNDATIONS.md](MATHEMATICAL_FOUNDATIONS.md). This README focuses on what NeuroTrace does and how to run it.

---

## What It Does

### 1. Interaction Engine
- Checks all pairwise drug-drug interactions in a psychiatric medication regimen (39 curated interactions + dynamic CYP450-derived rules)
- Flags serotonin syndrome risk using **mechanism-diversity scoring** — an MAOI + any reuptake inhibitor = Critical, not just "elevated risk"
- Quantifies QTc prolongation risk with **tiered agent classification** (high-risk: ziprasidone, methadone; moderate-risk: citalopram, haloperidol)
- Computes anticholinergic burden using the **validated ACB Scale** with age-adjusted Beers Criteria alerts
- Identifies CYP450 pathway conflicts (inhibitor + substrate on the same enzyme) with dynamic severity adjustment for metabolizer phenotypes
- Generates regimen-level warnings: duplicate drug classes, MAOI contraindications, polypharmacy alerts, elderly-specific risks

### 2. Pharmacokinetic Simulator
- Solves a **coupled multi-drug ODE system** (state dimension $2N + M + P$ for $N$ drugs, $M$ metabolites, $P$ enzyme pools) using `scipy.integrate.solve_ivp` with RK45
- Models **CYP450-mediated elimination** using Michaelis-Menten kinetics with **competitive inhibition** — the degree of inhibition depends on the time-varying concentration of the inhibitor
- Tracks **dynamic enzyme pool levels** via synthesis/degradation/inactivation kinetics (Yang et al., 2008), enabling accurate modeling of mechanism-based inhibition and enzyme recovery after drug discontinuation
- Models **enzyme induction** (e.g., smoking on CYP1A2) as increased enzyme synthesis with gradual onset and offset following enzyme turnover half-life (Fahmi et al., 2008)
- Tracks **active metabolites** (norfluoxetine, paliperidone, desvenlafaxine) as separate compartments that contribute to enzyme inhibition
- Applies **pharmacogenomic adjustments** (CYP2D6/CYP2C19 metabolizer phenotypes following CPIC guidelines)
- Handles complex **dose event scheduling**: start, stop, dose changes, titration schedules, cross-tapers
- Generates **concentration-time curves** with therapeutic range bands, dose event markers, and enzyme activity sub-plots

### 3. Graph-Theoretic Analysis
- Models the drug interaction network as a **weighted multigraph** $G = (V, E, w)$ and applies spectral graph theory
- Computes the **Laplacian spectrum** and **algebraic connectivity** $\lambda_2$ (Fiedler, 1973) to quantify regimen coupling — how tightly drugs are interactionally connected
- The **Fiedler vector** partitions the regimen into interaction clusters and identifies **bridge drugs** whose removal maximally decouples the network
- The **spectral radius** $\rho(\mathbf{W})$ and Perron eigenvector rank drugs by interaction centrality (Cvetković et al., 2010)
- Models the CYP450 drug-enzyme system as a **bipartite graph** $B = (V_D \cup V_E, E_B)$ with SVD-based metabolic pathway clustering
- Detects enzyme conflicts as length-2 paths and finds the **minimum vertex cover** (König, 1931) — the smallest set of drug removals to eliminate all metabolic conflicts
- Models drug metabolism as a **flow network** and applies the **max-flow min-cut theorem** (Ford & Fulkerson, 1962) to identify metabolic bottleneck enzymes
- Evaluates **three-drug (hypergraph) interactions** and computes the **independence polynomial** $I(G,x) = \sum_k i_k x^k$ for safe-subset enumeration
- Computes the **chromatic number** $\chi(G)$ for conflict graph partitioning and the **maximum independent set** $\alpha(G)$ for the largest safe drug subset

### 4. Advanced Mathematical Modeling
- **Monte Carlo simulation** of 10,000 virtual patients with population PK variability — produces confidence bands and toxicity probability estimates
- **Stochastic differential equations** (Milstein/Euler-Maruyama) for realistic "noisy" concentration curves capturing intra-individual variability
- **Optimal dose control** via discrete dynamic programming — computes mathematically optimal taper/titration schedules for cross-tapers and benzodiazepine discontinuation
- **Metabolic entropy** — Shannon entropy-based CYP Diversification Index (CDI) quantifies metabolic load concentration risk
- **Markov chain patient state model** — models clinical trajectories (Stable → Relapse → Remission) with drug-modified transition probabilities and expected first passage times
- **Topological data analysis** — persistent homology detects interaction loops and structural patterns via Vietoris-Rips filtration
- **Game-theoretic enzyme competition** — models CYP450 competition as a congestion game, computes Price of Anarchy, and recommends drug substitutions to minimize metabolic inefficiency

### 5. Clinical Scenario Library
Pre-built scenarios demonstrating real prescribing dilemmas:
- **SSRI-to-SNRI cross-taper** with aripiprazole — shows norfluoxetine's lingering CYP2D6 inhibition
- **Clozapine + smoking cessation** — CYP1A2 deinduction causes clozapine levels to rise 35–50%
- **Lamotrigine + valproic acid** — slower titration required to avoid Stevens-Johnson syndrome
- **CYP2D6 poor metabolizer on risperidone** — risperidone accumulates, paliperidone drops
- **Polypharmacy cascade** — 5-drug regimen with layered CYP and pharmacodynamic interactions

---

## Mathematical Foundations

NeuroTrace models multi-drug pharmacokinetic interactions using a system of coupled nonlinear ordinary differential equations with Michaelis-Menten enzyme kinetics, dynamic enzyme pool modeling, and Bayesian parameter estimation. The following equations describe the complete mathematical framework.

### 1. One-Compartment Oral Absorption Model (Bateman Function)

After a single oral dose $D$, plasma concentration over time (Gibaldi & Perrier, 1982):

$$C(t) = \frac{F \cdot D \cdot k_a}{V_d(k_a - k_e)} \left( e^{-k_e t} - e^{-k_a t} \right)$$

where $F$ = oral bioavailability, $k_a$ = absorption rate constant (h$^{-1}$), $k_e = CL / V_d$ = elimination rate constant (h$^{-1}$), and $V_d$ = apparent volume of distribution (L). The elimination half-life is:

$$t_{1/2} = \frac{\ln 2}{k_e} = \frac{0.693 \cdot V_d}{CL}$$

### 2. Multiple Dose Superposition at Steady State

For repeated oral dosing at interval $\tau$ hours, the steady-state peak and trough concentrations (Rowland & Tozer, 2011):

$$C_{ss,max} = \frac{F \cdot D \cdot k_a}{V_d(k_a - k_e)} \left( \frac{1}{1 - e^{-k_e \tau}} - \frac{1}{1 - e^{-k_a \tau}} \right)$$

$$C_{ss,min} = C_{ss,max} \cdot e^{-k_e \cdot \tau}$$

Average steady-state concentration:

$$\bar{C}_{ss} = \frac{F \cdot D}{CL \cdot \tau}$$

Time to reach steady state is approximately $4$–$5 \times t_{1/2}$.

### 3. Two-Compartment Model

For drugs with distribution phases (e.g., lithium, clozapine), the two-compartment model adds a peripheral compartment (Wagner, 1975):

$$\frac{dA_1}{dt} = -k_{10}A_1 - k_{12}A_1 + k_{21}A_2 + R_{in}(t)$$

$$\frac{dA_2}{dt} = k_{12}A_1 - k_{21}A_2$$

where $A_1$, $A_2$ are amounts in the central and peripheral compartments, $k_{10}$ is the elimination rate constant, and $k_{12}$, $k_{21}$ are inter-compartmental transfer rate constants. The analytical solution after IV bolus gives biexponential decay:

$$C(t) = A \cdot e^{-\alpha t} + B \cdot e^{-\beta t}$$

where $\alpha$ and $\beta$ are the macro rate constants:

$$\alpha, \beta = \frac{1}{2}\left[(k_{12} + k_{21} + k_{10}) \pm \sqrt{(k_{12} + k_{21} + k_{10})^2 - 4 k_{21} k_{10}}\right]$$

Implemented as an optional extension of `DrugConfig` in `backend/services/pk_simulator.py`: when `peripheral_vd_l`, `k12_per_h`, and `k21_per_h` are all supplied, the peripheral amount is appended to the ODE state vector and the central-plasma derivative gains the $-k_{12} A_1 + k_{21} A_2$ exchange flux. The simulation result exposes these as `peripheral_concentrations` alongside the regular central-compartment curve; drugs without the extra parameters continue to use the one-compartment model unchanged.

### 4. Michaelis-Menten (Saturable) Elimination

When enzyme systems become saturated at therapeutic concentrations (Michaelis & Menten, 1913):

$$\frac{dA}{dt} = R_{in}(t) - \frac{V_{max} \cdot C}{K_m + C}$$

At low concentrations ($C \ll K_m$), this approximates first-order kinetics: $\text{rate} \approx (V_{max}/K_m) \cdot C$. At high concentrations ($C \gg K_m$), elimination becomes zero-order: $\text{rate} \approx V_{max}$.

### 5. Competitive Inhibition of CYP450 Enzymes

**This is the core drug-drug interaction model.** When Drug B (inhibitor) competes with Drug A (substrate) for the same CYP enzyme (FDA DDI Guidance, 2020; ICH M12, 2024):

$$v_A = \frac{V_{max,A} \cdot C_A}{K_{m,A}\left(1 + \displaystyle\frac{C_B}{K_{i,B}}\right) + C_A}$$

where $K_{i,B}$ = inhibition constant of Drug B (lower $K_i$ = stronger inhibitor). The critical insight: **$C_B$ is not constant** — it changes over time as Drug B is absorbed, distributed, and eliminated, making the system a set of **coupled nonlinear ODEs**.

The FDA mechanistic static model predicts the AUC ratio:

$$\text{AUC ratio} = \frac{1}{1 - f_m \left(1 - \displaystyle\frac{1}{1 + [I]_u / K_{i,u}}\right)}$$

where $f_m$ = fraction metabolized by the affected enzyme, $[I]_u$ = unbound inhibitor concentration, and $K_{i,u}$ = unbound inhibition constant.

### 6. Mechanism-Based (Time-Dependent) Inhibition

Some drugs irreversibly inactivate CYP enzymes (e.g., paroxetine on CYP2D6). The enzyme must be resynthesized (Mayhew et al., 2000; Yang et al., 2008):

$$\frac{dE}{dt} = k_{synth} - k_{deg} \cdot E - \frac{k_{inact} \cdot C_I}{K_I + C_I} \cdot E$$

where $E$ = active enzyme amount (normalized, baseline = 1.0), $k_{synth} = k_{deg}$ at baseline, $k_{deg}$ = natural enzyme degradation rate constant, $k_{inact}$ = maximum inactivation rate constant, and $K_I$ = inhibitor concentration at half-maximal inactivation.

After inhibitor removal, enzyme recovery follows first-order resynthesis:

$$E(t) = E_{baseline} \left(1 - e^{-k_{deg} \cdot t}\right) + E_{inhibited} \cdot e^{-k_{deg} \cdot t}$$

**CYP enzyme degradation half-lives** (Yang et al., 2008):

| Enzyme | $k_{deg}$ (h$^{-1}$) | $t_{1/2,deg}$ (h) |
|--------|----------------------|-------------------|
| CYP1A2 | 0.0077 | 90 |
| CYP2C9 | 0.0087 | 80 |
| CYP2C19 | 0.0077 | 90 |
| CYP2D6 | 0.0136 | 51 |
| CYP3A4 (hepatic) | 0.0193 | 36 |

This is why fluoxetine's CYP2D6 inhibition persists for weeks — even after norfluoxetine clears, the enzyme must be resynthesized with $t_{1/2,deg} \approx 51$ hours for CYP2D6.

### 7. Enzyme Induction Kinetics

Enzyme inducers (e.g., carbamazepine, smoking/PAHs on CYP1A2) increase enzyme synthesis (Fahmi et al., 2008):

$$\frac{dE}{dt} = k_{synth} \cdot \left(1 + \frac{E_{max} \cdot C_{inducer}}{EC_{50} + C_{inducer}}\right) - k_{deg} \cdot E$$

At new steady state:

$$E_{ss,induced} = E_{baseline} \cdot \left(1 + \frac{E_{max} \cdot C_{inducer,ss}}{EC_{50} + C_{inducer,ss}}\right)$$

**Smoking cessation scenario:** When a smoker on clozapine quits, PAH-mediated CYP1A2 induction disappears. The enzyme level decays back to baseline with time constant $1/k_{deg}$ (CYP1A2 $t_{1/2,deg} \approx 90$ h). NeuroTrace models this dynamically — the enzyme pool gradually returns to baseline over $\sim$2–3 weeks, during which clozapine levels rise 35–70%.

### 8. Net Effect Model (Simultaneous Inhibition + Induction)

The net fold-change in intrinsic clearance combines reversible inhibition ($A$), mechanism-based inhibition ($B$), and induction ($C$) (Fahmi et al., 2008):

$$A = \frac{1}{1 + \displaystyle\frac{[I]_u}{K_{i,u}}} \quad \text{(reversible inhibition)}$$

$$B = \frac{k_{deg}}{k_{deg} + \displaystyle\frac{k_{inact} \cdot [I]_u}{K_{I,u} + [I]_u}} \quad \text{(mechanism-based inhibition)}$$

$$C = 1 + \frac{d \cdot E_{max} \cdot [I]_u}{EC_{50,u} + [I]_u} \quad \text{(induction)}$$

Net fold-change in intrinsic clearance = $A \cdot B \cdot C$

### 9. Multi-Drug Coupled ODE System

The complete system for $N$ drugs sharing $M$ enzymes, implemented in `pk_simulator.py` and solved by `scipy.integrate.solve_ivp` (Rostami-Hodjegan & Tucker, 2007). The state vector has dimension $2N + M_{met} + P$ (two compartments per drug, one per active metabolite, one per tracked enzyme pool).

**Drug compartments:**

$$\frac{dA_{gut,i}}{dt} = -k_{a,i} \cdot A_{gut,i} + \sum_{\text{doses}} D_i \cdot F_i \cdot \delta(t - t_{dose})$$

$$\frac{dA_{plasma,i}}{dt} = k_{a,i} \cdot A_{gut,i} - \sum_{j=1}^{P} \frac{V_{max,ij} \cdot C_i \cdot (E_j / E_{j,0})}{K_{m,ij} \cdot \left(1 + \displaystyle\sum_{k \neq i}^{N} \frac{C_k}{K_{i,kj}}\right) + C_i} - CL_{renal,i} \cdot C_i$$

**Dynamic enzyme pool:**

$$\frac{dE_j}{dt} = k_{synth,j} \cdot \left(1 + \sum_{i=1}^{N} \frac{E_{max,ij} \cdot C_i}{EC_{50,ij} + C_i}\right) - k_{deg,j} \cdot E_j - \sum_{i=1}^{N} \frac{k_{inact,ij} \cdot C_i}{K_{I,ij} + C_i} \cdot E_j$$

where $C_i = A_{plasma,i} / V_{d,i}$, $E_j$ = normalized enzyme pool level (baseline = 1.0), $V_{max,ij}$ = max metabolism rate of drug $i$ via enzyme $j$, $K_{m,ij}$ = Michaelis constant, $K_{i,kj}$ = competitive inhibition constant of drug $k$ on enzyme $j$, $k_{inact,ij}$ = time-dependent inactivation rate, $E_{max,ij}$ = maximum induction fold, and $\delta(t - t_{dose})$ = Dirac delta for dose events.

### 10. Active Metabolite Tracking

For drugs with clinically relevant active metabolites (Altamura et al., 1994):

$$\frac{dA_{norfluox}}{dt} = f_{met} \cdot \sum_{j} v_{fluox,j} - k_{e,norfluox} \cdot A_{norfluox}$$

Norfluoxetine is a potent CYP2D6 inhibitor ($K_i \approx 17$ nM). Its concentration feeds back into the inhibition term of the enzyme equation. Its half-life ($t_{1/2} \approx 4$–$16$ days) is much longer than fluoxetine ($t_{1/2} \approx 1$–$4$ days), which is why CYP2D6 inhibition persists for weeks after fluoxetine discontinuation.

### 11. Population PK — Nonlinear Mixed-Effects Model

For Bayesian estimation, individual PK parameters are drawn from population distributions (Sheiner & Beal, 1980; Mould & Upton, 2013):

$$\theta_i = \theta_{pop} \cdot e^{\eta_i}, \quad \eta_i \sim \mathcal{N}(0, \omega^2)$$

The Bayesian MAP estimation with therapeutic drug monitoring (TDM) data:

$$\hat{\eta}_i = \arg\min_{\eta} \left[ \sum_{j} \frac{(C_{obs,ij} - C_{pred,ij}(\eta))^2}{\sigma^2} + \eta^T \Omega^{-1} \eta \right]$$

The first term is the likelihood (fit to observed data), the second is the prior (population distribution). The posterior distribution $p(\theta | C_{obs}) \propto \mathcal{L}(C_{obs} | \theta) \cdot \pi(\theta)$.

Implemented in `backend/services/bayesian_pk.py` with log-normal population priors on $(\log CL, \log V_d)$, log-normal residual error, and a Bateman oral-superposition PK model. The MAP is found via BFGS and posterior covariance is the inverse Hessian at the MAP (Laplace approximation). Exposed through `POST /api/advanced/bayesian-pk`, which also returns a 95% credible band for the predictive curve derived from 500 Monte-Carlo draws of the posterior.

### 12. Pharmacogenomic Clearance Adjustment

CYP2D6 genotype-guided dosing following CPIC guidelines (Caudle et al., 2020):

$$CL_{adj} = CL_{pop} \cdot \left[\sum_j f_{m,j} \cdot AS_j + \left(1 - \sum_j f_{m,j}\right)\right]$$

where $f_{m,j}$ = fraction metabolized by enzyme $j$ and $AS_j$ = Activity Score for enzyme $j$ based on genotype.

| Phenotype | Activity Score | $AS$ multiplier |
|-----------|---------------|-----------------|
| Poor Metabolizer (PM) | 0 | 0.0–0.1 |
| Intermediate Metabolizer (IM) | 0.25–1.0 | 0.25–0.5 |
| Normal Metabolizer (NM) | 1.0–2.0 | 1.0 |
| Ultra-Rapid Metabolizer (UM) | > 2.0 | 1.5–3.0 |

**Example:** Aripiprazole is metabolized 65% by CYP3A4 and 35% by CYP2D6. A CYP2D6 PM has effective clearance = $CL \times (0.65 \times 1.0 + 0.35 \times 0.3) = 0.755 \times CL$, yielding $\sim$33% higher steady-state levels.

### 13. PBPK Liver Compartment (Well-Stirred Model)

The well-stirred liver model for hepatic clearance (Rowland et al., 1973; Ito & Houston, 2005):

$$CL_h = \frac{Q_h \cdot f_u \cdot CL_{int}}{Q_h + f_u \cdot CL_{int}}$$

where $Q_h$ = hepatic blood flow ($\sim$1.35 L/min), $f_u$ = fraction unbound in plasma, and $CL_{int} = \sum_j V_{max,j} / K_{m,j}$ = intrinsic clearance under linear conditions. Under competitive inhibition $CL_{int}$ becomes

$$CL_{int}(I) = \sum_j \frac{V_{max,j}/K_{m,j}}{1 + I_u / K_{i,j}}$$

yielding extraction ratio $E_h = CL_h / Q_h$ and first-pass fraction $F_h = 1 - E_h$. The Rowland/Wilkinson classification is low ($E_h < 0.3$), intermediate ($0.3 \leq E_h < 0.7$), or high ($E_h \geq 0.7$).

Implemented in `backend/services/hepatic_extraction.py`; exposed through `POST /api/advanced/hepatic-extraction`. Pulls $V_{max}$, $K_m$, and inhibitor $K_i$ directly from the CYP450 profile database and layers on DDI effects using steady-state plasma concentrations from the PK simulator.

### 14. Tissue Distribution (Reaction-Diffusion)

For drugs with slow tissue penetration (e.g., lithium into CNS), a PDE-based approach (de Lange, 2013):

$$\frac{\partial C(x,t)}{\partial t} = D \cdot \frac{\partial^2 C(x,t)}{\partial x^2} - k_e \cdot C(x,t) + S(x,t)$$

Blood-brain barrier flux (Robin boundary condition at $x=0$):

$$-D \cdot \left.\frac{\partial C}{\partial x}\right|_{x=0} = P_{eff} \cdot (f_u \cdot C_{plasma}(t) - C(0, t)), \quad \left.\frac{\partial C}{\partial x}\right|_{x=L} = 0$$

This explains the 2–4 week lag between starting an SSRI and clinical effect — the drug must equilibrate across the BBB and then downstream neuroadaptive changes (receptor downregulation) must occur.

Implemented in `backend/services/tissue_pde.py` via the method of lines: the spatial operator is discretized on a uniform 1-D grid with central finite differences and the resulting stiff ODE system is integrated with LSODA. Per-drug defaults for $P_{eff}$ and $f_u$ cover SSRIs/SNRIs, antipsychotics, mood stabilizers, and benzodiazepines. Exposed through `POST /api/advanced/tissue-pde` driven by the PK simulator output.

### 15. Receptor Occupancy Model (PD Link)

Connecting PK (drug levels) to PD (clinical effect) via the $E_{max}$ model (Meyer et al., 2004):

$$E(C) = E_0 + \frac{E_{max} \cdot C^{\gamma}}{EC_{50}^{\gamma} + C^{\gamma}}$$

For serotonin transporter (SERT) occupancy by SSRIs:

$$\text{SERT occupancy}(\%) = \frac{C_{plasma}}{C_{plasma} + K_d} \times 100$$

Published $K_d$ values: fluoxetine $\approx 0.8$ nM, sertraline $\approx 0.3$ nM, paroxetine $\approx 0.1$ nM. Clinical response typically requires >80% SERT occupancy.

Implemented in `backend/services/receptor_occupancy.py` with built-in $K_d$ profiles for ~25 psychiatric drugs across SERT, NET, DAT, D2, 5-HT2A, 5-HT1A, H1, M1, and α-adrenergic targets. Occupancy trajectories are auto-classified against clinical windows (SERT ≥ 80% therapeutic; D2 60–80% therapeutic, > 80% EPS risk). Exposed through `POST /api/advanced/receptor-occupancy`.

---

## Graph-Theoretic Foundations

NeuroTrace models the structural problem of drug interactions — which drugs interact with which, through which enzymes, creating which risk cascades — as a formal graph theory problem. This connects algebraic graph theory directly to clinical pharmacology.

### Weighted Interaction Multigraph

The drug interaction network is defined as a weighted undirected multigraph:

$$G = (V, E, w, \ell)$$

where $V = \{d_1, \ldots, d_n\}$ = medications (vertices), $E \subseteq \binom{V}{2}$ = interacting pairs (edges), $w: E \to \{1, 2, 3, 4\}$ maps severity (Minor=1, Moderate=2, Major=3, Critical=4), and $\ell: E \to \mathcal{P}(\{PK, PD\})$ encodes mechanism type. The weighted adjacency matrix $\mathbf{W} \in \mathbb{R}^{n \times n}$:

$$W_{ij} = \begin{cases} w(d_i, d_j) & \text{if } (d_i, d_j) \in E \\\\ 0 & \text{otherwise} \end{cases}$$

### Spectral Risk Analysis

The graph Laplacian $\mathbf{L} = \mathbf{D} - \mathbf{W}$ (where $D_{ii} = \sum_j W_{ij}$) has eigenvalues $0 = \lambda_1 \leq \lambda_2 \leq \cdots \leq \lambda_n$.

The **algebraic connectivity** $\lambda_2$ (Fiedler value) measures how tightly coupled the interaction network is. The corresponding **Fiedler vector** $\mathbf{v}_2$ partitions the drug set into two interaction clusters by sign:

$$\mathbf{L}\mathbf{v}_2 = \lambda_2 \mathbf{v}_2$$

The drug closest to zero in the Fiedler vector is the **bridge drug** — the node whose removal maximally decouples the network (Fiedler, 1973).

The **spectral radius** $\rho(\mathbf{W}) = \lambda_{max}(\mathbf{W})$ bounds the maximum cascading interaction intensity. By the Perron-Frobenius theorem, the corresponding eigenvector $\mathbf{v}_{max}$ has all non-negative entries, identifying the most interactionally central drug (Cvetković et al., 2010).

### Bipartite CYP450 Drug-Enzyme Network

The CYP450 metabolism system forms a bipartite graph $B = (V_D \cup V_E, E_B)$ where $V_D$ = drugs, $V_E$ = enzymes. The biadjacency matrix $\mathbf{M} \in \mathbb{R}^{n \times m}$ encodes substrate fractions, inhibitor potencies, and inducer effects. Its SVD $\mathbf{M} = \mathbf{U}\boldsymbol{\Sigma}\mathbf{V}^T$ clusters drugs by metabolic pathway similarity.

Enzyme conflicts are counted as length-2 paths through each enzyme node:

$$\text{Conflicts}(G) = \sum_{j=1}^{m} |V_{substrate}(e_j)| \cdot |V_{inhibitor}(e_j)|$$

The **minimum vertex cover** (König, 1931) identifies the smallest set of drug removals that eliminates all metabolic conflicts: $\nu(B) = \tau(B)$.

### Metabolic Flow Network

Drug metabolism through CYP450 enzymes is modeled as a capacitated flow network with enzyme capacities $c(d_i, e_j) = V_{max,ij}$. The **max-flow min-cut theorem** (Ford & Fulkerson, 1962) identifies the metabolic bottleneck:

$$\text{max flow} = \text{min cut}$$

### Polypharmacy Combinatorics

For $n$ concurrent medications, $\binom{n}{2}$ pairwise and $\binom{n}{3}$ triple interactions must be evaluated. The **independence polynomial** enumerates safe drug combinations of each size:

$$I(G, x) = \sum_{k=0}^{\alpha(G)} i_k \cdot x^k$$

where $i_k$ = number of independent sets of size $k$ in the conflict graph. The **chromatic number** $\chi(G)$ gives the minimum number of compatibility phases for safe sequential administration. The **maximum independent set** $\alpha(G)$ identifies the largest subset of drugs that can be taken together without major interactions.

By Ramsey's theorem, $R(3,3) = 6$: in any regimen of 6+ drugs, there must exist either 3 mutually interacting drugs or 3 mutually safe drugs (Ramsey, 1930).

---

## Advanced Mathematical Modeling

NeuroTrace extends beyond deterministic simulation with a suite of advanced mathematical methods spanning stochastic analysis, optimal control, information theory, algebraic topology, and algorithmic game theory.

### Stochastic Pharmacokinetics

#### Monte Carlo Population Simulation

PK parameters are drawn from log-normal population distributions and the ODE system is solved for $K$ virtual patients (Nestorov, 2007):

$$\theta_i = \theta_{pop} \cdot e^{\eta_i}, \quad \eta_i \sim \mathcal{N}(0, \omega^2)$$

Toxicity probability at each time point:

$$P(\text{toxic at } t) = \frac{1}{K}\sum_{k=1}^{K} \mathbb{1}\left[C^{(k)}(t) > C_{toxic}\right]$$

CYP2D6 polymorphism is modeled as a mixture distribution reflecting Caucasian population frequencies: PM (~7%), IM (~15%), NM (~70%), UM (~8%).

#### Itô SDE Pharmacokinetics

Deterministic ODEs are replaced with stochastic differential equations capturing intra-individual variability (Kloeden & Platen, 1992; Donnet & Samson, 2013):

$$dC_i = \mu_i(C, t)\,dt + \sigma_i \cdot C_i \cdot dW_i(t)$$

Solved numerically via the Milstein method:

$$C_i(t+\Delta t) = C_i(t) + \mu_i \Delta t + \sigma_i C_i \sqrt{\Delta t}\, Z + \tfrac{1}{2}\sigma_i^2 C_i \Delta t (Z^2 - 1)$$

The geometric Brownian motion structure ($\sigma_i \cdot C_i$) ensures concentrations remain non-negative.

### Optimal Dose Control

Given a clinical transition (e.g., SSRI-to-SNRI cross-taper), the optimizer minimizes a cost functional via discrete dynamic programming (Bellman, 1957; Pontryagin et al., 1962):

$$J[\mathbf{u}] = \sum_{t=0}^{T} \left[ \alpha \max(0, C - C_{max})^2 + \beta \max(0, C_{min} - C)^2 + \delta |\Delta D| \right]$$

subject to available tablet sizes and clinical constraints (washout periods, max daily reduction, Ashton taper rates for benzodiazepines). The optimizer produces a day-by-day dose schedule with human-readable recommendations.

### Information-Theoretic Metabolic Entropy

The CYP Diversification Index (CDI) quantifies how evenly the metabolic load is distributed across enzymes using Shannon entropy (Shannon, 1948):

$$\text{CDI} = \frac{H(\mathbf{p})}{\log_2 M}, \quad H(\mathbf{p}) = -\sum_{j=1}^{M} p_j \log_2 p_j$$

where $p_j = L_j / \sum_k L_k$ is the normalized metabolic load on enzyme $j$. CDI = 1.0 indicates perfectly diversified metabolism (lowest bottleneck risk); CDI near 0 indicates dangerous concentration on a single enzyme.

Kullback-Leibler divergence from the uniform distribution quantifies deviation from the ideal:

$$D_{KL}(\mathbf{p} \| \mathbf{u}) = \sum_j p_j \log_2 \frac{p_j}{1/M}$$

### Markov Chain Patient State Model

The patient's clinical trajectory is modeled as a discrete-time Markov chain (Norris, 1997) with states $S = \{\text{Stable, Partial Response, Relapse, Adverse Event, Hospitalized, Remission}\}$.

The stationary distribution $\boldsymbol{\pi} = \boldsymbol{\pi}\mathbf{P}$ gives the long-run fraction of time in each clinical state. Expected first passage times solve:

$$m_{ij} = 1 + \sum_{k \ne j} P_{ik} \cdot m_{kj}$$

Drug class effects modify transition probabilities: SSRIs increase transitions toward Remission, antipsychotics reduce Relapse probability, and all medications carry some adverse event risk.

### Topological Data Analysis — Persistent Homology

Persistent homology detects topological features in the drug interaction network (Edelsbrunner & Harer, 2010; Carlsson, 2009). The Vietoris-Rips complex is built from a distance matrix $d(d_i, d_j) = 1/w(d_i, d_j)$:

$$\text{VR}_\epsilon = \{\sigma \subseteq V : d(v_i, v_j) \leq \epsilon \text{ for all } v_i, v_j \in \sigma\}$$

Betti numbers track connected components ($\beta_0$) and interaction loops ($\beta_1$) as the filtration parameter increases. Persistent $\beta_1$ cycles reveal metabolic feedback loops (A inhibits B's enzyme, B inhibits C's enzyme, C induces A's enzyme).

### Algorithmic Game Theory — Enzyme Competition

Drug competition for CYP450 capacity is modeled as an N-player congestion game (Roughgarden, 2016; Rosenthal, 1973). The social cost quantifies total metabolic inefficiency:

$$SC(\mathbf{C}) = \sum_i \left(\frac{CL_{i,\text{ideal}}}{CL_{i,\text{eff}}} - 1\right)^2$$

The Price of Anarchy (PoA) measures how much worse the competitive outcome is compared to the cooperative optimum. A drug substitution recommender identifies replacements that minimize social cost — e.g., replacing fluoxetine (strong CYP2D6 inhibitor) with sertraline (minimal CYP2D6 impact) when aripiprazole is co-prescribed.

---

## Clinical Scenario: SSRI-to-SNRI Cross-Taper

**Patient:** 34F on fluoxetine 40 mg + aripiprazole 10 mg for 8 weeks with partial response. Clinician decides to cross-taper to venlafaxine XR.

**The problem:** Fluoxetine's metabolite (norfluoxetine, $t_{1/2} = 4$–$16$ days) continues inhibiting CYP2D6 for weeks after discontinuation. During this window, aripiprazole levels remain elevated, increasing risk of akathisia and EPS. Premature venlafaxine initiation while fluoxetine levels remain significant creates serotonin toxicity risk.

**NeuroTrace shows:** The concentration-time plot displays fluoxetine decay, norfluoxetine persistence, and aripiprazole elevation over 8 weeks. The enzyme activity sub-plot — now driven by the dynamic enzyme pool model — shows CYP2D6 activity recovering gradually with $t_{1/2,deg} \approx 51$ hours as norfluoxetine clears and the enzyme is resynthesized.

**Clinical insight:** Safe to start venlafaxine approximately 5 weeks after last fluoxetine dose. Aripiprazole dose should remain reduced until norfluoxetine has cleared and CYP2D6 pool has recovered.

---

## Clinical Scenario: Clozapine and Smoking Cessation

**Patient:** 45M with treatment-resistant schizophrenia, stable on clozapine 400 mg/day (levels 420 ng/mL). Smokes 20 cigarettes/day. Admitted to inpatient unit where smoking is prohibited.

**The problem:** Smoking induces CYP1A2 (via polycyclic aromatic hydrocarbons), which metabolizes $\sim$70% of clozapine. NeuroTrace models this as dynamic enzyme induction — the CYP1A2 enzyme pool is elevated to $\sim$1.5× baseline during active smoking. Upon cessation, the enzyme pool decays back to baseline with $t_{1/2,deg} \approx 90$ hours (CYP1A2 turnover). Over 2–4 weeks, clozapine clearance drops by $\sim$35%, and levels can rise 50–70%, potentially reaching the toxic range (>1000 ng/mL → seizures, myocarditis).

**NeuroTrace shows:** Simulating with `smoking=True` (baseline) vs. `smoking=False` (post-cessation) demonstrates the predicted rise in clozapine concentrations and the need for proactive 25–33% dose reduction.

---

## Architecture

```mermaid
flowchart LR
  subgraph client [Browser]
    UI["React + Tailwind + D3.js + Recharts"]
  end
  subgraph vercel [Vercel - default]
    FN["Python function - FastAPI, api/index.py<br/>serves /api/* and the built SPA"]
    MEM[(In-memory SQLite - seeded at cold start)]
  end
  subgraph compose [Docker Compose - optional, local]
    NG[Nginx - static UI + API proxy]
    API["FastAPI - interaction engine + PK solver"]
    PG[(PostgreSQL - durable storage)]
  end
  UI --> FN
  FN --> MEM
  FN -->|scipy.solve_ivp| ODE[ODE Solver]
  UI -.-> NG
  NG -.->|/api/*| API
  API -.-> PG
```

The two deployments run the same application code. The only difference is
`DATABASE_URL`: unset, the API builds an in-memory SQLite database and seeds it
from `seed_data.py` at startup; set to a Postgres URL, it uses that instead.
The reference data is static, so nothing is lost by rebuilding it per cold
start.

- **Frontend:** React 18 (TypeScript), Tailwind CSS, **D3.js** (force-directed interaction graph + concentration-time curves), **Recharts** (risk summary charts)
- **Backend:** Python **FastAPI**, SQLAlchemy ORM, **NumPy + SciPy** (`solve_ivp` for ODE integration with dynamic enzyme pools)
- **Database:** SQLite in-memory by default, PostgreSQL when `DATABASE_URL` is set. Curated seed data: 50 psychiatric medications with published PK parameters, 78 CYP450 enzyme profiles with Ki/Km/Vmax values, 39 interaction rules, 5 clinical scenarios

---

## Data Sources

- **PK parameters** ($F$, $V_d$, $CL$, $k_a$, $t_{1/2}$): FDA-approved prescribing information (package inserts)
- **Therapeutic ranges**: AGNP Consensus Guidelines for TDM in Neuropsychopharmacology (Hiemke et al., 2018)
- **CYP450 profiles** ($K_i$, $K_m$, $V_{max}$, $f_m$): in vitro enzyme kinetic studies from FDA labels and Stahl's Essential Psychopharmacology (5th ed.)
- **Enzyme degradation half-lives** ($k_{deg}$): Yang et al., 2008
- **Interaction rules**: FDA drug safety communications, Stahl's, published case reports
- **Anticholinergic scores**: Anticholinergic Cognitive Burden (ACB) Scale (Boustani et al., 2008)
- **Beers Criteria**: American Geriatrics Society 2023 Updated AGS Beers Criteria
- **Pharmacogenomics**: CPIC Guidelines (Caudle et al., 2020; Hicks et al., 2015)

Each parameter is annotated with its source in the seed data files (`backend/database/seed_data.py`).

**Coverage boundary.** 50 of the 115 medications carry full PK parameters ($CL$, $V_d$, $k_a$); the remaining 65 have interaction, CYP450 and half-life data only. Those entries are complete for the interaction and risk analyses, which is what they are used for, but cannot drive the compartmental model: $t_{1/2} = \ln 2 \cdot V_d / CL$ is one equation in two unknowns, and $k_a$ additionally needs $t_{max}$, so the missing parameters are not recoverable from what is present. Rather than invent values, `/api/medications/pk-complete` reports which medications support the PK-model analyses, the search response carries a `has_pk_parameters` flag, and the Design & Diagnostics panels select a usable medication themselves.

---

## Deploying to Vercel

The repository is configured for Vercel out of the box and needs no database,
no environment variables, and no external services.

```bash
vercel deploy
```

| Service | URL |
|---------|-----|
| App | https://psych-medic-interaction-checker-git-main-cutesurtrs-projects.vercel.app/ |
| API (Swagger) | https://psych-medic-interaction-checker-git-main-cutesurtrs-projects.vercel.app/docs |
| API (ReDoc) | https://psych-medic-interaction-checker-git-main-cutesurtrs-projects.vercel.app/redoc |
| Deploy health check | https://psych-medic-interaction-checker-git-main-cutesurtrs-projects.vercel.app/api/__status |

`vercel.json` wires it up:

- `frontend/` is built with Vite into `frontend/dist`
- `api/index.py` exposes the FastAPI app, which serves **both** the API and the
  built SPA. `includeFiles` puts `backend/` and `frontend/dist/` in the
  function bundle.
- There are **no rewrites**. Vercel detects this as a FastAPI backend project
  and routes every request to the application, so a rewrite pointing at
  `/index.html` is handed straight back to FastAPI and 404s. Instead the app
  mounts `/assets` and falls back to `index.html` for any non-API path, which
  is what makes client-side routes deep-link correctly.

Two design changes make the API work on serverless, where a request cannot rely
on state written by a previous one:

- `POST /api/simulation/run` configures and runs a simulation in a single
  request. The older `POST /api/simulation/create` plus
  `GET /api/simulation/{id}/run` pair is still available for deployments backed
  by a real database.
- The analysis endpoints (`tissue-pde`, `receptor-occupancy`,
  `hepatic-extraction`) accept an inline `simulation` object as well as a
  `simulation_id`.

### Deployment self-check

`GET /api/__status` reports whether seeding succeeded, the Python version, and
the number of registered routes. It is the fastest way to confirm a deploy is
healthy.

### Keep the `app` binding at the top level

Vercel detects this project as a FastAPI backend and statically scans
`api/index.py` for a module-level `app`. `from main import app` must stay
unconditional at the top level. Wrapping it in `try`/`except` hides it from
that scan and fails the build with *"Found api/index.py but it does not define
a top-level `app` FastAPI instance"*.

### Troubleshooting a crashed function

If `/api/*` returns 500, check `vercel logs` - the Python runtime prints the
full import traceback there.

Do **not** override `installCommand` in `vercel.json`. Doing so suppresses the
`pip install -r requirements.txt` step for the whole project, and the function
then fails with `ModuleNotFoundError: No module named 'sqlalchemy'`. A copy of
the requirements lives at `api/requirements.txt` as well, because
`@vercel/python` resolves a requirements file next to the entrypoint before
falling back to the project root.

To use durable storage instead, set `DATABASE_URL` to a Postgres connection
string (Neon, Supabase, Vercel Postgres) in the project's environment
variables. Nothing else changes.

Optional environment variables:

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | `sqlite://` (in-memory) | Postgres URL for durable storage |
| `CORS_ORIGINS` | localhost dev origins | Comma-separated allowed browser origins. Not needed on Vercel, where the SPA and API share an origin |

---

## Quick Start

### Docker Compose (optional, for local Postgres)

```bash
cd neurotrace
docker compose up --build
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| API (Swagger) | http://localhost:8000/docs |
| PostgreSQL | localhost:5433 (user: `neurotrace`, db: `neurotrace`) |

Docker Compose keeps the three-service split, with Nginx serving the SPA and
Postgres for durable storage. The Vercel deployment differs: there the single
FastAPI application serves both the API and the built SPA (see below).

The database is automatically seeded on first API startup with 50 medications, 78 CYP450 profiles, 39 interactions, and 5 clinical scenarios.

### Local Development

**Backend:**
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev    # Vite proxies /api to http://127.0.0.1:8000
```

---

## Testing

```bash
cd backend
pip install pytest numpy scipy
pytest -v
```

**295 tests** covering:

- **`test_enzyme_kinetics.py`** — Michaelis-Menten rate at $K_m$ (= $V_{max}/2$), competitive inhibition math, enzyme activity factors
- **`test_risk_calculator.py`** — Mechanism-aware serotonin syndrome scoring (MAOI + SSRI = Critical), tiered QTc risk, anticholinergic burden, CNS depression
- **`test_pk_simulator.py`** — Dose scheduler event generation, steady-state convergence, **CYP2D6 inhibition effect** (fluoxetine increases aripiprazole AUC ≥1.3×, matching FDA label), **norfluoxetine persistence** after fluoxetine discontinuation, **smoking cessation** effect on clozapine levels (≥1.2× increase via dynamic CYP1A2 enzyme pool), **enzyme pool dynamics** (unit tests for `enzyme_pool_derivative`, integration tests for MBI-mediated enzyme depletion and post-discontinuation recovery with $t_{1/2,deg} \approx 51$ h for CYP2D6)
- **`test_graph_analysis.py`** — Spectral graph theory ($\lambda_1 = 0$, $\lambda_2 > 0$ for connected graphs, $\rho(K_n) = w(n-1)$), chromatic number ($\chi(K_4) = 4$), independence polynomial ($I(K_n, x) = 1 + nx$ for conflict graphs), Fiedler vector partition for disconnected clusters, **bipartite conflict detection** (substrate × inhibitor counting), **König minimum cover**, **max-flow/min-cut** bottleneck identification, **three-drug interaction detection** (lithium + NSAID + ACE inhibitor triple whammy), **Ramsey $R(3,3)=6$** verification on 6-drug regimens
- **`test_optimal_design.py`**, **`test_sensitivity_analysis.py`**, **`test_treatment_mdp.py`**, **`test_identifiability.py`** — the design and diagnostics layer, validated against cases with known answers rather than by inspection: Sobol indices against the analytic Ishigami decomposition and against $AUC_{0-\infty} = F\!\cdot\!D/CL$; Fisher information for additivity, singularity when under-sampled and dose-invariance under proportional error; the MDP value function against the Bellman optimality equation with policy iteration and value iteration cross-checked; identifiability against schedules whose rank is known by construction
- **`test_stateless_api.py`** — the database-free deployment path: schema builds on SQLite, reference data seeds itself, brand-name search works without PostgreSQL array functions, the one-shot `POST /api/simulation/run` needs no prior request, analysis endpoints accept an inline simulation, and the stateless and persisted paths produce identical concentration curves
- **`test_advanced_math.py`** (40 tests) — **Monte Carlo** (CI ordering, toxicity probability, parameter perturbation), **optimal control** (taper schedules, titration, dose-level constraints, risk timelines), **SDE simulation** (Milstein vs. Euler-Maruyama, non-negativity, stochastic path variability, $\sigma=0$ determinism), **entropy analysis** (CDI near 0 for single-enzyme concentration, CDI near 1 for uniform distribution, KL divergence), **Markov chain** (stochastic matrix validation, stationary distribution, treatment effect on Remission probability, first passage times), **TDA** (persistent homology, $\beta_0$ component counting, $\beta_1$ loop detection, distance ordering), **game theory** (ideal vs. effective clearances, social cost, Price of Anarchy ≥ 1, no-competition baseline)

---

## API Surface

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/medications/search?q=` | Autocomplete search |
| `GET` | `/api/medications/{id}` | Full medication profile + CYP450 |
| `GET` | `/api/medications/{id}/pk-parameters` | PK parameters only |
| `GET` | `/api/medications/classes` | Distinct drug classes |
| `GET` | `/api/medications/pk-complete` | Medications whose entry can drive the compartmental model |
| `POST` | `/api/interactions/check` | Pairwise interactions for IDs |
| `GET` | `/api/cyp450/profile?medication_ids=1,2,3` | Enzyme buckets + conflict flags |
| `POST` | `/api/risk-summary` | Composite risk scores |
| `POST` | `/api/simulation/run` | **Configure and run in one request** (stateless; used by the UI) |
| `POST` | `/api/simulation/create` | Create simulation with dose schedules (needs durable storage) |
| `GET` | `/api/simulation/{id}/run` | Run ODE solver for a stored simulation |
| `GET` | `/api/simulation/templates` | List clinical scenario templates |
| `GET` | `/api/simulation/templates/{id}` | Load a scenario |
| `GET` | `/api/analysis/graph-metrics?medication_ids=` | Spectral graph analysis (Laplacian, Fiedler, $\chi$, $\alpha$) |
| `GET` | `/api/analysis/bipartite-metrics?medication_ids=` | CYP450 bipartite analysis (SVD, conflicts, König cover) |
| `GET` | `/api/analysis/metabolic-flow?medication_ids=` | Max-flow/min-cut bottleneck identification |
| `GET` | `/api/analysis/combinatorics?medication_ids=` | Polypharmacy combinatorics + three-drug interactions |
| `POST` | `/api/advanced/optimizer/taper` | Optimal taper/titration schedule via dynamic programming |
| `POST` | `/api/advanced/monte-carlo` | Population variability envelope with therapeutic-window probabilities |
| `POST` | `/api/advanced/optimal-design` | D-optimal TDM sampling times (Fisher information) |
| `POST` | `/api/advanced/sensitivity` | Sobol first-order and total-effect indices |
| `POST` | `/api/advanced/treatment-policy` | Optimal state-dependent policy (MDP, policy iteration) |
| `POST` | `/api/advanced/identifiability` | Sensitivity rank, collinearity index, profile likelihood |
| `GET`  | `/api/__status` | Deployment health check (seeding, Python version, route count) |
| `POST` | `/api/advanced/simulation/stochastic` | SDE simulation (Milstein/Euler-Maruyama) |
| `GET` | `/api/advanced/entropy?medication_ids=` | CYP Diversification Index (Shannon entropy) |
| `POST` | `/api/advanced/markov` | Markov chain patient state transition model |
| `GET` | `/api/advanced/topology?medication_ids=` | Persistent homology (TDA) of interaction network |
| `POST` | `/api/advanced/game-theory` | Enzyme competition game theory (PoA, social cost) |

---

## Roadmap

- **Bayesian parameter estimation**: PyMC integration for posterior updating with therapeutic drug monitoring (TDM) data — personalized PK models with credible intervals
- **Two-compartment models**: Distribution-phase modeling for drugs with multiexponential disposition (lithium, clozapine)
- **FHIR interoperability**: Read medication lists from EHR systems via SMART on FHIR
- **Population PK**: Integrate published PopPK models for key drugs (clozapine, lithium, valproic acid)
- **PBPK liver model**: Full physiologically-based hepatic clearance with portal vein and hepatic artery contributions
- **Receptor occupancy visualization**: SERT/D2 occupancy curves linked to concentration-time plots
- **Mobile-responsive PWA**: Optimized for clinic tablet use (iPad-sized screens)
- **Expanded drug database**: Non-psychiatric medications that commonly interact with psych meds (macrolide antibiotics, azole antifungals, ciprofloxacin, antiretrovirals)
- **ML-based adverse event prediction**: Train on FDA FAERS data for combination-specific risk estimates

---

## References

### Core PK/PD Textbooks

1. Stahl SM. *Stahl's Essential Psychopharmacology: Neuroscientific Basis and Practical Applications*. 5th ed. Cambridge University Press; 2021.
2. Rowland M, Tozer TN. *Clinical Pharmacokinetics and Pharmacodynamics: Concepts and Applications*. 4th ed. Lippincott Williams & Wilkins; 2011.
3. Gibaldi M, Perrier D. *Pharmacokinetics*. 2nd ed. Marcel Dekker; 1982.

### Drug-Drug Interaction Modeling

4. FDA Guidance for Industry. *In Vitro Drug Interaction Studies — Cytochrome P450 Enzyme- and Transporter-Mediated Drug Interactions*. January 2020.
5. ICH M12 Guideline. *Drug Interaction Studies*. Step 5. May 2024.
6. Fahmi OA, Maurer TS, Kish M, et al. A combined model for predicting CYP3A4 clinical net drug-drug interaction based on CYP3A4 inhibition, inactivation, and induction determined in vitro. *Drug Metab Dispos*. 2008;36(8):1698-1708. DOI: [10.1124/dmd.107.018663](https://doi.org/10.1124/dmd.107.018663)
7. Rostami-Hodjegan A, Tucker GT. Simulation and prediction of in vivo drug metabolism in human populations from in vitro data. *Nat Rev Drug Discov*. 2007;6:140-148. DOI: [10.1038/nrd2173](https://doi.org/10.1038/nrd2173)

### CYP450 Enzyme Kinetics

8. Michaelis L, Menten ML. Die Kinetik der Invertinwirkung. *Biochem Z*. 1913;49:333-369.
9. Yang J, Liao M, Shou M, et al. Cytochrome P450 turnover: regulation of synthesis and degradation, methods for determining rates, and implications for the prediction of drug interactions. *Curr Drug Metab*. 2008;9(5):384-394. DOI: [10.2174/138920008784746382](https://doi.org/10.2174/138920008784746382)
10. Mayhew BS, Jones DR, Hall SD. An in vitro model for predicting in vivo inhibition of cytochrome P450 3A4 by metabolic intermediate complex formation. *Drug Metab Dispos*. 2000;28(9):1031-1037.

### Pharmacogenomics

11. Caudle KE, Sangkuhl K, Whirl-Carrillo M, et al. Standardizing CYP2D6 genotype to phenotype translation: consensus recommendations from the Clinical Pharmacogenetics Implementation Consortium and Dutch Pharmacogenetics Working Group. *Clin Transl Sci*. 2020;13(1):116-124. DOI: [10.1111/cts.12692](https://doi.org/10.1111/cts.12692)
12. Hicks JK, Bishop JR, Sangkuhl K, et al. Clinical Pharmacogenetics Implementation Consortium (CPIC) guideline for CYP2D6 and CYP2C19 genotypes and dosing of selective serotonin reuptake inhibitors. *Clin Pharmacol Ther*. 2015;98(2):127-134. DOI: [10.1002/cpt.147](https://doi.org/10.1002/cpt.147)

### Population PK & Bayesian Methods

13. Sheiner LB, Beal SL. Evaluation of methods for estimating population pharmacokinetic parameters. I. Michaelis-Menten model: routine clinical pharmacokinetic data. *J Pharmacokinet Biopharm*. 1980;8(6):553-571. DOI: [10.1007/BF01060053](https://doi.org/10.1007/BF01060053)
14. Mould DR, Upton RN. Basic concepts in population modeling, simulation, and model-based drug development — Part 2: Introduction to pharmacokinetic modeling methods. *CPT Pharmacometrics Syst Pharmacol*. 2013;2:e38. DOI: [10.1038/psp.2013.14](https://doi.org/10.1038/psp.2013.14)

### Specific Drug PK Data

15. Altamura AC, Moro AR, Percudani M. Clinical pharmacokinetics of fluoxetine. *Clin Pharmacokinet*. 1994;26(3):201-214. DOI: [10.2165/00003088-199426030-00004](https://doi.org/10.2165/00003088-199426030-00004)
16. Huang ML, Van Peer A, Woestenborghs R, et al. Pharmacokinetics of the novel antipsychotic agent risperidone and the prolactin response in healthy subjects. *Clin Pharmacol Ther*. 1993;54(3):257-268.
17. Hiemke C, Bergemann N, Clement HW, et al. Consensus guidelines for therapeutic drug monitoring in neuropsychopharmacology: update 2017. *Pharmacopsychiatry*. 2018;51(01/02):9-62. DOI: [10.1055/s-0043-116492](https://doi.org/10.1055/s-0043-116492)

### PBPK Modeling

18. Rowland M, Benet LZ, Graham GG. Clearance concepts in pharmacokinetics. *J Pharmacokinet Biopharm*. 1973;1(2):123-136. DOI: [10.1007/BF01059626](https://doi.org/10.1007/BF01059626)
19. Ito K, Houston JB. Prediction of human drug clearance from in vitro and preclinical data using physiologically based and empirical approaches. *Pharm Res*. 2005;22(1):103-112.
20. de Lange ECM. Utility of CSF in translational neuroscience. *J Pharmacokinet Pharmacodyn*. 2013;40(3):315-326. DOI: [10.1007/s10928-013-9301-9](https://doi.org/10.1007/s10928-013-9301-9)

### Serotonin Transporter Occupancy

21. Meyer JH, Wilson AA, Sagrati S, et al. Serotonin transporter occupancy of five selective serotonin reuptake inhibitors at different doses: an [11C]DASB positron emission tomography study. *Am J Psychiatry*. 2004;161(5):826-835. DOI: [10.1176/appi.ajp.161.5.826](https://doi.org/10.1176/appi.ajp.161.5.826)

### Clinical Pharmacology

22. Boustani M, Campbell NL, Munger S, et al. Impact of anticholinergics on the aging brain: a review and practical application. *Aging Health*. 2008;4(3):311-320.
23. By the 2023 American Geriatrics Society Beers Criteria Update Expert Panel. American Geriatrics Society 2023 updated AGS Beers Criteria. *J Am Geriatr Soc*. 2023;71(7):2052-2077.
24. de Leon J, Armstrong SC, Cozza KL. A clinical guide for the use of clozapine plasma levels and fluvoxamine. *Psychosomatics*. 2005;46(4):315-318.
25. Wagner JG. *Fundamentals of Clinical Pharmacokinetics*. Drug Intelligence Publications; 1975.
26. Dumbreck S, Flynn A, Nairn M, et al. Drug-disease and drug-drug interactions: systematic examination of recommendations in 12 UK national clinical guidelines. *BMJ*. 2015;350:h949. DOI: [10.1136/bmj.h949](https://doi.org/10.1136/bmj.h949)

### Stochastic PK & Optimal Control

27. Nestorov I. Whole-body physiologically based pharmacokinetic models. *Expert Opin Drug Metab Toxicol*. 2007;3(2):235-249. DOI: [10.1517/17425255.3.2.235](https://doi.org/10.1517/17425255.3.2.235)
28. Kloeden PE, Platen E. *Numerical Solution of Stochastic Differential Equations*. Springer; 1992.
29. Donnet S, Samson A. A review on estimation of stochastic differential equations for pharmacokinetic/pharmacodynamic models. *Adv Drug Deliv Rev*. 2013;65(7):929-939. DOI: [10.1016/j.addr.2013.03.005](https://doi.org/10.1016/j.addr.2013.03.005)
30. Pontryagin LS, Boltyanskii VG, Gamkrelidze RV, Mishchenko EF. *The Mathematical Theory of Optimal Processes*. Wiley-Interscience; 1962.
31. Bellman R. *Dynamic Programming*. Princeton University Press; 1957.

### Information Theory & Stochastic Processes

32. Shannon CE. A Mathematical Theory of Communication. *Bell System Technical Journal*. 1948;27(3):379-423.
33. Norris JR. *Markov Chains*. Cambridge University Press; 1997.

### Topological Data Analysis

34. Edelsbrunner H, Harer J. *Computational Topology: An Introduction*. AMS; 2010.
35. Carlsson G. Topology and data. *Bull Amer Math Soc*. 2009;46(2):255-308. DOI: [10.1090/S0273-0979-09-01249-X](https://doi.org/10.1090/S0273-0979-09-01249-X)

### Algorithmic Game Theory

36. Roughgarden T. *Twenty Lectures on Algorithmic Game Theory*. Cambridge University Press; 2016.
37. Rosenthal RW. A class of games possessing pure-strategy Nash equilibria. *Int J Game Theory*. 1973;2:65-67. DOI: [10.1007/BF01737559](https://doi.org/10.1007/BF01737559)

### Graph Theory & Combinatorics

27. Fiedler M. Algebraic connectivity of graphs. *Czechoslovak Mathematical Journal*. 1973;23(2):298-305.
28. Cvetković D, Rowlinson P, Simić S. *An Introduction to the Theory of Graph Spectra*. Cambridge University Press; 2010.
29. König D. Gráfok és mátrixok. *Matematikai és Fizikai Lapok*. 1931;38:116-119.
30. Ford LR, Fulkerson DR. *Flows in Networks*. Princeton University Press; 1962.
31. Ahuja RK, Magnanti TL, Orlin JB. *Network Flows: Theory, Algorithms, and Applications*. Prentice Hall; 1993.
32. Ramsey FP. On a Problem of Formal Logic. *Proc London Math Soc*. 1930;s2-30(1):264-286. DOI: [10.1112/plms/s2-30.1.264](https://doi.org/10.1112/plms/s2-30.1.264)
33. Birkhoff GD. A Determinant Formula for the Number of Ways of Coloring a Map. *Ann Math*. 1912;14(1/4):42-46. DOI: [10.2307/1967597](https://doi.org/10.2307/1967597)
34. Oxley JG. *Matroid Theory*. 2nd ed. Oxford University Press; 2011.
35. Gutman I, Harary F. Generalizations of the matching polynomial. *Utilitas Math*. 1983;24:97-106.
36. Rota GC. On the foundations of combinatorial theory I. Theory of Möbius functions. *Z Wahrscheinlichkeitstheorie*. 1964;2:340-368. DOI: [10.1007/BF00531932](https://doi.org/10.1007/BF00531932)

---

## License

MIT License. See `LICENSE` for details.

This project is intended for **education, research, and portfolio demonstration**. It is **not** a medical device and is **not** intended for standalone clinical decision-making.
