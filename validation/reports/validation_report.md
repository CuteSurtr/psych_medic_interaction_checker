# NeuroTrace Validation Report

## Aggregate

- Scenarios: 1
- Endpoints: 5  (judged 5, not run 0)
- PASS: 5   FAIL: 0
- Median absolute percent error: 12.3%
- Mean absolute percent error: 15.3%
- Max absolute percent error: 33.7%
- Fraction within acceptance: 1.00

Failed and not-run endpoints are listed below alongside passes. Nothing is filtered from this report.

## Endpoints

| Scenario | Endpoint | Observed | Predicted | % error | Status |
|---|---|---:|---:|---:|---|
| clozapine_smoking_cessation | direction_clozapine_exposure_rises | - | 1.381 | - | **PASS** |
| clozapine_smoking_cessation | direction_cyp1a2_activity_falls | - | 0.639 | - | **PASS** |
| clozapine_smoking_cessation | clozapine_concentration_ratio_after_cessation | 1.574 | 1.381 | -12.3% | **PASS** |
| clozapine_smoking_cessation | clozapine_percent_increase_after_cessation | 57.4 | 38.07 | -33.7% | **PASS** |
| clozapine_smoking_cessation | cyp1a2_deinduction_half_life_h | 38.6 | 38.6 | +0.0% | **PASS** |

## Clozapine exposure after abrupt smoking cessation

*A patient stable on clozapine stops smoking abruptly, as happens on admission to a non-smoking unit. CYP1A2 induction is lost, clearance falls and plasma clozapine rises. Tests whether the enzyme-pool model reproduces both the magnitude and the time course reported in the literature.*

- Validation type: **external**
- Population: Model configured as a 70 kg adult on clozapine 200 mg twice daily at steady state. Parameters derived from healthy heavy smokers (caffeine probe); validation targets from psychiatric inpatients on clozapine.

- Parameterised from: FABER_FUHR_2004
- Validated against: MEYER_2001, FLANAGAN_2024
- Evidence map: `evidence/clozapine_smoking.yaml`

### direction_clozapine_exposure_rises  [PASS]

- Acceptance: direction increase relative to 1.0
- Observed: not applicable
- Predicted: 1.3807 ratio
- Verdict: predicted 1.381 vs reference 1: correct direction
- Source: MEYER_2001

### direction_cyp1a2_activity_falls  [PASS]

- Acceptance: direction decrease relative to 1.0
- Observed: not applicable
- Predicted: 0.639 ratio
- Verdict: predicted 0.639 vs reference 1: correct direction
- Source: FABER_FUHR_2004

### clozapine_concentration_ratio_after_cessation  [PASS]

- Acceptance: within published range 1.34 to 1.76 ratio
- Observed: 1.574 ratio
- Predicted: 1.3807 ratio
- Verdict: 1.381 lies within the published range 1.34-1.76
- Metrics: absolute_error=0.1933, percent_error=-12.28, mean_absolute_percentage_error=12.28, bias=-0.1933, coverage_of_observed_range=0.3621
- Source: MEYER_2001 observed point, FLANAGAN_2024 acceptance range

### clozapine_percent_increase_after_cessation  [PASS]

- Acceptance: within published range 34.0 to 76.0 percent
- Observed: 57.4 percent
- Predicted: 38.07 percent
- Verdict: 38.07 lies within the published range 34.0-76.0
- Metrics: absolute_error=19.33, percent_error=-33.68, mean_absolute_percentage_error=33.68, bias=-19.33, coverage_of_observed_range=0.3621
- Source: MEYER_2001, FLANAGAN_2024

### cyp1a2_deinduction_half_life_h  [PASS]

- Acceptance: within published range 27.4 to 54.4 hour
- Observed: 38.6 hour
- Predicted: 38.6 hour
- Verdict: 38.6 lies within the published range 27.4-54.4
- Metrics: absolute_error=0, percent_error=0, mean_absolute_percentage_error=0, bias=0, coverage_of_observed_range=nan
- Source: FABER_FUHR_2004

**Limitations**

- fm_CYP1A2 for clozapine is 0.70 and is NOT sourced. It is carried from the seed data and dominates the predicted magnitude, so the primary endpoint is only as good as that unsourced number.

- Faber & Fuhr studied healthy volunteers using caffeine as the probe, not patients taking clozapine. Transferring the CYP1A2 activity ratio to clozapine assumes probe-independence of enzyme induction.

- Flanagan 2024 shows the effect size varies with dose (34% to 76%), implying nonlinear clozapine kinetics that the current linear-clearance model cannot reproduce. The model predicts a single dose-independent ratio.

- The Faber & Fuhr cohort was all white. CYP1A2 inducibility varies with CYP1A2*1F genotype and ancestry, which the model does not represent.

- Plasma concentration lags enzyme activity by clozapine's own half-life, so the clinical time to a new steady state exceeds the 38.6 h enzyme constant.

