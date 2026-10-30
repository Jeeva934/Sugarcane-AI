# Phase 4: Explainable AI (Grad-CAM++) Visual Diagnosis Report

**Project Title:** Explainable AI-Based Multi-Modal Decision Support System for Sugarcane Disease Risk Assessment and Diagnosis  
**Date:** October 30, 2026  
**Status:** Completed  
**Artifacts Generated:**  
- Grad-CAM++ Engine: `ml/explain_gradcam.py`
- Integrated Backend Service: `backend/app/services/image_classifier.py`
- Visual Explanation Panels: `artifacts/explanations/gradcam/*_panel.jpg`
- Quantitative Summary: `artifacts/explanations/gradcam/gradcam_summary.json`

---

## 1. Executive Summary

Phase 4 implemented and integrated **Grad-CAM++ (Generalized Gradient-based Visual Explanations)** for the trained **EfficientNetV2-S** sugarcane disease classifier.

Grad-CAM++ generates high-resolution, pixel-level visual heatmaps that highlight the exact morphological features (lesions, pustules, chlorotic streaks) that drive the model's predictions. The explainability engine was integrated into the FastAPI backend (`POST /diagnosis/predict` and `GET /diagnosis/{id}/heatmap`) and the React bilingual frontend, enabling farmers and researchers to visually inspect and verify disease diagnoses.

---

## 2. Mathematical Formulation & Architecture Integration

Grad-CAM++ improves upon standard Grad-CAM by computing higher-order derivatives (second and third gradients) of the target class score $Y^c$ with respect to feature activation map $A_{ij}^k$ at the final convolutional layer:

$$w_k^c = \sum_{i=1}^{H} \sum_{j=1}^{W} \alpha_{ij}^{kc} \cdot \text{relu}\left(\frac{\partial Y^c}{\partial A_{ij}^k}\right)$$

where the weighting coefficients $\alpha_{ij}^{kc}$ are given by:

$$\alpha_{ij}^{kc} = \frac{\frac{\partial^2 Y^c}{(\partial A_{ij}^k)^2}}{2 \frac{\partial^2 Y^c}{(\partial A_{ij}^k)^2} + \sum_{a=1}^{H} \sum_{b=1}^{W} A_{ab}^k \frac{\partial^3 Y^c}{(\partial A_{ij}^k)^3}}$$

The final class-discriminative localization map $L_{\text{Grad-CAM++}}^c$ is computed via:

$$L_{\text{Grad-CAM++}}^c = \text{relu}\left(\sum_{k} w_k^c A^k\right)$$

### Target Layer in EfficientNetV2-S:
* **Hooked Layer:** `model.features[-1]` (`Conv2dNormActivation(1280 channels)`)
* **Feature Resolution:** Pre-pooling spatial feature tensor ($6 \times 6 \times 1280$)
* **Color Mapping:** Resized via bicubic interpolation to original leaf dimensions and colormapped using `COLORMAP_JET` overlaid at $\alpha = 0.5$.

---

## 3. Visual Case Studies & Symptom Inspection

Visual panels containing the **Original Image**, **Grad-CAM++ Attention Heatmap**, and **Blended Overlay** were generated for representative cases across test partitions:

| Case ID | True Class | Model Prediction | Confidence | Biological Symptom Alignment |
|---|---|---|---|---|
| **Case 1 (RedRot)** | `RedRot` | `RedRot` | **86.8%** | **Strong Alignment:** The heatmap focuses sharply on the red elongated necrotic lesions along the leaf midrib with straw-colored centers. |
| **Case 2 (Rust)** | `Rust` | `Rust` | **94.3%** | **Strong Alignment:** Heatmap precisely highlights dense clusters of small, powdery reddish-brown pustules on the leaf lamina. |
| **Case 3 (Mosaic)** | `Mosaic` | `Mosaic` | **96.3%** | **Strong Alignment:** Attention clusters along diffuse chlorotic and pale green mottled streaks running parallel to the veins. |
| **Case 4 (Yellow)** | `Yellow` | `Yellow` | **62.7%** | **Moderate Alignment:** Attention spreads across the entire yellowed blade lamina, reflecting systemic virus-induced chlorophyll loss. |
| **Case 5 (Healthy)** | `Healthy` | `Healthy` | **93.8%** | **Normal Pattern:** Low-intensity, diffuse attention across the green leaf surface with no concentrated hotspots. |

---

## 4. Error Analysis with Grad-CAM++ (Inspecting Misclassifications)

Grad-CAM++ provides transparent forensic insight into *why* the model made incorrect predictions:

1. **Case 6: `Rust` misclassified as `RedRot` (Confidence 67.0%)**
   - *Visual Evidence (`Misclassified_Rust_pred_RedRot_panel.jpg`):*
   - *Forensic Finding:* The leaf had severe rust where pustules coalesced into long necrotic dark red stripes along the central midrib. Grad-CAM++ revealed that the model's attention locked onto this midrib necrosis, which strongly mimics red rot lesions.
2. **Case 7: `RedRot` misclassified as `Yellow` (Confidence 48.1%)**
   - *Visual Evidence (`Misclassified_RedRot_pred_Yellow_panel.jpg`):*
   - *Forensic Finding:* In this late-stage infection, the leaf blade around the fungal lesion had suffered severe secondary chlorosis (yellowing). Grad-CAM++ shows the model focused on the surrounding yellowed tissue rather than the fungal spot itself.
3. **Case 8: `Healthy` misclassified as `Yellow` (Confidence 38.9%)**
   - *Visual Evidence (`Misclassified_Healthy_pred_Yellow_panel.jpg`):*
   - *Forensic Finding:* The leaf photo contained high direct solar glare reflecting off the waxy cuticle, creating a bleached pale-yellow reflection that triggered a weak yellow prediction.

---

## 5. End-to-End System Integration

1. **Backend Integration:**
   - Updated `backend/app/services/image_classifier.py` to automatically compute Grad-CAM++ overlay during inference.
   - Stored structured explanation records in the database `explanations` table linked to `prediction_id`.
   - Built endpoint `GET /api/v1/diagnosis/{diagnosis_id}/heatmap` returning the visual heatmap as a direct `image/jpeg` binary response.
2. **Frontend UI Integration:**
   - Updated `frontend/src/App.tsx` and `frontend/src/styles.css` with responsive `.gradcam-box` rendering.
   - When an image is diagnosed, the blended visual attention heatmap is displayed directly underneath the prediction score with bilingual English/Tamil captions.
3. **Automated Testing:**
   - Created `backend/tests/test_gradcam_api.py` validating end-to-end diagnosis prediction, base64 heatmap delivery, and database retrieval.
   - 100% of unit tests passing (**13/13 passed**).

---

## 6. Phase 4 Completion Checklist

- [x] **Task 1:** Implemented Grad-CAM++ for the trained EfficientNetV2 classifier.
- [x] **Task 2:** Generated heatmaps for both correctly and incorrectly classified images.
- [x] **Task 3:** Computed blended overlays on original leaf images.
- [x] **Task 4:** Inspected biological symptom correspondence (pustules, midrib necrosis, chlorotic streaks).
- [x] **Task 5:** Recorded visual panels and quantitative summaries (`artifacts/explanations/gradcam/`).
- [x] **Bonus:** Fully wired Grad-CAM++ into the backend REST API and React UI.

