# NeuroTrace PK Engine Audit

**Date:** 2026-08-15
**Commit audited:** `a8ee7c1`
**Scope:** `backend/services/{pk_simulator,enzyme_kinetics,metabolite_tracker,risk_calculator,constants}.py`, `backend/database/seed_data.py`
**Purpose:** Establish which parameters and mechanisms in the PK engine are evidence-grounded before any validation suite is built on top of them.

---

## Why this document exists first

The project plan puts the validation framework first and the equation audit near the end. This document exists because that order is unsafe.

Every quantitative knob available for tuning the three flagship demo scenarios is currently a fabricated constant. If a validation suite is built before those constants are sourced, the only way to make a scenario pass is to adjust invented numbers until they reproduce published results, and then cite those publications as validation. That is curve fitting wearing validation's clothes, and it is worse than no validation, because it converts an unexamined assumption into a passing test that future reviewers will trust.

The finding below that matters most is **F-1**: the enzyme de-induction half-life used by the clozapine demo is roughly 2.3x slower than the published measurement, and outside its confidence interval. That error is invisible without this audit and would have been silently absorbed into parameter tuning.

---

## Verdict

| | |
|---|---|
| Findings | 23 (2 resolved, 2 added by validation) |
| Blocking a flagship demo | 6 |
| Verified as correct | 4 |
| Citations verified against Crossref | 15 / 15 |
| Demo scenarios validatable today | **1 of 3** (Demo 2 passing, 5/5 endpoints) |

**Update 2026-08-15.** F-1 and F-2 are resolved and Demo 2 now validates against
published data. Standing up that validation immediately surfaced two further
findings, F-22 and F-23, neither of which was visible by reading the code. That
is the argument for this document existing, made concrete: the validation suite
failed first, and the failure localised to a parameter nobody had questioned.

The ODE machinery is structurally sound. `enzyme_pool_derivative` correctly implements the Fahmi/Yang synthesis-degradation-inactivation form, bioavailability is applied exactly once, and the compartment bookkeeping is standard. **The problem is almost entirely in the parameters fed to that machinery, not the machinery itself.** That is good news: the fixes are data and provenance work, not an engine rewrite.

---

## Evidence confidence convention

This audit distinguishes two separate things, because conflating them is the failure mode the project's evidence doctrine is designed to prevent:

- **`CITATION_VERIFIED`** means the DOI resolves via the Crossref API and the returned title, authors, journal, year, and pages match what is cited here. All 9 citations below are verified at this level.
- **`VALUE_LOW_CONFIDENCE`** means a specific numeric value is attributed to that paper on the basis of secondary sources (search result summaries, review articles) rather than reading the primary text. **These values must be checked against the original paper before entering the codebase.**

I verified that the papers exist and are the right papers. I did not read most of them in full. Every numeric value below carrying `VALUE_LOW_CONFIDENCE` is a candidate for implementation, not an established input.

---

## Findings

### CRITICAL

#### F-1. CYP1A2 de-induction half-life is ~2.3x too slow  `RESOLVED 2026-08-15`

> **Resolution.** `CYP_KDEG['CYP1A2']` now derives from the Faber & Fuhr
> measurement (t-half 38.6 h) via `services/sourced_params.py`, replacing the
> Yang in vitro figure. Modelled de-induction half-life is now 38.6 h, inside
> the published CI. Regression test:
> `test_cyp1a2_decay_follows_published_half_life`.
>
> **The audit's original recommendation was wrong** and is corrected here. It
> proposed adding a *separate* de-induction constant alongside `k_deg`. That is
> not physically coherent: a single enzyme pool has a single turnover rate, and
> both MBI recovery and de-induction are governed by it. The real situation is
> that Yang (~90 h) and Faber & Fuhr (38.6 h) *disagree by 2.3x* about what
> CYP1A2 turnover is. Faber & Fuhr is preferred because it measures in vivo, in
> humans, the exact quantity the model uses it for. The disagreement is recorded
> in `evidence/clozapine_smoking.yaml` rather than averaged away.

**Code:** [`enzyme_kinetics.py:3`](../backend/services/enzyme_kinetics.py:3) sets `CYP_KDEG['CYP1A2'] = 0.0077 h⁻¹`, giving t½ = ln2/0.0077 = **90 h**. [`pk_simulator.py:145`](../backend/services/pk_simulator.py:145) uses this same constant as the sole determinant of how fast enzyme activity returns to baseline after an inducer is removed.

**Literature:** Faber & Fuhr (2004) measured CYP1A2 activity by caffeine clearance in heavy smokers after cessation and reported an apparent de-induction half-life of **38.6 h (95% CI 27.4 to 54.4)**, with a new steady state reached in about one week. `VALUE_LOW_CONFIDENCE`

**Why it matters:** 90 h sits outside the published confidence interval. The model predicts a new steady state in 2 to 3 weeks; the literature reports about 1 week. The README states 2 to 3 weeks, so the documentation faithfully describes an incorrect time course.

**Root cause, and this is the important part:** the model conflates two different physical quantities. `k_deg` from Yang et al. (2008) is a *hepatic enzyme protein turnover* constant. The Faber & Fuhr value is an *observed in vivo de-induction* constant, which reflects both enzyme turnover and clearance of the inducing agent. Using the former where the latter is needed is a mechanistic category error, not a bad number.

**Fix:** introduce a separate, separately-sourced de-induction rate constant. Do not overload `k_deg`.

---

#### F-2. Smoking induction is a hard-coded magic tuple  `RESOLVED 2026-08-15`

> **Resolution.** Replaced by `smoking_induction_term()` in
> `services/sourced_params.py`, parameterised to an induction ratio of **1.5649
> (95% CI 1.4472-1.7301)**, derived as the reciprocal of the 36.1% (30.9-42.2)
> fall in caffeine clearance reported by Faber & Fuhr. The CI is carried on the
> `Parameter` so Monte Carlo samples it instead of a point estimate. The
> saturating-exposure representation (`SMOKING_EXPOSURE_UNITS`,
> `SMOKING_CYP1A2_EC50`) remains an explicit `MODELING_ASSUMPTION`, because
> cigarettes/day is not tracked. Only the saturated steady-state ratio is
> evidence-based.

**Code:** [`pk_simulator.py:157`](../backend/services/pk_simulator.py:157):
```python
if smoking and ename == 'CYP1A2':
    induction_terms.append((1.0, 1.0, 1.0))
```

This is `(C=1.0, Emax=1.0, EC50=1.0)`, which evaluates to `1 + 1x1/(1+1)` = exactly **1.5x** CYP1A2 synthesis. It is unsourced, has no dose or exposure dependence, and cannot represent the observation that 7 to 12 cigarettes/day is already near-maximal induction. `VALUE_LOW_CONFIDENCE`

This single line is the entire mechanistic basis of flagship Demo 2.

**Fix:** parameterise from Faber & Fuhr / Dobrinas et al. with a documented source, and represent it as a saturating exposure-response rather than a boolean.

---

#### F-3. Mechanism-based inhibition parameters are fabricated

**Code:** [`pk_simulator.py:308-310`](../backend/services/pk_simulator.py:308):
```python
if potency == 'strong':
    k_deg = CYP_KDEG.get(cyp.enzyme, 0.01)
    mbi_effects.append(MBIParams(enzyme_name=cyp.enzyme, k_inact=k_deg * 10, k_i_conc=ki_mg_l))
```

Two distinct problems:
1. `k_inact = 10 x k_deg` is invented. There is no pharmacological basis for tying inactivation rate to turnover rate by a factor of 10.
2. `k_i_conc` (the MBI half-inactivation concentration, `K_I`) is set equal to the **competitive** inhibition constant `Ki`. These are different physical quantities measured by different experiments and are not interchangeable.

MBI is the mechanism underpinning flagship Demo 1.

**Literature:** Sager et al. (2014) characterised fluoxetine and norfluoxetine as *complex* inhibitors with both reversible and time-dependent components against CYP2D6, CYP2C19 and CYP3A4, and performed in vitro to in vivo correlation. This is the correct primary source and it reports the parameter class needed here.

---

#### F-4. Norfluoxetine Ki: three-way contradiction

| Source | CYP2D6 Ki |
|---|---|
| [`pk_simulator.py:317`](../backend/services/pk_simulator.py:317) | 70.0 nM |
| README (pre-fix) | ~17 nM |
| Sager et al. 2014 | S-norfluoxetine **35 nM**; S-fluoxetine **68 nM** `VALUE_LOW_CONFIDENCE` |

The code's 70.0 nM is suspiciously close to the reported value for **S-fluoxetine** (68 nM), not norfluoxetine. This has the signature of a transcription error in which the parent drug's constant was entered for the metabolite. The README's 17 nM matches neither.

Additionally, the constant is defined *inside a loop body* as a function-local dict, making it invisible to any parameter audit:
```python
_METABOLITE_INHIBITORS = {'fluoxetine': ('CYP2D6', 70.0), 'venlafaxine': ('CYP2D6', 1400.0)}
```

Note also that Sager reports **enantiomer-specific** values, and fluoxetine is administered as a racemate. Whether to model enantiomers separately is a modelling decision that must be made explicitly, not by accident.

---

### HIGH

#### F-5. Metabolite formation is not molar-mass corrected

[`metabolite_tracker.py:32`](../backend/services/metabolite_tracker.py:32): `formation = met.formation_fraction * parent_elim`, where `parent_elim` is mg/h of **parent**. The resulting metabolite amount is in parent-equivalent mass, then divided by metabolite Vd to give a concentration reported as the metabolite's.

Correct form requires `x (MW_metabolite / MW_parent)`. For fluoxetine (309.3) to norfluoxetine (295.3, demethylation) that is a factor of ~0.955, so roughly a 4.5% systematic error. Small, but it is a genuine dimensional inconsistency and it is undocumented.

#### F-6. Metabolites have no enzyme-mediated elimination

[`metabolite_tracker.py:33`](../backend/services/metabolite_tracker.py:33): `elimination = met.ke_metabolite * a_met`, a fixed first-order rate.

Norfluoxetine is itself CYP2D6-metabolised **and** a potent CYP2D6 inhibitor, so it inhibits its own clearance. The model cannot represent this autoinhibition, which is part of why norfluoxetine's apparent half-life is so long. Demo 1's central claim, that inhibition persists for weeks after the parent is stopped, rests on a mechanism the engine does not implement.

#### F-7. Metabolite Vd silently defaults to the parent's Vd

[`pk_simulator.py:325`](../backend/services/pk_simulator.py:325) and [`metabolite_tracker.py:23`](../backend/services/metabolite_tracker.py:23). This directly scales the metabolite concentration that feeds back into the CYP2D6 inhibition term, so an undocumented assumption propagates straight into Demo 1's headline number.

#### F-8. Literature ranges collapsed to point estimates

Seed data stores norfluoxetine half-life as `240` hours (10 days), the midpoint of the literature's 4 to 16 days, with no record that a range existed. This is precisely the range-collapse the project's evidence doctrine prohibits, already present in the data.

#### F-9. Mass balance breaks when renal overrides meet CYP substrate data

[`pk_simulator.py:329`](../backend/services/pk_simulator.py:329) sets `_RENAL_OVERRIDES` independently of the database's `fraction_metabolized` values. In [`pk_simulator.py:105`](../backend/services/pk_simulator.py:105), `remaining_frac = max(0.0, 1.0 - renal - Σfm)` clamps at zero.

Where a renal override coexists with CYP substrate rows (paliperidone: renal 0.6, plus CYP substrate entries), total elimination becomes `Σfm·CL·C + renal·CL·C` which exceeds `CL·C`. For paliperidone at Σfm = 0.6 that is 1.2x over-elimination. **Checkable against the seed rows; flagged as a risk pending that check.**

In the normal path, where `renal_frac` is derived as `1 - Σfm`, the fractions are self-consistent and this does not occur.

#### F-10. Michaelis-Menten kinetics are effectively decorative

[`pk_simulator.py:301`](../backend/services/pk_simulator.py:301): `vmax_calibrated = cl * km_mg_l`.

This forces the MM expression to reduce to first-order `CL·C` at therapeutic concentrations, which is a defensible modelling choice. But two consequences are undocumented:
1. The database's measured `vmax_nmol_per_h` is read only as a presence check at [line 299](../backend/services/pk_simulator.py:299) and then discarded.
2. The saturation point is therefore an artifact of whatever `Km` was entered, not an evidence-based prediction.

The README's claim of "saturable Michaelis-Menten kinetics" overstates what the code does. Either implement genuine saturable kinetics where the literature supports them, or document this as a deliberate linear approximation.

#### F-11. Pharmacogenomic multipliers are invented, and contradict the README

[`pk_simulator.py:9`](../backend/services/pk_simulator.py:9) uses flat multipliers: poor 0.3, intermediate 0.6, normal 1.0, ultra-rapid 2.0. These are round numbers with no source.

README section 12 describes a CPIC Activity Score formula, `CL_adj = CL_pop · [Σ fm,j · AS_j + (1 - Σ fm,j)]`, **which the code does not implement.** Caudle et al. (2020) is the correct standard for genotype to phenotype translation and defines the activity score system properly.

#### F-12. No UGT mechanism exists, and a competitive model would be wrong anyway

`UGT1A4` appears in `TRACKED_ENZYMES` and `CYP_KDEG`, but is processed by the same `CYP450Profile` table and the same competitive-inhibition path as the CYPs.

The valproate-lamotrigine interaction is glucuronidation-mediated. Two problems beyond the missing pathway:

1. **The literature disagrees on magnitude.** Reported effects range from ~21% clearance reduction to ~50% maximum inhibition, with half-life increases variously reported as 24→72 h and 30→60 h. `VALUE_LOW_CONFIDENCE` This is a textbook case for the doctrine's "model probabilistically when studies disagree" guidance, not for picking the cleanest number.
2. **The dose-response saturates.** Maximum inhibition is reportedly reached at valproate doses as low as 250 to 500 mg/day. `VALUE_LOW_CONFIDENCE` A competitive term of the form `1 + I/Ki` increases monotonically with inhibitor concentration and **structurally cannot** reproduce a plateau. Forcing this interaction through the existing engine would produce the wrong shape regardless of how Ki is tuned.

This scenario is not a validation task. It is a mechanism implementation task.

---

### CRITICAL: found by the validation suite, not by code review

#### F-22. Clozapine Km is ~125x below any published value

**Code:** the clozapine fixture uses `Km = 0.16 mg/L` for all three CYP
pathways. Converted at MW 326.8 that is **0.49 uM**.

**Literature:** Eiermann et al. (1997) report Km for clozapine demethylation in
human liver microsomes as **61 +/- 21 uM** (19.93 mg/L). Other studies span 13
to 120 uM. The lowest published value is 26x higher than the code's; the central
value is 125x higher.

**Why it matters, and why F-10 was under-graded.** The audit originally called
Michaelis-Menten "effectively decorative" because `Vmax` is back-calculated as
`CL x Km`, which makes the expression reduce to first-order clearance. That is
only true when C is far below Km. At the seed Km, therapeutic clozapine sat at
**C/Km = 3.7 to 7.8**, deep in the saturated regime, where reducing enzyme
activity raises concentration superlinearly.

Measured effect on the flagship prediction:

| Km | C/Km | Predicted rise on cessation | vs published 1.34-1.76 |
|---|---|---|---|
| 0.16 mg/L (seed) | 3.7-7.8 | **2.079x** | FAIL |
| 19.93 mg/L (Eiermann) | ~0.03 | **1.381x** | PASS |

An arbitrary Km is therefore not harmless. It inflated the predicted
drug-interaction effect by 50% while leaving clearance untouched, which is
exactly the failure mode that would have been "fixed" by detuning the
well-measured induction parameter had the audit not come first.

**Scope:** corrected in the validation driver via
`CLOZAPINE_CYP1A2_KM_MG_L`. **The seed database still carries the wrong value**
and every other drug's Km remains unaudited. Guarded by
`test_clozapine_stays_in_linear_kinetic_regime`.

#### F-23. Clozapine fm_CYP1A2 conflicts with in vitro data

The model uses **fm_CYP1A2 = 0.70**, unsourced, carried from seed data. Olesen &
Linnet (2001) measured CYP1A2 contributing **30%** of clozapine N-demethylation
at a therapeutically relevant 5 uM (CYP2C19 24%, CYP3A4 22%, CYP2C9 12%, CYP2D6
6%).

Substituting 0.30 predicts only a **1.17x** rise on cessation, well below the
observed 1.34-1.76. Keeping 0.70 predicts 1.381x and matches. The in vitro
fraction and the clinical effect size disagree, and the authors themselves note
CYP1A2 appears more important clinically than in vitro.

**This is deliberately left unresolved.** Picking whichever value makes the
model agree would be fitting to the validation target. It is registered as a
`MODELING_ASSUMPTION` with the conflict documented, and it is the single largest
source of uncertainty in Demo 2. Guarded by
`test_fm_cyp1a2_is_still_flagged_as_unsourced`.

---

### MEDIUM: clinical risk layer

#### F-13. The serotonin score is not the Hunter criteria

[`risk_calculator.py:16-50`](../backend/services/risk_calculator.py:16) implements a bespoke mechanism-counting heuristic with invented thresholds (`>=2 reuptake inhibitors → High`, `total_potency >= 3 → Moderate`).

The Hunter Serotonin Toxicity Criteria (Dunkley et al. 2003) is a **diagnostic decision rule applied to observed clinical signs** in a patient who has already taken a serotonergic agent: clonus, agitation, diaphoresis, tremor, hyperreflexia, hypertonia, temperature >38°C. It is not a predictive risk score computed from a medication list.

Citing Hunter for this function is a category error that misrepresents the source. The heuristic may still be useful, but it must be labelled as an unvalidated internal heuristic, not attributed to Hunter.

#### F-14. The ACB score is not the ACB scale

[`risk_calculator.py:80`](../backend/services/risk_calculator.py:80) sums a database column and returns a raw integer with **no threshold interpretation at all**. The published ACB scale (Boustani et al. 2008) assigns defined 1/2/3 scores per drug, and the clinically meaningful signal is a total at or above 3. Whether the stored values match published ACB scores is unverified.

#### F-15. QTc tiers are unsourced

[`risk_calculator.py:51`](../backend/services/risk_calculator.py:51) hard-codes a high/moderate/low mapping. The authoritative reference is the CredibleMeds/AZCERT QTdrugs classification (Known / Possible / Conditional risk of TdP), whose taxonomy this does not match. Individual assignments are also debatable: escitalopram is tiered identically to citalopram despite differing regulatory treatment.

#### F-16. CNS depression thresholds are invented

[`risk_calculator.py:83-89`](../backend/services/risk_calculator.py:83): `>= 6 High`, `>= 3 Moderate`. No source.

#### F-17. FDA pregnancy letter categories are deprecated

[`risk_calculator.py:112-113`](../backend/services/risk_calculator.py:112) uses `fda_pregnancy_category` and flags categories D and X.

The FDA Pregnancy and Lactation Labeling Rule removed pregnancy letter categories A, B, C, D and X. The rule published 3 December 2014 and took effect **30 June 2015**; manufacturers of products approved before 30 June 2001 were required to remove the category within 3 years. The project is citing a regulatory framework that has been retired for over a decade.

---

### LOW: robustness and numerics

#### F-18. Silent fallbacks manufacture plausible-looking drugs

[`pk_simulator.py:291, 326-328`](../backend/services/pk_simulator.py:291): `clearance or 5.0`, `vd or 100.0`, `ka or 0.5`, `bioavailability or 0.5`, `formation_fraction or 0.5`, molecular weight default `350.0`.

A medication with no PK data receives a complete set of invented parameters and produces a confident-looking concentration curve indistinguishable from a well-characterised drug. This is the highest-risk category of failure for a tool claiming scientific auditability.

#### F-19. Enzyme level clipped silently

[`pk_simulator.py:95`](../backend/services/pk_simulator.py:95): `max(y[...], 0.01)`. Clipping happens with no warning and no record in the result object.

#### F-20. No stiffness handling

[`pk_simulator.py:248`](../backend/services/pk_simulator.py:248) uses RK45 with `max_step=1.0`. System timescales span roughly two orders of magnitude (absorption ka ~0.5 to 1.5 h⁻¹ against enzyme turnover ~50 to 90 h). Not a correctness bug, but BDF or Radau should be available and stiffness should be detected rather than assumed absent.

#### F-21. Minor citation error

README cites Yang et al. 2008 as pages 384-394. Crossref returns **384-393**.

---

## Verified as correct

Stated explicitly, because a fair audit records what holds up:

1. **Bioavailability is applied exactly once**, at the gut dose ([`pk_simulator.py:243`](../backend/services/pk_simulator.py:243)), with no second application on gut-to-plasma transfer.
2. **`enzyme_pool_derivative` is structurally correct** and matches the Fahmi/Yang formulation, with `k_synth = k_deg` correctly giving baseline E = 1.0 at steady state.
3. **Elimination fractions are self-consistent** in the normal path where renal fraction is derived from `1 - Σfm`.
4. **Two-compartment exchange flux** ([`pk_simulator.py:139`](../backend/services/pk_simulator.py:139)) uses the standard amount-based form.

---

## Validation readiness

| Demo scenario | Status | Blocked by | Source available? |
|---|---|---|---|
| 1. Fluoxetine / norfluoxetine CYP2D6 persistence | **Blocked** | F-3, F-4, F-6, F-7 | Yes: Sager 2014 |
| 2. Clozapine / smoking cessation | **VALIDATED** (5/5 endpoints) | resolved F-1, F-2, F-22 | Faber & Fuhr 2004; Meyer 2001; Flanagan 2024 |
| 3. Polypharmacy timeline | **Blocked** | F-11, F-18, plus all of the above | Partial |
| Lamotrigine + valproate | **Not implementable** | F-12 (no UGT mechanism, wrong dose-response shape) | Yes, but mechanism must be built first |
| Risperidone CYP2D6 PM | **Blocked** | F-11, F-5, F-7 | Yes: Caudle 2020, Hicks 2015 |

### Demo 2 result

External validation: parameterised from Faber & Fuhr (caffeine probe, healthy
heavy smokers), validated against Meyer 2001 and Flanagan 2024 (clozapine
concentrations in psychiatric patients). Different drug, population and
measurement method, so this is not fitting and testing on the same data.

| Endpoint | Observed | Predicted | Status |
|---|---:|---:|---|
| Direction: exposure rises | increase | 1.381x | PASS |
| Direction: CYP1A2 activity falls | decrease | 0.639x | PASS |
| Concentration ratio after cessation | 1.574 (range 1.34-1.76) | **1.381** | PASS |
| Percent increase after cessation | 57.4% (range 34-76%) | **38.1%** | PASS |
| CYP1A2 de-induction half-life | 38.6 h (CI 27.4-54.4) | 38.6 h | PASS (internal) |

Percent error against the Meyer point estimate is **-12.3%**: the model
under-predicts, sitting in the lower half of the published range. The last row is
*internal* validation, since the engine is parameterised from that same
measurement; it confirms correct implementation, not predictive accuracy.

The pass was earned by sourcing F-22's Km, not by tuning. The suite failed first
at 2.079x, and the failure was traced to the Km rather than absorbed into the
induction parameter.

**One of three demos now validates.** The primary sources needed to unblock
Demo 1 are identified and citation-verified below.

---

## Assumptions register

Every unsourced numeric constant found in the scientific path. This is the starting inventory for the provenance schema.

| Constant | Value | Location | Status |
|---|---|---|---|
| Smoking CYP1A2 induction tuple | `(1.0, 1.0, 1.0)` → 1.5x | `pk_simulator.py:157` | ASSUMPTION |
| MBI `k_inact` | `10 x k_deg` | `pk_simulator.py:310` | ASSUMPTION |
| MBI `K_I` | reuses competitive `Ki` | `pk_simulator.py:310` | ASSUMPTION (wrong quantity) |
| Induction `Emax` map | strong 2.0 / mod 1.0 / weak 0.5 | `pk_simulator.py:313` | ASSUMPTION |
| Induction `EC50` | reuses `Ki`, else 0.5 | `pk_simulator.py:314` | ASSUMPTION (wrong quantity) |
| Norfluoxetine `Ki` | 70.0 nM | `pk_simulator.py:317` | LIKELY TRANSCRIPTION ERROR |
| Desvenlafaxine `Ki` | 1400.0 nM | `pk_simulator.py:317` | UNSOURCED |
| CYP2D6 phenotype multipliers | 0.3 / 0.6 / 1.0 / 2.0 | `pk_simulator.py:9` | ASSUMPTION |
| Default clearance | 5.0 L/h | `pk_simulator.py:291` | SILENT FALLBACK |
| Default Vd | 100.0 L | `pk_simulator.py:327` | SILENT FALLBACK |
| Default ka | 0.5 h⁻¹ | `pk_simulator.py:326` | SILENT FALLBACK |
| Default bioavailability | 0.5 | `pk_simulator.py:328` | SILENT FALLBACK |
| Default molecular weight | 350.0 | `pk_simulator.py:292` | SILENT FALLBACK |
| Default formation fraction | 0.5 | `pk_simulator.py:325` | SILENT FALLBACK |
| Renal fraction overrides | 8 hard-coded drugs | `pk_simulator.py:329` | UNSOURCED |
| Serotonin thresholds | `>=2`, `>=3` | `risk_calculator.py:41,46` | ASSUMPTION |
| CNS depression thresholds | `>=6`, `>=3` | `risk_calculator.py:85,87` | ASSUMPTION |
| QTc tier assignments | 18 drugs | `risk_calculator.py:51` | UNSOURCED |
| Enzyme floor | 0.01 | `pk_simulator.py:95` | NUMERICAL GUARD |

---

## References

All DOIs below resolved successfully against the Crossref API on 2026-08-15. Metadata shown is as returned by Crossref, not as remembered.

1. **Sager JE, Lutz JD, Foti RS, Davis C, Kunze KL, Isoherranen N.** Fluoxetine- and Norfluoxetine-Mediated Complex Drug-Drug Interactions: In Vitro to In Vivo Correlation of Effects on CYP2D6, CYP2C19, and CYP3A4. *Clin Pharmacol Ther.* 2014;95:653-662. DOI: [10.1038/clpt.2014.50](https://doi.org/10.1038/clpt.2014.50) `CITATION_VERIFIED`

2. **Faber MS, Fuhr U.** Time response of cytochrome P450 1A2 activity on cessation of heavy smoking. *Clin Pharmacol Ther.* 2004;76:178-184. DOI: [10.1016/j.clpt.2004.04.003](https://doi.org/10.1016/j.clpt.2004.04.003) `CITATION_VERIFIED`

3. **Dobrinas M, et al.** Impact of Smoking, Smoking Cessation, and Genetic Polymorphisms on CYP1A2 Activity and Inducibility. *Clin Pharmacol Ther.* 2011;90:117-125. DOI: [10.1038/clpt.2011.70](https://doi.org/10.1038/clpt.2011.70) `CITATION_VERIFIED`

4. **Yang J, Liao M, Shou M, et al.** Cytochrome P450 Turnover: Regulation of Synthesis and Degradation. *Curr Drug Metab.* 2008;9:384-393. DOI: [10.2174/138920008784746382](https://doi.org/10.2174/138920008784746382) `CITATION_VERIFIED`

5. **Fahmi OA, et al.** A Combined Model for Predicting CYP3A4 Clinical Net Drug-Drug Interaction. *Drug Metab Dispos.* 2008;36:1698-1708. DOI: [10.1124/dmd.107.018663](https://doi.org/10.1124/dmd.107.018663) `CITATION_VERIFIED`

6. **Dunkley EJC, Isbister GK, Sibbritt D, Dawson AH, Whyte IM.** The Hunter Serotonin Toxicity Criteria: simple and accurate diagnostic decision rules for serotonin toxicity. *QJM.* 2003;96:635-642. DOI: [10.1093/qjmed/hcg109](https://doi.org/10.1093/qjmed/hcg109) `CITATION_VERIFIED`

7. **Boustani M, Campbell NL, Munger S, et al.** Impact of Anticholinergics on the Aging Brain: A Review and Practical Application. *Aging Health.* 2008;4:311-320. DOI: [10.2217/1745509X.4.3.311](https://doi.org/10.2217/1745509X.4.3.311) `CITATION_VERIFIED`

8. **Caudle KE, Sangkuhl K, Whirl-Carrillo M, et al.** Standardizing CYP2D6 Genotype to Phenotype Translation. *Clin Transl Sci.* 2020;13:116-124. DOI: [10.1111/cts.12692](https://doi.org/10.1111/cts.12692) `CITATION_VERIFIED`

9. **Hicks JK, Bishop JR, Sangkuhl K, et al.** CPIC Guideline for CYP2D6 and CYP2C19 Genotypes and Dosing of SSRIs. *Clin Pharmacol Ther.* 2015;98:127-134. DOI: [10.1002/cpt.147](https://doi.org/10.1002/cpt.147) `CITATION_VERIFIED`

**Regulatory:** FDA Pregnancy and Lactation Labeling Rule, published 3 December 2014, effective 30 June 2015. Removes pregnancy categories A, B, C, D, X.

---

## Recommended sequence

1. **Unblock Demo 2 first.** It needs only F-1 and F-2, and Faber & Fuhr provides both the de-induction constant and its confidence interval, which doubles as a literature-supported acceptance range. This is the shortest path to one genuine external validation.
2. **Then Demo 1**, using Sager 2014 for the reversible and time-dependent CYP2D6 parameters, which resolves F-3 and F-4 together.
3. **Build the provenance schema alongside step 1**, not after. The assumptions register above is its initial content.
4. **Fix F-18 before anything user-facing.** Silent fallbacks are the finding most likely to embarrass the project under review, because they make unsourced drugs indistinguishable from sourced ones.
5. **Defer lamotrigine/valproate** until a saturable non-CYP inhibition mechanism exists. It is not a validation scenario yet.

**Before any of the `VALUE_LOW_CONFIDENCE` numbers above enter the codebase, they need checking against the primary text.** The citations are verified; the numbers inside them are not.
