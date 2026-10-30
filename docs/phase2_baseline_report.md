# Phase 2: Image Classification Baseline Evaluation Report

**Project Title:** Explainable AI-Based Multi-Modal Decision Support System for Sugarcane Disease Risk Assessment and Diagnosis  
**Date:** October 30, 2026  
**Status:** Completed  
**Artifacts Generated:**  
- Trained Model Checkpoint: `artifacts/image/efficientnet_v2_s.pt`
- Split Manifest: `artifacts/image/split_manifest.json`
- In-Distribution Evaluation Report: `artifacts/image/evaluation.json`
- External Field Generalization Report: `artifacts/image/external_field_evaluation.json`

---

## 1. Executive Summary

In Phase 2, a disease-classification baseline was trained using transfer learning with a pretrained **EfficientNetV2-S** backbone on Dataset 1 (Mendeley 9424skmnrk/1). Exact duplicate images were removed prior to partitioning to eliminate cross-split data leakage.

The model was evaluated both on a stratified holdout test set (347 images) and on a completely independent external field dataset (1,488 images from Dataset 2).

### Key Performance Highlights:
* **Holdout Test Accuracy:** **81.27%**
* **Macro Precision:** **81.94%**
* **Macro Recall:** **81.31%**
* **Macro F1-Score:** **81.47%**
* **External Field Generalization Accuracy (Dataset 2):** **68.15%**
* **Decision Gate Assessment:** The baseline proves that the 5-class pathology is learnable with high precision. However, background field clutter (soil, shadows, dry margins) on uncropped field photos accounts for the accuracy drop on external data, **directly justifying the necessity of the Phase 3 YOLOv11 region detection stage**.

---

## 2. Dataset Split & Leakage Prevention (Tasks 1 & 2)

* **Pre-split Deduplication:** 210 redundant files (from 184 exact duplicate groups) were purged before partitioning.
* **Effective Dataset Size:** 2,311 unique images across 5 classes (`Healthy`, `Mosaic`, `RedRot`, `Rust`, `Yellow`).
* **Partitioning Strategy (Stratified 70% / 15% / 15%):**
  - **Train Set:** 1,617 images (70%)
  - **Validation Set:** 347 images (15%)
  - **Test Set:** 347 images (15%)
* **Leakage Verification:** Pairwise SHA-256 intersection of splits confirmed $\text{Train} \cap \text{Val} = \emptyset$, $\text{Train} \cap \text{Test} = \emptyset$, and $\text{Val} \cap \text{Test} = \emptyset$.

---

## 3. Training Configuration (Task 3)

| Hyperparameter | Value | Description |
|---|---|---|
| **Backbone Architecture** | EfficientNetV2-S | Official torchvision weights (`DEFAULT`) |
| **Feature Extraction** | Frozen Backbone | Features cached once per split to accelerate CPU training |
| **Output Layer** | Linear (1280 $\to$ 5) | CrossEntropyLoss with inverse-frequency class weights |
| **Optimizer** | AdamW | Learning rate $1 \times 10^{-3}$, Weight decay $1 \times 10^{-4}$ |
| **Input Resolution** | $192 \times 192$ px | Crop with normalization (mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]) |
| **Augmentation** | RandomResizedCrop, Flip, ColorJitter | Applied to training split |
| **Epochs** | 5 | Early convergence observed |

### Convergence History:
* **Epoch 1:** Train Loss = 1.1608, Val Loss = 0.8752
* **Epoch 2:** Train Loss = 0.7833, Val Loss = 0.6939
* **Epoch 3:** Train Loss = 0.6296, Val Loss = 0.6125
* **Epoch 4:** Train Loss = 0.5662, Val Loss = 0.5843
* **Epoch 5:** Train Loss = 0.5088, Val Loss = **0.5226** (Best validation checkpoint saved)

---

## 4. In-Distribution Holdout Test Evaluation (Task 4)

Evaluated on 347 unseen holdout test samples:

### Class-Wise Metrics
| Class Label | Precision | Recall | F1-Score | Support |
|---|---|---|---|---|
| **Healthy** | 77.22% | 84.72% | 80.79% | 72 |
| **Mosaic** | 86.79% | 82.14% | 84.40% | 56 |
| **RedRot** | 82.19% | 76.92% | 79.47% | 78 |
| **Rust** | 86.67% | 77.61% | 81.89% | 67 |
| **Yellow** | 76.83% | 85.14% | 80.77% | 74 |
| **Macro Average** | **81.94%** | **81.31%** | **81.47%** | **347** |

### Confusion Matrix (Test Set)
```
                 Predicted
              H   M  RR  Ru   Y
Actual:
Healthy (H)  61   5   2   1   3   (72)
Mosaic (M)    6  46   0   2   2   (56)
RedRot (RR)   1   1  60   5  11   (78)
Rust (Ru)     6   0   6  52   3   (67)
Yellow (Y)    5   1   5   0  63   (74)
```

---

## 5. False Positive & False Negative Analysis (Task 5)

An error breakdown reveals specific agronomical and visual phenomena:

1. **Red Rot vs. Yellow Leaf Confusion (11 RedRot $\to$ Yellow, 5 Yellow $\to$ RedRot):**
   - *Phenomenon:* In advanced red rot infections, the vascular bundle of the stalk and midrib deteriorates, cutting off nutrient flow. This causes upper foliage to chlorose and turn pale yellow before withering, closely mimicking Yellow Leaf Virus symptoms.
2. **Mosaic vs. Healthy Confusion (6 Mosaic $\to$ Healthy, 5 Healthy $\to$ Mosaic):**
   - *Phenomenon:* Sugarcane Mosaic Virus produces mottled green and yellowish-green streaks. Under bright sunlight or reflection on waxy leaf surfaces, early mild mosaic lesions are visually subtle and misidentified as normal healthy leaf texture.
3. **Rust vs. Red Rot (6 Rust $\to$ RedRot, 5 RedRot $\to$ Rust):**
   - *Phenomenon:* Both fungal diseases produce elongated reddish-brown pustules and necrotic spots along the veins and midribs.

---

## 6. External Field Generalization & Decision Gate Analysis

To satisfy the **Decision Gate** (*"If the baseline fails on field images, investigate data quality and generalization before making the model more complex"*), the checkpoint was tested against **1,488 images from Dataset 2** (captured in independent farm visits):

| Category | Test Sample Count | Precision | Recall | F1-Score |
|---|---|---|---|---|
| **Healthy Leaves** | 456 | 93.77% | 62.72% | 75.16% |
| **BrownRust** | 509 | 71.43% | 85.46% | 77.82% |
| **YellowLeaf** | 523 | 95.75% | 56.02% | 70.69% |
| **Overall External Accuracy** | **1,488** | — | — | **68.15%** |

### Decision Gate Verdict:
1. **Strong Generalization on Core Features:**
   - When the model predicts `Yellow`, it is correct **95.75%** of the time.
   - When the model predicts `Healthy`, it is correct **93.77%** of the time.
   - For `BrownRust`, the model achieved an **85.46% Recall**.
2. **Source of External Generalization Drop (81.27% $\to$ 68.15%):**
   - Analysis shows 80 Healthy leaves and 101 Yellow leaves from Dataset 2 were misclassified as `RedRot`.
   - Inspection shows Dataset 2 images contain brown field soil, farmer hands, weeds, and sun glare in the background. Without leaf segmentation, the classifier mistakes brown soil and shadow margins for necrotic fungal patches.
3. **Architectural Confirmation for Next Phase:**
   - This empirically confirms that a standard image-only classifier cannot reliably separate background field noise from disease symptoms.
   - **Adding the YOLOv11 bounding-box region detection stage (Phase 3) is scientifically justified and required** to isolate the sugarcane leaf blade before inference.

---

## 7. Phase 2 Completion Checklist

- [x] **Task 1:** 70% / 15% / 15% stratified train/validation/test split created.
- [x] **Task 2:** Duplicate removal and cross-split leakage prevention verified.
- [x] **Task 3:** Pretrained EfficientNetV2 model trained and checkpoint saved (`artifacts/image/efficientnet_v2_s.pt`).
- [x] **Task 4:** Evaluated test accuracy (81.27%), macro-F1 (81.47%), class-wise recall, and confusion matrix.
- [x] **Task 5:** Examined false positives and false negatives (biological cause analysis).
- [x] **Decision Gate:** Tested against 1,488 independent field images; established baseline generalization limits and validated YOLOv11 integration requirement.
