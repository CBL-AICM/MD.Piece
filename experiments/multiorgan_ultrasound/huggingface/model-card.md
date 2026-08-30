---
library_name: scikit-learn
pipeline_tag: image-classification
tags:
- medical
- ultrasound
- breast-ultrasound
- interpretable-ml
license: cc-by-4.0
---

# Interpretable ultrasound evidence model — research draft

This card is a local publication draft. No model has been uploaded to Hugging Face.

## Model description

Balanced L2 logistic regression over 18 expert-mask morphology and texture features. The mask is an external expert input; the model does not perform lesion localization. Pathology, diagnosis, verification, and BI-RADS fields are never input features.

## Intended use

Reproducible research on dataset shift in benign-versus-malignant breast lesion classification. It must not be used for autonomous diagnosis, triage, kidney disease classification, or treatment decisions.

## Evaluation

- BUS-BRA patient-level five-fold OOF: AUROC 0.931 (95% CI 0.914–0.948).
- TCIA BREAST-LESIONS-USG locked external test: AUROC 0.807 (95% CI 0.753–0.859).
- BUS-UCLM patient-grouped five-fold development: AUROC 0.925 (clustered 95% CI 0.835–0.978).

The TCIA result is the best current estimate of cross-site performance and is below the 0.90 design target.

An organ-expansion experiment on 601 pathology-labeled thyroid cases yielded AUROC 0.484 for the frozen whole-image baseline and 0.489 for nested gated-attention MIL. The independent 241-case thyroid Batch 2 remains locked and unevaluated.

## Limitations

Requires expert segmentation, has not been prospectively validated, and shows material domain shift. BUS-UCLM has only 35 eligible patients. Breast results cannot be transferred to kidney etiology claims.
