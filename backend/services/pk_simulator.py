from __future__ import annotations
import numpy as np
from scipy.integrate import solve_ivp
from dataclasses import dataclass, field
from typing import Any
from services.enzyme_kinetics import CYP_KDEG, EnzymeParams, InhibitorParams, MBIParams, InductionParams, competitive_inhibition_rate, enzyme_activity_factor, enzyme_pool_derivative
from services.dose_scheduler import DoseEvent, MedicationSchedule, build_dose_timeline
from services.metabolite_tracker import MetaboliteParams, build_metabolite_ode_terms
from services.sourced_params import documented_tdi, smoking_induction_term
CYP_ACTIVITY_MULTIPLIERS: dict[str, dict[str, float]] = {'CYP2D6': {'poor': 0.3, 'intermediate': 0.6, 'normal': 1.0, 'ultra-rapid': 2.0}, 'CYP2C19': {'poor': 0.3, 'intermediate': 0.6, 'normal': 1.0, 'ultra-rapid': 2.0}, 'CYP3A4': {'normal': 1.0}, 'CYP1A2': {'normal': 1.0}}

@dataclass
class DrugConfig:
    index: int
    generic_name: str
    ka: float
    bioavailability: float
    vd_l: float
    clearance_l_per_h: float
    renal_clearance_fraction: float
    enzyme_substrates: list[EnzymeParams]
    enzyme_inhibitions: list[InhibitorParams]
    metabolite: MetaboliteParams | None
    mbi_effects: list[MBIParams] = field(default_factory=list)
    induction_effects: list[InductionParams] = field(default_factory=list)
    peripheral_vd_l: float | None = None
    k12_per_h: float | None = None
    k21_per_h: float | None = None

    @property
    def is_two_compartment(self) -> bool:
        return self.peripheral_vd_l is not None and self.k12_per_h is not None and (self.k21_per_h is not None)
REFERENCE_WEIGHT_KG = 70.0

@dataclass
class SimulationConfig:
    drugs: list[DrugConfig]
    schedules: list[MedicationSchedule]
    horizon_days: int = 56
    cyp2d6_phenotype: str = 'normal'
    cyp2c19_phenotype: str = 'normal'
    smoking: bool = False
    patient_weight_kg: float = 70.0

@dataclass
class SimulationResult:
    time_hours: np.ndarray
    concentrations: dict[str, np.ndarray]
    metabolite_concentrations: dict[str, np.ndarray]
    dose_events: list[dict]
    enzyme_activity: dict[str, np.ndarray]
    steady_state_info: list[dict]
    peripheral_concentrations: dict[str, np.ndarray] = field(default_factory=dict)

def _build_cyp_multipliers(config: SimulationConfig) -> dict[str, float]:
    multipliers: dict[str, float] = {}
    for enzyme, pheno_map in CYP_ACTIVITY_MULTIPLIERS.items():
        if enzyme == 'CYP2D6':
            multipliers[enzyme] = pheno_map.get(config.cyp2d6_phenotype, 1.0)
        elif enzyme == 'CYP2C19':
            multipliers[enzyme] = pheno_map.get(config.cyp2c19_phenotype, 1.0)
        else:
            multipliers[enzyme] = pheno_map.get('normal', 1.0)
    return multipliers

def _collect_tracked_enzymes(drugs: list[DrugConfig]) -> list[str]:
    seen: set[str] = set()
    for drug in drugs:
        for enz in drug.enzyme_substrates:
            seen.add(enz.enzyme_name)
        for inhib in drug.enzyme_inhibitions:
            seen.add(inhib.enzyme_name)
        for mbi in drug.mbi_effects:
            seen.add(mbi.enzyme_name)
        for ind in drug.induction_effects:
            seen.add(ind.enzyme_name)
    return sorted(seen)

def _ode_rhs(t: float, y: np.ndarray, drugs: list[DrugConfig], metabolites: list[MetaboliteParams], cyp_multipliers: dict[str, float], smoking: bool, enzyme_names: list[str], peripheral_index: dict[int, int] | None=None) -> np.ndarray:
    n_drugs = len(drugs)
    n_met = len(metabolites)
    n_enz = len(enzyme_names)
    dydt = np.zeros_like(y)
    enz_offset = 2 * n_drugs + n_met
    peripheral_offset = enz_offset + n_enz
    peripheral_index = peripheral_index or {}
    enz_index = {name: idx for idx, name in enumerate(enzyme_names)}
    plasma_concs = np.empty(n_drugs)
    for i, drug in enumerate(drugs):
        plasma_concs[i] = max(y[2 * i + 1], 0.0) / drug.vd_l
    met_concs = np.empty(n_met)
    for m_idx, met in enumerate(metabolites):
        met_concs[m_idx] = max(y[2 * n_drugs + m_idx], 0.0) / met.vd_metabolite_l
    enzyme_levels: dict[str, float] = {}
    for e_idx, ename in enumerate(enzyme_names):
        enzyme_levels[ename] = max(y[enz_offset + e_idx], 0.01)
    parent_elimination_rates = np.zeros(n_drugs)
    for i, drug in enumerate(drugs):
        a_gut = max(y[2 * i], 0.0)
        c_i = plasma_concs[i]
        dydt[2 * i] = -drug.ka * a_gut
        renal_rate = drug.renal_clearance_fraction * drug.clearance_l_per_h * c_i
        hepatic_rate = 0.0
        if drug.enzyme_substrates:
            total_enzyme_frac = sum((enz.fraction_metabolized for enz in drug.enzyme_substrates))
            remaining_frac = max(0.0, 1.0 - drug.renal_clearance_fraction - total_enzyme_frac)
            hepatic_rate = remaining_frac * drug.clearance_l_per_h * c_i
            for enz in drug.enzyme_substrates:
                vmax = enz.vmax
                e_level = enzyme_levels.get(enz.enzyme_name, 1.0)
                vmax *= e_level
                if enz.enzyme_name in cyp_multipliers:
                    vmax *= cyp_multipliers[enz.enzyme_name]
                inhib_concs: list[float] = []
                ki_vals: list[float] = []
                for j, other_drug in enumerate(drugs):
                    if j == i:
                        continue
                    for inhib in other_drug.enzyme_inhibitions:
                        if inhib.enzyme_name == enz.enzyme_name:
                            inhib_concs.append(float(plasma_concs[j]))
                            ki_vals.append(inhib.ki)
                for m_idx2, met in enumerate(metabolites):
                    if met.is_enzyme_inhibitor and met.inhibited_enzyme == enz.enzyme_name and met.ki_nm:
                        inhib_concs.append(float(met_concs[m_idx2]))
                        ki_vals.append(met.ki_nm)
                rate = competitive_inhibition_rate(c_i, vmax, enz.km, inhib_concs, ki_vals)
                hepatic_rate += enz.fraction_metabolized * rate
        else:
            hepatic_rate = (1.0 - drug.renal_clearance_fraction) * drug.clearance_l_per_h * c_i
        total_elim = hepatic_rate + renal_rate
        parent_elimination_rates[i] = total_elim
        dydt[2 * i + 1] = drug.ka * a_gut - total_elim
        if drug.is_two_compartment and i in peripheral_index:
            periph_idx = peripheral_offset + peripheral_index[i]
            a_periph = max(y[periph_idx], 0.0)
            a_plasma = max(y[2 * i + 1], 0.0)
            k12 = drug.k12_per_h
            k21 = drug.k21_per_h
            flux_to_periph = k12 * a_plasma - k21 * a_periph
            dydt[2 * i + 1] -= flux_to_periph
            dydt[periph_idx] = flux_to_periph
    met_derivs = build_metabolite_ode_terms(metabolites, parent_elimination_rates.tolist(), y, n_drugs)
    dydt[2 * n_drugs:2 * n_drugs + n_met] = met_derivs
    for e_idx, ename in enumerate(enzyme_names):
        k_deg = CYP_KDEG.get(ename, 0.01)
        e_level = enzyme_levels[ename]
        induction_terms: list[tuple[float, float, float]] = []
        mbi_terms: list[tuple[float, float, float]] = []
        for drug in drugs:
            c_drug = plasma_concs[drug.index]
            for ind in drug.induction_effects:
                if ind.enzyme_name == ename:
                    induction_terms.append((c_drug, ind.e_max, ind.ec50))
            for mbi in drug.mbi_effects:
                if mbi.enzyme_name == ename:
                    mbi_terms.append((c_drug, mbi.k_inact, mbi.k_i_conc))
        if smoking and ename == 'CYP1A2':
            # Sourced from Faber & Fuhr 2004 via sourced_params; previously a
            # hard-coded (1.0, 1.0, 1.0) giving exactly 1.5x with no citation.
            induction_terms.append(smoking_induction_term())
        dydt[enz_offset + e_idx] = enzyme_pool_derivative(e_level, k_deg, induction_terms, mbi_terms)
    return dydt

def _extract_enzyme_activity(y_full: np.ndarray, n_drugs: int, n_met: int, enzyme_names: list[str]) -> dict[str, np.ndarray]:
    enz_offset = 2 * n_drugs + n_met
    activity: dict[str, np.ndarray] = {}
    for e_idx, ename in enumerate(enzyme_names):
        activity[ename] = np.maximum(y_full[enz_offset + e_idx, :], 0.0)
    return activity

def _compute_steady_state_info(time_hours: np.ndarray, concentrations: dict[str, np.ndarray], config: SimulationConfig) -> list[dict]:
    freq_map = {'daily': 24.0, 'BID': 12.0, 'TID': 8.0, 'QHS': 24.0}
    info: list[dict] = []
    for drug, schedule in zip(config.drugs, config.schedules):
        conc = concentrations.get(drug.generic_name)
        if conc is None or len(conc) == 0:
            info.append({'drug_name': drug.generic_name, 'trough_ng_ml': 0.0, 'peak_ng_ml': 0.0, 'time_to_steady_state_days': None})
            continue
        active_events = [e for e in schedule.events if e['event_type'] != 'stop']
        freq_h = 24.0
        if active_events:
            last_evt = active_events[-1]
            freq_h = freq_map.get(last_evt.get('frequency', 'daily'), 24.0)
        horizon_h = float(config.horizon_days) * 24.0
        last_mask = time_hours >= horizon_h - freq_h
        if np.any(last_mask):
            last_conc = conc[last_mask]
            trough = float(np.min(last_conc))
            peak = float(np.max(last_conc))
        else:
            trough = float(conc[-1])
            peak = float(np.max(conc))
        time_to_ss: float | None = None
        if trough > 0.0:
            threshold = 0.9 * trough
            interval_starts = np.arange(0, horizon_h - freq_h, freq_h)
            for iv_start in interval_starts:
                mask = (time_hours >= iv_start) & (time_hours < iv_start + freq_h)
                if np.any(mask):
                    iv_trough = float(np.min(conc[mask]))
                    if iv_trough >= threshold:
                        time_to_ss = float(iv_start)
                        break
        info.append({'drug_name': drug.generic_name, 'trough_ng_ml': trough, 'peak_ng_ml': peak, 'time_to_steady_state_days': round(time_to_ss / 24.0, 1) if time_to_ss is not None else None})
    return info

def run_simulation(config: SimulationConfig) -> SimulationResult:
    weight_factor = config.patient_weight_kg / REFERENCE_WEIGHT_KG
    if weight_factor != 1.0:
        scaled_drugs: list[DrugConfig] = []
        for drug in config.drugs:
            scaled_drugs.append(DrugConfig(index=drug.index, generic_name=drug.generic_name, ka=drug.ka, bioavailability=drug.bioavailability, vd_l=drug.vd_l * weight_factor, clearance_l_per_h=drug.clearance_l_per_h * weight_factor, renal_clearance_fraction=drug.renal_clearance_fraction, enzyme_substrates=drug.enzyme_substrates, enzyme_inhibitions=drug.enzyme_inhibitions, metabolite=drug.metabolite, mbi_effects=drug.mbi_effects, induction_effects=drug.induction_effects, peripheral_vd_l=drug.peripheral_vd_l * weight_factor if drug.peripheral_vd_l is not None else None, k12_per_h=drug.k12_per_h, k21_per_h=drug.k21_per_h))
        config = SimulationConfig(drugs=scaled_drugs, schedules=config.schedules, horizon_days=config.horizon_days, cyp2d6_phenotype=config.cyp2d6_phenotype, cyp2c19_phenotype=config.cyp2c19_phenotype, smoking=config.smoking, patient_weight_kg=config.patient_weight_kg)
    n_drugs = len(config.drugs)
    metabolites = [d.metabolite for d in config.drugs if d.metabolite is not None]
    n_met = len(metabolites)
    enzyme_names = _collect_tracked_enzymes(config.drugs)
    n_enz = len(enzyme_names)
    peripheral_index: dict[int, int] = {}
    for drug in config.drugs:
        if drug.is_two_compartment:
            peripheral_index[drug.index] = len(peripheral_index)
    n_peripheral = len(peripheral_index)
    state_size = 2 * n_drugs + n_met + n_enz + n_peripheral
    horizon_h = float(config.horizon_days) * 24.0
    cyp_multipliers = _build_cyp_multipliers(config)
    dose_events = build_dose_timeline(config.schedules, config.horizon_days)
    dose_map: dict[float, list[DoseEvent]] = {}
    for de in dose_events:
        dose_map.setdefault(de.time_h, []).append(de)
    segment_boundaries = sorted({0.0, horizon_h} | set(dose_map.keys()))
    y0 = np.zeros(state_size)
    enz_offset = 2 * n_drugs + n_met
    for e_idx in range(n_enz):
        y0[enz_offset + e_idx] = 1.0
    current_y = y0.copy()
    all_t: list[np.ndarray] = []
    all_y: list[np.ndarray] = []
    for seg_idx in range(len(segment_boundaries) - 1):
        t_start = segment_boundaries[seg_idx]
        t_end = segment_boundaries[seg_idx + 1]
        if t_start in dose_map:
            for de in dose_map[t_start]:
                drug = config.drugs[de.medication_index]
                current_y[2 * de.medication_index] += drug.bioavailability * de.dose_mg
        if t_end <= t_start:
            continue
        n_eval = max(3, int((t_end - t_start) / 0.5) + 1)
        t_eval = np.linspace(t_start, t_end, n_eval)
        sol = solve_ivp(_ode_rhs, [t_start, t_end], current_y, method='RK45', t_eval=t_eval, args=(config.drugs, metabolites, cyp_multipliers, config.smoking, enzyme_names, peripheral_index), rtol=1e-06, atol=1e-09, max_step=1.0)
        if not sol.success:
            raise RuntimeError(f'ODE solver failed at segment [{t_start}, {t_end}]: {sol.message}')
        start_slice = 0 if seg_idx == 0 else 1
        all_t.append(sol.t[start_slice:])
        all_y.append(sol.y[:, start_slice:])
        current_y = sol.y[:, -1].copy()
    time_hours = np.concatenate(all_t) if all_t else np.array([0.0])
    y_full = np.concatenate(all_y, axis=1) if all_y else np.zeros((state_size, 1))
    concentrations: dict[str, np.ndarray] = {}
    for i, drug in enumerate(config.drugs):
        c_mg_l = np.maximum(y_full[2 * i + 1, :], 0.0) / drug.vd_l
        concentrations[drug.generic_name] = c_mg_l * 1000.0
    metabolite_concentrations: dict[str, np.ndarray] = {}
    for m_idx, met in enumerate(metabolites):
        c_mg_l = np.maximum(y_full[2 * n_drugs + m_idx, :], 0.0) / met.vd_metabolite_l
        metabolite_concentrations[met.metabolite_name] = c_mg_l * 1000.0
    peripheral_concentrations: dict[str, np.ndarray] = {}
    peripheral_offset = 2 * n_drugs + n_met + n_enz
    for drug_idx, slot in peripheral_index.items():
        drug = config.drugs[drug_idx]
        if drug.peripheral_vd_l is None:
            continue
        a_periph = np.maximum(y_full[peripheral_offset + slot, :], 0.0)
        c_mg_l = a_periph / drug.peripheral_vd_l
        peripheral_concentrations[drug.generic_name] = c_mg_l * 1000.0
    enzyme_activity = _extract_enzyme_activity(y_full, n_drugs, n_met, enzyme_names)
    steady_state_info = _compute_steady_state_info(time_hours, concentrations, config)
    dose_event_dicts = [{'time_h': de.time_h, 'dose_mg': de.dose_mg, 'drug_name': config.drugs[de.medication_index].generic_name} for de in dose_events]
    return SimulationResult(time_hours=time_hours, concentrations=concentrations, metabolite_concentrations=metabolite_concentrations, dose_events=dose_event_dicts, enzyme_activity=enzyme_activity, steady_state_info=steady_state_info, peripheral_concentrations=peripheral_concentrations)
_MW_APPROX: dict[str, float] = {'fluoxetine': 309.3, 'sertraline': 306.2, 'paroxetine': 329.4, 'citalopram': 324.4, 'escitalopram': 324.4, 'fluvoxamine': 318.3, 'venlafaxine': 277.4, 'duloxetine': 297.4, 'desvenlafaxine': 263.4, 'amitriptyline': 277.4, 'nortriptyline': 263.4, 'clomipramine': 314.9, 'aripiprazole': 448.4, 'quetiapine': 383.5, 'olanzapine': 312.4, 'risperidone': 410.5, 'ziprasidone': 412.9, 'clozapine': 326.8, 'lurasidone': 492.7, 'paliperidone': 426.5, 'haloperidol': 375.9, 'chlorpromazine': 318.9, 'carbamazepine': 236.3, 'lamotrigine': 256.1, 'valproic acid': 144.2, 'bupropion': 239.7, 'trazodone': 371.9, 'mirtazapine': 265.4, 'buspirone': 385.5, 'alprazolam': 308.8, 'diazepam': 284.7, 'methadone': 309.4, 'tramadol': 263.4, 'propranolol': 259.3, 'donepezil': 379.5, 'buprenorphine': 467.6}

def build_drug_configs_from_db(db_session: Any, medication_ids: list[int], cyp2d6_phenotype: str='normal', cyp2c19_phenotype: str='normal') -> list[DrugConfig]:
    from models import CYP450Profile, Medication
    from services.metabolite_tracker import MetaboliteParams
    configs: list[DrugConfig] = []
    meds = db_session.query(Medication).filter(Medication.id.in_(medication_ids)).all()
    med_by_id = {m.id: m for m in meds}
    for idx, med_id in enumerate(medication_ids):
        med = med_by_id.get(med_id)
        if med is None:
            raise ValueError(f'Medication id={med_id} not found')
        gn = (med.generic_name or '').lower()
        cl = float(med.clearance_l_per_h or (med.half_life_hours and 0.693 * float(med.volume_of_distribution_l or 100.0) / float(med.half_life_hours)) or 5.0)
        mw = _MW_APPROX.get(gn, 350.0)
        cyp_profiles = db_session.query(CYP450Profile).filter(CYP450Profile.medication_id == med_id).all()
        enzyme_substrates: list[EnzymeParams] = []
        enzyme_inhibitions: list[InhibitorParams] = []
        mbi_effects: list[MBIParams] = []
        induction_effects: list[InductionParams] = []
        for cyp in cyp_profiles:
            if cyp.role == 'substrate' and cyp.vmax_nmol_per_h and cyp.km_nm:
                km_mg_l = float(cyp.km_nm) * mw / 1000000.0
                vmax_calibrated = cl * km_mg_l
                enzyme_substrates.append(EnzymeParams(enzyme_name=cyp.enzyme, vmax=vmax_calibrated, km=km_mg_l, fraction_metabolized=float(cyp.fraction_metabolized or 0.5)))
            elif cyp.role == 'inhibitor' and cyp.ki_nm:
                inh_mw = _MW_APPROX.get(gn, 350.0)
                ki_mg_l = float(cyp.ki_nm) * inh_mw / 1000000.0
                enzyme_inhibitions.append(InhibitorParams(enzyme_name=cyp.enzyme, ki=ki_mg_l, drug_index=idx))
                # Mechanism-based inactivation is applied ONLY where a source
                # documents it. Previously any inhibitor tagged "strong" was
                # given k_inact = 10 * k_deg with the competitive Ki reused as
                # K_I, which invented enzyme destruction for interactions that
                # are purely reversible. See AUDIT.md F-3 and F-24: Sager 2014
                # reports no CYP2D6 TDI for fluoxetine or norfluoxetine, so the
                # persistence of that interaction must emerge from
                # norfluoxetine's half-life, not from enzyme inactivation.
                tdi = documented_tdi(gn, cyp.enzyme)
                if tdi is not None:
                    k_i_conc, k_inact = tdi
                    mbi_effects.append(MBIParams(enzyme_name=cyp.enzyme, k_inact=k_inact, k_i_conc=k_i_conc))
            elif cyp.role == 'inducer':
                potency = (cyp.potency or 'moderate').lower()
                e_max_map = {'strong': 2.0, 'moderate': 1.0, 'weak': 0.5}
                induction_effects.append(InductionParams(enzyme_name=cyp.enzyme, e_max=e_max_map.get(potency, 1.0), ec50=ki_mg_l if cyp.ki_nm else 0.5))
        metabolite = None
        if med.has_active_metabolite and med.metabolite_name and med.metabolite_half_life_hours:
            _METABOLITE_INHIBITORS: dict[str, tuple[str, float]] = {'fluoxetine': ('CYP2D6', 70.0), 'venlafaxine': ('CYP2D6', 1400.0)}
            is_inhibitor = False
            inhibited_enzyme = None
            met_ki = None
            if gn in _METABOLITE_INHIBITORS:
                inhibited_enzyme, ki_nm_val = _METABOLITE_INHIBITORS[gn]
                is_inhibitor = True
                met_ki = ki_nm_val * mw / 1000000.0
            metabolite = MetaboliteParams(parent_drug_index=idx, metabolite_name=med.metabolite_name, formation_fraction=float(med.metabolite_formation_fraction or 0.5), ke_metabolite=0.693 / float(med.metabolite_half_life_hours), vd_metabolite_l=float(med.volume_of_distribution_l or 100.0), is_enzyme_inhibitor=is_inhibitor, inhibited_enzyme=inhibited_enzyme, ki_nm=met_ki)
        ka = float(med.absorption_rate_constant or 0.5)
        vd = float(med.volume_of_distribution_l or 100.0)
        f = float(med.bioavailability or 0.5)
        _RENAL_OVERRIDES: dict[str, float] = {'lithium': 1.0, 'gabapentin': 0.75, 'pregabalin': 0.9, 'memantine': 0.7, 'paliperidone': 0.6, 'desvenlafaxine': 0.45, 'topiramate': 0.7, 'amisulpride': 0.5}
        if gn in _RENAL_OVERRIDES:
            renal_frac = _RENAL_OVERRIDES[gn]
        elif enzyme_substrates:
            renal_frac = max(0.0, 1.0 - sum((e.fraction_metabolized for e in enzyme_substrates)))
        else:
            renal_frac = 0.2
        configs.append(DrugConfig(index=idx, generic_name=med.generic_name, ka=ka, bioavailability=f, vd_l=vd, clearance_l_per_h=cl, renal_clearance_fraction=renal_frac, enzyme_substrates=enzyme_substrates, enzyme_inhibitions=enzyme_inhibitions, metabolite=metabolite, mbi_effects=mbi_effects, induction_effects=induction_effects))
    return configs
