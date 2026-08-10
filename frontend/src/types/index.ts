export interface MedicationSearchHit {
  /** Whether the entry carries CL, Vd and ka, which the PK-model
   *  analyses require. Roughly half the formulary does not. */
  has_pk_parameters?: boolean;
  id: number;
  generic_name: string;
  brand_names: string[];
  drug_class: string;
  sub_class: string | null;
}

export interface RegimenItem extends MedicationSearchHit {
  dosage?: string;
}

export interface MedicationDetail {
  id: number;
  generic_name: string;
  brand_names: string[];
  drug_class: string;
  sub_class: string | null;
  bioavailability: number | null;
  volume_of_distribution_l: number | null;
  clearance_l_per_h: number | null;
  half_life_hours: number | null;
  absorption_rate_constant: number | null;
  tmax_hours: number | null;
  protein_binding_pct: number | null;
  therapeutic_min_ng_ml: number | null;
  therapeutic_max_ng_ml: number | null;
  toxic_threshold_ng_ml: number | null;
  has_active_metabolite: boolean;
  metabolite_name: string | null;
  metabolite_half_life_hours: number | null;
  qtc_prolongation_risk: boolean;
  anticholinergic_potency: number;
  serotonergic_potency: number;
  cns_depression_risk: number;
  beers_criteria_flag: boolean;
  fda_pregnancy_category: string | null;
  common_dose_range: string | null;
  typical_start_dose_mg: number | null;
  max_dose_mg: number | null;
  dosing_frequency: string | null;
  notes: string | null;
  cyp450: CYP450Entry[];
}

export interface CYP450Entry {
  enzyme: string;
  relationship: string;
  potency: string | null;
  fraction_metabolized: number | null;
  ki_nm: number | null;
}

export interface InteractionRow {
  drug_a_id: number;
  drug_b_id: number;
  drug_a_name: string;
  drug_b_name: string;
  severity: string;
  mechanism_type: string;
  mechanism_detail: string;
  clinical_effect: string;
  recommendation: string;
  evidence_level: string | null;
  references: string[] | null;
  source: string;
}

export interface RiskSummary {
  interactions: InteractionRow[];
  counts_by_severity: Record<string, number>;
  top_risk: InteractionRow | null;
  serotonin_risk: string;
  qtc_risk: string;
  anticholinergic_burden: number;
  cns_depression_risk: string;
  contextual_notes: string[];
}

export interface PatientContext {
  age: number | "";
  weight_kg: number | "";
  smoking_status: boolean;
  egfr: number | "";
  hepatic_impairment: "none" | "mild" | "moderate" | "severe";
  pregnancy_status: boolean;
  cyp2d6_phenotype: string;
  cyp2c19_phenotype: string;
}

export interface DoseEventInput {
  medication_id: number;
  medication_name: string;
  event_type: "start" | "dose_change" | "stop";
  event_day: number;
  dose_mg: number;
  frequency: string;
}

/**
 * A simulation sent inline with a request rather than referenced by id.
 *
 * The API runs without a durable database, so analysis endpoints receive the
 * full spec instead of an id pointing at a stored row.
 */
export interface SimulationSpec {
  patient_weight_kg: number;
  smoking_status: boolean;
  cyp2d6_phenotype: string;
  cyp2c19_phenotype: string;
  horizon_days: number;
  dose_schedules: {
    medication_id: number;
    event_type: string;
    event_day: number;
    dose_mg: number;
    frequency: string;
  }[];
}

export interface SimulationResult {
  time_hours: number[];
  concentrations: Record<string, number[]>;
  metabolite_concentrations: Record<string, number[]>;
  dose_events: { time_h: number; dose_mg: number; drug_name: string }[];
  enzyme_activity: Record<string, number[]>;
  steady_state_info: {
    drug_name: string;
    trough_ng_ml: number;
    peak_ng_ml: number;
    time_to_steady_state_days: number | null;
  }[];
}

export interface ScenarioTemplate {
  id: number;
  name: string;
  description: string;
  medications?: string[];
  dose_events?: { medication: string; event_type: string; day: number; dose_mg: number; frequency: string }[];
}
