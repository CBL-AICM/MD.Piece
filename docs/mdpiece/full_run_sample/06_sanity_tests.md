# 6. Sanity Tests

- exit code: **0** (PASS)

## stdout
```
============================= test session starts ==============================
collecting ... collected 20 items

tests/test_mdpiece/test_age_distribution.py::test_age_within_global_range_20_to_90 PASSED [  5%]
tests/test_mdpiece/test_age_distribution.py::test_age_distribution_matches_yaml_within_15pp PASSED [ 10%]
tests/test_mdpiece/test_age_distribution.py::test_elderly_mechanism_triggers_for_age_ge_70 PASSED [ 15%]
tests/test_mdpiece/test_biomarker_range.py::test_all_biomarkers_within_range PASSED [ 20%]
tests/test_mdpiece/test_comorbidity.py::test_ra_comorbidity_rates_within_tolerance PASSED [ 25%]
tests/test_mdpiece/test_dynamics.py::test_chronic_relapsing_flare_count_in_range PASSED [ 30%]
tests/test_mdpiece/test_dynamics.py::test_reversible_returns_to_baseline_after_trigger PASSED [ 35%]
tests/test_mdpiece/test_dynamics.py::test_progressive_burden_monotonic_increase PASSED [ 40%]
tests/test_mdpiece/test_reproducibility.py::test_identical_seed_identical_trajectory PASSED [ 45%]
tests/test_mdpiece/test_social_profile.py::test_every_patient_has_full_social_profile PASSED [ 50%]
tests/test_mdpiece/test_social_profile.py::test_education_distribution_varies PASSED [ 55%]
tests/test_mdpiece/test_social_profile.py::test_smoking_proportion_realistic_for_taiwan PASSED [ 60%]
tests/test_mdpiece/test_social_profile.py::test_personality_modifies_subjective_biomarkers PASSED [ 65%]
tests/test_mdpiece/test_social_profile.py::test_low_income_reduces_biologic_access PASSED [ 70%]
tests/test_mdpiece/test_treatment.py::test_tnf_inhibitor_lowers_ra_das28 PASSED [ 75%]
tests/test_mdpiece/test_unpredictability.py::test_responder_class_distribution_within_5pp PASSED [ 80%]
tests/test_mdpiece/test_unpredictability.py::test_same_treatment_same_disease_has_high_variation PASSED [ 85%]
tests/test_mdpiece/test_unpredictability.py::test_adherence_records_some_dose_skips PASSED [ 90%]
tests/test_mdpiece/test_unpredictability.py::test_life_events_scheduled_for_some_patients PASSED [ 95%]
tests/test_mdpiece/test_unpredictability.py::test_subtype_assignment_present PASSED [100%]

======================== 20 passed in 81.27s (0:01:21) =========================

```