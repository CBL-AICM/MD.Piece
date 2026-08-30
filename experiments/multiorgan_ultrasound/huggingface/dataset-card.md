---
license: cc-by-4.0
task_categories:
- image-classification
- image-segmentation
tags:
- ultrasound
- medical-imaging
---

# Multi-site ultrasound experiment manifest — research draft

This is a metadata card for reproducibility, not a redistribution of the source images. Users must obtain each dataset from its original source and comply with its license.

## Sources

- BUS-BRA: DOI `10.5281/zenodo.8231412`, CC BY 4.0.
- TCIA BREAST-LESIONS-USG: DOI `10.7937/9WKK-Q141`, CC BY 4.0.
- BUS-UCLM: DOI `10.17632/7fvgj4jsp7.3`, CC BY 4.0; experiment mirror pinned to revision `5874ae42ce98f0e403a916981773db8e5fea4c32`.
- OASBUD: DOI `10.5281/zenodo.545928`, CC BY 4.0; download and patient-linkage audit pending.

Checksums, exclusions, roles, and claim boundaries are recorded in `params/data_sources.json` and `params/external_test_lock.json`.

## Sensitive and clinical considerations

The sources contain de-identified clinical images. They remain unsuitable for re-identification attempts or direct clinical deployment. Dataset labels and expert annotations can encode institution-specific practice and annotation bias.

