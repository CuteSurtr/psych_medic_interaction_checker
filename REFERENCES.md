# References

Primary literature behind each model in NeuroTrace, mapped to the module that
implements it. Every entry below was located and verified through **PubMed**;
DOI links are given for each.

Paper PDFs are not distributed with this repository. Put local copies in
`literature/`, which is gitignored.

---

## Enzyme kinetics and CYP450 drug-drug interactions

`services/enzyme_kinetics.py`, `services/cyp450_analyzer.py`, `services/interaction_engine.py`

**Grime KH, Bird J, Ferguson D, Riley RJ (2008).** Mechanism-based inhibition of
cytochrome P450 enzymes: an evaluation of early decision making in vitro
approaches and drug-drug interaction prediction methods. *Eur J Pharm Sci*
36(2-3):175-91.
[10.1016/j.ejps.2008.10.002](https://doi.org/10.1016/j.ejps.2008.10.002) - PMID 19013237

> Source of the `k_inact` / `K_I` parameterisation and of the active-enzyme
> balance used for time-dependent inhibition. Also the basis for comparing a
> simple unbound-inhibitor algorithm against a compartmental model, which is
> the trade-off this project's dynamic enzyme pool makes.

**Kanamitsu SI, Ito K, Okuda H, Ogura K, Watabe T, Muro K, Sugiyama Y (2000).**
Prediction of in vivo drug-drug interactions based on mechanism-based
inhibition from in vitro data: inhibition of 5-fluorouracil metabolism by
(E)-5-(2-bromovinyl)uracil. *Drug Metab Dispos* 28(4):467-74. - PMID 10725316

> The canonical demonstration that in vitro `k_inact` / `K'_app` plus a
> physiologically based model predicts the in vivo AUC change. Motivates
> propagating inactivation through the enzyme pool rather than applying a
> static fold-change to clearance.

**Sekiguchi N, Kato M, Takada M, Watanabe H, Takata S, Mitsui T, Aso Y,
Ishigai M (2011).** Quantitative prediction of mechanism-based inhibition
caused by mibefradil in rats. *Drug Metab Dispos* 39(7):1255-62.
[10.1124/dmd.110.037903](https://doi.org/10.1124/dmd.110.037903) - PMID 21474682

> Shows that predictions improve markedly when the fraction metabolised by each
> isozyme is modelled separately rather than lumped. This is why CYP450
> profiles here carry a per-enzyme `fraction_metabolized` instead of a single
> clearance term.

---

## Active metabolites and prolonged inhibition

`services/metabolite_tracker.py`

**Deodhar M, Al Rihani SB, Darakjian L, Turgeon J, Michaud V (2021).**
Assessing the mechanism of fluoxetine-mediated CYP2D6 inhibition.
*Pharmaceutics* 13(2):148.
[10.3390/pharmaceutics13020148](https://doi.org/10.3390/pharmaceutics13020148) - PMID 33498694

> Directly underpins the fluoxetine/norfluoxetine handling. Establishes that
> CYP2D6 inhibition persists long after discontinuation because both parent and
> active metabolite bind with strong affinity and have long elimination
> half-lives, and that fluoxetine is additionally a mechanism-based inhibitor
> of CYP2C19. Both behaviours are represented in the metabolite tracker.

---

## Hepatic clearance

`services/hepatic_extraction.py`

**Pang KS, Rowland M (1977).** Hepatic clearance of drugs. III. Additional
experimental evidence supporting the "well-stirred" model, using metabolite
(MEGX) generated from lidocaine under varying hepatic blood flow rates and
linear conditions in the perfused rat liver in situ preparation.
*J Pharmacokinet Biopharm* 5(6):681-99.
[10.1007/BF01059690](https://doi.org/10.1007/BF01059690) - PMID 599413

> The well-stirred model, `CL_H = Q_H * f_u * CL_int / (Q_H + f_u * CL_int)`,
> used for hepatic extraction and for the unbound-fraction sensitivity in the
> extraction panel.

---

## Enzyme induction by smoking

`services/pk_simulator.py` (smoking covariate), `services/cyp450_analyzer.py`

**Scherf-Clavel M, Samanski L, Hommers LG, Deckert J, Menke A, Unterecker S
(2019).** Analysis of smoking behavior on the pharmacokinetics of
antidepressants and antipsychotics: evidence for the role of alternative
pathways apart from CYP1A2. *Int Clin Psychopharmacol* 34(2):93-100.
[10.1097/YIC.0000000000000250](https://doi.org/10.1097/YIC.0000000000000250) - PMID 30557209

> Therapeutic-drug-monitoring evidence that smoking lowers steady-state
> concentrations of clozapine, amitriptyline and mirtazapine, and that the
> effect is not purely CYP1A2. Supports treating smoking status as a covariate
> on clearance and flagging the reverse transition on cessation.

---

## Pharmacogenomic phenotypes

`services/cyp450_analyzer.py` (CYP2D6 / CYP2C19 phenotype adjustment)

**Bousman CA, Stevenson JM, Ramsey LB, et al. (2023).** Clinical
Pharmacogenetics Implementation Consortium (CPIC) guideline for CYP2D6,
CYP2C19, CYP2B6, SLC6A4, and HTR2A genotypes and serotonin reuptake inhibitor
antidepressants. *Clin Pharmacol Ther* 114(1):51-68.
[10.1002/cpt.2903](https://doi.org/10.1002/cpt.2903) - PMID 37032427

**Hicks JK, Swen JJ, Thorn CF, et al. (2013).** Clinical Pharmacogenetics
Implementation Consortium guideline for CYP2D6 and CYP2C19 genotypes and
dosing of tricyclic antidepressants. *Clin Pharmacol Ther* 93(5):402-8.
[10.1038/clpt.2013.2](https://doi.org/10.1038/clpt.2013.2) - PMID 23486447

> The source of the poor / intermediate / normal / rapid / ultrarapid
> metabolizer strata and their direction of effect on exposure. The TCA
> guideline additionally motivates modelling CYP2C19 demethylation to an active
> metabolite followed by CYP2D6 hydroxylation, which is the two-enzyme
> sequential pattern the metabolite tracker represents.

---

## Serotonin toxicity

`services/risk_calculator.py` (serotonin syndrome scoring)

**Dunkley EJC, Isbister GK, Sibbritt D, Dawson AH, Whyte IM (2003).** The
Hunter Serotonin Toxicity Criteria: simple and accurate diagnostic decision
rules for serotonin toxicity. *QJM* 96(9):635-42.
[10.1093/qjmed/hcg109](https://doi.org/10.1093/qjmed/hcg109) - PMID 12925718

> The decision rules the risk calculator follows: clonus (inducible,
> spontaneous, ocular), agitation, diaphoresis, tremor, hyperreflexia, plus
> hypertonicity with temperature above 38 C for life-threatening cases.
> Reported sensitivity 84 percent and specificity 97 percent, against 75 and 96
> percent for Sternbach's criteria - which is why these are used rather than
> the older set.

---

## Anticholinergic burden

`services/risk_calculator.py` (ACB scoring)

**Pasina L, Djade CD, Lucca U, et al. (2013).** Association of anticholinergic
burden with cognitive and functional status in a cohort of hospitalized
elderly: comparison of the Anticholinergic Cognitive Burden scale and
Anticholinergic Risk Scale. Results from the REPOSI study. *Drugs Aging*
30(2):103-12.
[10.1007/s40266-012-0044-x](https://doi.org/10.1007/s40266-012-0044-x) - PMID 23239364

> Validation of the ACB scale in 1,380 inpatients aged 65 and over,
> demonstrating a dose-response relationship between total ACB score and
> cognitive impairment. Justifies summing per-drug ACB points rather than
> flagging anticholinergics individually.

---

## Prescribing in older adults

`services/risk_calculator.py` (Beers flags, age-adjusted alerts)

**American Geriatrics Society (2023).** American Geriatrics Society 2023
updated AGS Beers Criteria for potentially inappropriate medication use in
older adults. *J Am Geriatr Soc* 71(7):2052-2081.
[10.1111/jgs.18372](https://doi.org/10.1111/jgs.18372) - PMID 37139824

**American Geriatrics Society (2025).** Alternative treatments to selected
medications in the 2023 American Geriatrics Society Beers Criteria.
*J Am Geriatr Soc* 73(9):2657-2677.
[10.1111/jgs.19500](https://doi.org/10.1111/jgs.19500) - PMID 40697073

> The 2023 criteria drive the `beers_criteria_flag` field and the age-based
> alerts. The 2025 companion supplies the alternatives to suggest alongside a
> flag, so a warning is actionable rather than merely prohibitive.

---

## Receptor occupancy

`services/receptor_occupancy.py`

**Kapur S, Zipursky R, Jones C, Remington G, Houle S (2000).** Relationship
between dopamine D2 occupancy, clinical response, and side effects: a
double-blind PET study of first-episode schizophrenia. *Am J Psychiatry*
157(4):514-20.
[10.1176/appi.ajp.157.4.514](https://doi.org/10.1176/appi.ajp.157.4.514) - PMID 10739409

> Source of the occupancy thresholds the panel annotates: likelihood of
> clinical response rises above roughly 65 percent D2 occupancy,
> hyperprolactinaemia above 72 percent, and extrapyramidal side effects above
> 78 percent. These are what make a plotted occupancy trajectory interpretable
> rather than merely a curve.

---

## Bayesian individualisation

`services/bayesian_pk.py`

**Vozeh S, Muir KT, Sheiner LB, Follath F (1981).** Predicting individual
phenytoin dosage. *J Pharmacokinet Biopharm* 9(2):131-46.
[10.1007/BF01068078](https://doi.org/10.1007/BF01068078) - PMID 7277205

> The maximum a posteriori approach implemented here: combine a population
> prior with an individual's measured concentrations to estimate that person's
> parameters. The paper shows the Bayesian estimator dominates the alternatives
> because each of them is a suboptimal special case of it, which is the
> argument for using a prior on `log CL` and `log Vd` rather than fitting each
> subject independently.

**Bruno R, Hille D, Riva A, et al. (1998).** Population
pharmacokinetics/pharmacodynamics of docetaxel in phase II studies in patients
with cancer. *J Clin Oncol* 16(1):187-96.
[10.1200/JCO.1998.16.1.187](https://doi.org/10.1200/JCO.1998.16.1.187) - PMID 9440742

> A large-scale demonstration that Bayesian estimates of clearance and AUC from
> sparse sampling predict clinical outcomes. Supports the sparse-sampling
> design the Bayesian panel assumes.

---

## Attribution

Bibliographic data retrieved from PubMed (National Library of Medicine).
Citations and DOIs above are reproduced from PubMed records.
