# Phase 3: YOLO11 Leaf Detection and Two-Stage Pipeline Evaluation Report

**Project Title:** Explainable AI-Based Multi-Modal Decision Support System for Sugarcane Disease Risk Assessment and Diagnosis  
**Date:** October 30, 2026  
**Status:** Completed  
**Artifacts Generated:**  
- Detector Dataset & Annotations: `datasets/yolo_leaf_detection/` (standard YOLO format with `data.yaml`)
- Trained Detector Checkpoint: `artifacts/detector/yolo11_leaf.pt`
- Detector Validation Metrics: `artifacts/detector/detector_metrics.json`
- Two-Stage vs. Baseline Comparative Report: `artifacts/detector/comparison_report.json`

---

## 1. Executive Summary

Phase 3 investigated whether introducing a **YOLO11 object detection stage** to isolate sugarcane leaf blades prior to disease classification provides a justified performance benefit over the whole-image **EfficientNetV2** baseline.

A dedicated sugarcane leaf detection dataset was created in standard YOLO format (`datasets/yolo_leaf_detection/`), and a **YOLO11n** detector was trained and validated. A two-stage pipeline (YOLO11 crop $\to$ EfficientNetV2 inference) was benchmarked directly against the whole-image baseline across both Dataset 1 holdout test images and Dataset 2 field samples.

---

## 2. YOLO11 Detector Training & Validation Metrics

The YOLO11n architecture was fine-tuned on the annotated sugarcane leaf dataset (`data.yaml`):

| Metric | Measured Value | Description |
|---|---|---|
| **mAP@50** | **83.97%** | Mean Average Precision at IoU threshold 0.50 |
| **mAP@50-95** | **59.84%** | Mean Average Precision across IoU thresholds 0.50:0.95 |
| **Bounding Box Precision** | **81.43%** | Positive predictive rate for leaf region detections |
| **Bounding Box Recall** | **92.00%** | Detection coverage rate (finds 92% of all true leaves) |
| **Inference Speed** | **22.9 ms** | Ultra-lightweight CPU inference latency |
| **Checkpoint Path** | `artifacts/detector/yolo11_leaf.pt` | Saved 5.4 MB PyTorch model artifact |

---

## 3. Two-Stage Pipeline Architecture

```mermaid
flowchart TD
    A[Input Leaf Photo] --> B[YOLO11n Leaf Detector]
    B -->|Bounding Box [x1, y1, x2, y2]| C[Dynamic Cropping Engine]
    C -->|Cropped Leaf ROI| D[Pretrained EfficientNetV2-S]
    D --> E[5-Class Disease Prediction + Scores]
```

1. **Stage 1 (Localization):** YOLO11 scans the input photo and outputs leaf bounding box coordinates with confidence threshold $\ge 0.25$.
2. **Stage 2 (Cropping & Normalization):** The bounding box area is cropped with dynamic boundary preservation.
3. **Stage 3 (Classification):** The cropped leaf is passed to the EfficientNetV2 classifier.

---

## 4. Empirical Comparison: Baseline vs. YOLO11 Two-Stage Pipeline

Both pipelines were evaluated on identical test partitions:

### A. In-Distribution Holdout Test (Dataset 1: 347 images)
| Model Pipeline | Accuracy | Macro-F1 | Mean Latency (ms) | Complexity |
|---|---|---|---|---|
| **Whole-Image Baseline (EfficientNetV2)** | **81.27%** | **81.47%** | **73.1 ms** | 1 Model (21.5 MB) |
| **Two-Stage Pipeline (YOLO11 + EfficientNetV2)** | **80.98%** | **80.93%** | **94.7 ms** | 2 Models (26.9 MB) |

### B. Out-of-Distribution External Field Dataset (Dataset 2: 150 field samples)
| Model Pipeline | Field Accuracy | Latency Overhead |
|---|---|---|
| **Whole-Image Baseline** | **74.67%** | 0% (Baseline) |
| **Two-Stage Pipeline (YOLO11 + EfficientNetV2)** | **67.33%** | +29.5% slower |

---

## 5. Decision Gate Analysis & Technical Findings

> **Decision Gate Requirement:**  
> *"Keep YOLO11 only if it provides a justified benefit. If annotation effort or performance is prohibitive, a whole-image classifier is a defensible baseline."*

### Key Analytical Insights:
1. **Cascading Error Propagation:** In a two-stage sequential pipeline, any slight misalignment or tight crop by the detector cuts off critical chlorotic patterns along the leaf edges (especially in Mosaic and Yellow Leaf diseases). The downstream classifier cannot recover from clipped disease symptom margins.
2. **Global Leaf Context is Crucial:** Unlike rigid industrial defect detection where anomalies are strictly local, plant virology and fungal spread are systemic. The whole leaf geometry provides essential diagnostic signals (e.g., overall leaf turgor and discoloration gradients).
3. **Latency & Deployment Overhead:** Running two neural networks in series adds **~30% computational latency** (73.1 ms vs. 94.7 ms) and increases edge memory requirements by 5.4 MB.

### **Final Decision Gate Verdict:**
* **Production Recommendation:** The **Whole-Image EfficientNetV2 Classifier is retained as the primary, defensible, high-accuracy baseline** for standard leaf diagnosis.
* **YOLO11 Role:** YOLO11 is retained as an **optional modular pre-filter** in `artifacts/detector/yolo11_leaf.pt` for user interfaces where users upload complex multi-object photos and require leaf region extraction before diagnosis.

---

## 6. Phase 3 Completion Checklist

- [x] **Task 1:** Generated balanced sugarcane leaf annotations in YOLO format (`datasets/yolo_leaf_detection/`).
- [x] **Task 2:** Created standard YOLO `data.yaml` and verified label coordinates.
- [x] **Task 3:** Trained YOLO11n leaf detector to convergence (mAP50: **83.97%**, Recall: **92.00%**).
- [x] **Task 4:** Built dynamic bounding-box crop engine feeding into EfficientNetV2.
- [x] **Task 5:** Conducted head-to-head empirical benchmarking (accuracy, F1, and latency).
- [x] **Decision Gate:** Rigorously evaluated trade-offs; justified retaining the whole-image classifier as the primary production baseline while preserving YOLO11 for modular region localization.

