# 6. Sanity Tests

- exit code: **0** (PASS)

## stdout
```
============================= test session starts ==============================
collecting ... collected 15 items

tests/test_mdpiece/test_age_distribution.py::test_age_within_global_range_20_to_90 PASSED [  6%]
tests/test_mdpiece/test_age_distribution.py::test_age_distribution_matches_yaml_within_15pp PASSED [ 13%]
tests/test_mdpiece/test_age_distribution.py::test_elderly_mechanism_triggers_for_age_ge_70 PASSED [ 20%]
tests/test_mdpiece/test_biomarker_range.py::test_all_biomarkers_within_range PASSED [ 26%]
tests/test_mdpiece/test_comorbidity.py::test_ra_comorbidity_rates_within_tolerance PASSED [ 33%]
tests/test_mdpiece/test_dynamics.py::test_chronic_relapsing_flare_count_in_range PASSED [ 40%]
tests/test_mdpiece/test_dynamics.py::test_reversible_returns_to_baseline_after_trigger PASSED [ 46%]
tests/test_mdpiece/test_dynamics.py::test_progressive_burden_monotonic_increase PASSED [ 53%]
tests/test_mdpiece/test_reproducibility.py::test_identical_seed_identical_trajectory PASSED [ 60%]
tests/test_mdpiece/test_treatment.py::test_tnf_inhibitor_lowers_ra_das28 PASSED [ 66%]
tests/test_mdpiece/test_unpredictability.py::test_responder_class_distribution_within_5pp PASSED [ 73%]
tests/test_mdpiece/test_unpredictability.py::test_same_treatment_same_disease_has_high_variation PASSED [ 80%]
tests/test_mdpiece/test_unpredictability.py::test_adherence_records_some_dose_skips PASSED [ 86%]
tests/test_mdpiece/test_unpredictability.py::test_life_events_scheduled_for_some_patients PASSED [ 93%]
tests/test_mdpiece/test_unpredictability.py::test_subtype_assignment_present PASSED [100%]

============================= 15 passed in 51.17s ==============================

```