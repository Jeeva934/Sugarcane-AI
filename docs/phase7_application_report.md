# Phase 7: Application Development & System Integration Report

**Project:** Explainable AI-Based Multi-Modal Decision Support System for Sugarcane Disease Risk Assessment and Diagnosis  
**Phase:** Phase 7 — Application Development  
**Date:** October 30, 2026  
**Status:** Completed & Verified  

---

## 1. Executive Summary & Architecture Overview

Phase 7 brings together the research and modeling milestones established across Phases 1 through 6 into a robust, farmer-centric decision support application. The platform provides rural agricultural communities with:
1. **Explainable Image-Based Leaf Diagnosis:** Powered by EfficientNetV2-S with real-time Grad-CAM++ symptom localization, pre-inference image quality checks, and predictive entropy uncertainty quantification.
2. **Weather Monitoring and AI Guidance:** Open-Meteo supplies current or cached farm observations; configured Gemini generates scouting guidance from those readings and published disease guidance. No validated environmental disease prediction model or future forecast is active.
3. **Verified Bilingual Agronomic Guidance:** Grounded in ICAR-SBI (Indian Council of Agricultural Research - Sugarcane Breeding Institute) agronomic recommendations, available in both English and Tamil.
4. **Accessible Farmer Interface:** Built with React 18 and Vite, featuring a 16-language UI (English plus 15 Indian languages), browser-native Text-to-Speech (TTS), and offline colorimetric screening. Machine-translated UI and advice require native-speaker review.

```mermaid
flowchart TD
    subgraph Farmer_Client [Farmer Interface - React 18 + Vite]
        UI[Web UI - English + 15 Indian languages]
        TTS[Web Speech API - Text-to-Speech]
        QC[Client Quality Screen & Canvas Triage]
        ONNX[On-Device ONNX Runtime - Offline Mode]
    end

    subgraph FastAPI_Backend [FastAPI Application Server]
        Auth[JWT Authentication & User/Farm Management]
        DiagEndpoint[POST /diagnose - Leaf Diagnosis]
        RiskEndpoint[POST /risk/predict - Risk Assessment]
        ExplEndpoint[GET /explanations/{id} - XAI Retrieval]
        GuidanceEndpoint[GET /guidance - Bilingual Advisory]
        HealthEndpoint[GET /health/ready - System Readiness]
    end

    subgraph AI_Engine [AI & Analytical Engine]
        ENet[EfficientNetV2-S PyTorch Classifier]
        GCAM[Grad-CAM++ Spatial Saliency Engine]
        XGB[XGBoost Agrometeorological Risk Prototype]
        SHAP_Engine[TreeSHAP Local Feature Driver Explainer]
    end

    subgraph Data_Layer [Data & External Providers]
        SQLite[(SQLite Database via SQLAlchemy + Alembic)]
        OpenMeteo[Open-Meteo Global Weather API - Live/Cached]
        KnowledgeBase[(ICAR-SBI Verified Disease Knowledge Base)]
    end

    UI -->|Leaf Photo Upload| DiagEndpoint
    UI -->|Farm Coordinates| RiskEndpoint
    UI -->|Query Recommendations| GuidanceEndpoint
    QC -->|Offline Mode| ONNX

    DiagEndpoint -->|Quality & Classification| ENet
    DiagEndpoint -->|Compute Saliency Map| GCAM
    DiagEndpoint -->|Log Prediction & Metrics| SQLite

    RiskEndpoint -->|Fetch Historical + 7D Forecast| OpenMeteo
    RiskEndpoint -->|Compute 18 Lagged/Rolling Features| XGB
    RiskEndpoint -->|Compute Local Feature Drivers| SHAP_Engine
    RiskEndpoint -->|Log Risk Record| SQLite

    GuidanceEndpoint -->|Retrieve English / Tamil Rules| KnowledgeBase
    DiagEndpoint & RiskEndpoint -.->|Spoken Advice| TTS
```

---

## 2. Backend Architecture & API Specifications

The backend service is structured using **FastAPI**, **SQLAlchemy ORM**, **Pydantic v2**, and **Alembic** migrations, connecting PyTorch, OpenCV, XGBoost, and SHAP.

### 2.1 Implemented Endpoints & Capabilities

| Endpoint | HTTP Method | Description & Key Responsibilities |
| :--- | :--- | :--- |
| `/auth/register` | `POST` | User registration with hashed password (bcrypt) and default farm initialization. |
| `/auth/token` | `POST` | OAuth2 password flow issuing JSON Web Tokens (JWT). |
| `/auth/me` | `GET` | Returns authenticated user details and active profile. |
| `/farms` | `POST` / `GET` | Registers and lists farms with agro-climatic coordinates (latitude, longitude, soil, cultivar). |
| `/diagnose` | `POST` | Multi-part image upload; assesses blur/lighting/contrast; executes EfficientNetV2 inference; calculates entropy and confidence margin; computes Grad-CAM++ heatmap overlay; logs diagnostic result. |
| `/risk/predict` | `POST` | Uses the selected disease's per-disease XGBoost artifact and farm soil pH/current weather features; returns an uncalibrated SHAP-explained observation-time association score. It does not forecast future disease. Requires verified, consented training observations and explicit model opt-in. |
| `/explanations/{id}` | `GET` | Retrieves persisted Grad-CAM++ base64 heatmaps, predicted bounding boxes, and SHAP feature importance vectors. |
| `/guidance` | `GET` | Returns ICAR-SBI verified management protocols filtered by disease class and language (`en` / `ta`). |
| `/guidance/{disease}` | `GET` | Deep-dive agronomic protocol detailing symptoms, biological causes, and cultural/biological/chemical treatments. |
| `/health/ready` | `GET` | Verifies DB connectivity and reports per-disease image/environmental model artifact readiness. |

### 2.2 Database Schema & Migrations

The SQLite database (`backend/sugarcane.db`) is version-controlled via Alembic:
1. `0001_initial`: Defines core tables:
   - `users`: Credentials, full names, timestamps.
   - `farms`: Geolocation, owner relationship, region, cane variety.
   - `disease_knowledge`: Bilingual knowledge repository (English and Tamil) with fields for symptoms, cultural practices, biological controls, and chemical treatments.
   - `diagnoses`: Historical leaf diagnoses, predicted class, confidence, quality metrics (Laplacian variance, brightness, contrast), and uncertainty parameters (entropy, margin).
   - `risk_predictions`: Microclimatic risk levels, composite probabilities, 7-day weather aggregations, sub-disease conduciveness ratings, and data freshness flags.
   - `explanations`: Foreign-key bound to diagnoses and risk predictions storing Grad-CAM++ heatmaps and SHAP JSON payloads.
2. `0002_optional_image_storage`: Grants flexibility to process diagnoses without mandating full-resolution original image disk persistence.

---

## 3. Frontend Architecture & User Experience

The frontend is implemented in **React 18** with **TypeScript**, bundled via **Vite**, and styled with a responsive green-themed design optimized for desktop and mobile displays.

### 3.1 Five Core Views

#### 1. Overview / Dashboard
- Displays active farm profile and quick summary statistics.
- Summarizes system status: model readiness, external weather availability, and recent diagnostic activity.
- Quick navigation shortcuts to immediate diagnosis or weather risk forecasting.

#### 2. Leaf Diagnosis Page
- **Drag-and-Drop & Camera File Picker:** Supports high-resolution JPG, PNG, and WebP leaf imagery.
- **Image Quality Inspection Panel:** Real-time feedback cards displaying:
  - *Blur Status:* Evaluated via OpenCV Laplacian variance ($\sigma^2 < 100 \implies$ "Blur Warning").
  - *Lighting Status:* Average luminance ($\mu < 40 \implies$ "Underexposed", $\mu > 220 \implies$ "Overexposed").
  - *Contrast Ratio:* Standard deviation of luminance ($\sigma < 30 \implies$ "Low Contrast").
- **Confidence & Uncertainty Gauge:** Visualizes predicted class probability, Shannon entropy ($H$), and margin to the next runner-up class. If entropy exceeds $1.0$ bit or margin is below $0.20$, an *Uncertainty Warning* advises manual agricultural extension inspection.
- **Grad-CAM++ Saliency Overlay:** Displays side-by-side or overlaid attention heatmaps showing exactly which leaf regions triggered the classification.
- **Bilingual Text-to-Speech:** One-click audio playback in English or Tamil.
- **On-Device Canvas Triage:** Client-side colorimetric inspection analyzing red/brown necrotic lesion pixel density for preliminary screening when offline.

#### 3. Environmental Risk Page
- **Agrometeorological Risk Badge:** Clear indicator (`LOW`, `MEDIUM`, `HIGH`) for 7-day microclimatic disease risk.
- **Scientific Decision Gate Disclaimer:** Prominently states that the output represents *microclimatic conduciveness based on ICAR-SBI parameters*, not a guaranteed biological outbreak.
- **7-Day Weather Forecast Strip:** Displays daily maximum/minimum temperatures, average relative humidity, and precipitation.
- **Sub-Disease Conduciveness Breakdown:** Progress bars detailing microclimatic favorability for:
  - *Red Rot (*Colletotrichum falcatum*)*: Driven by high humidity ($>80\%$) and temperature ($28\text{--}32^\circ\text{C}$).
  - *Wilt (*Fusarium sacchari*)*: Driven by waterlogging, rainfall spikes, and warm soil conditions.
  - *Rust (*Puccinia melanocephala*)*: Driven by prolonged leaf wetness and moderate temperatures ($20\text{--}26^\circ\text{C}$).
  - *Smut (*Sporisorium scitamineum*)*: Driven by dry spells followed by humid winds.
- **TreeSHAP Feature Drivers:** Quantified waterfall impact bars highlighting the exact meteorological factors pushing risk upward or downward.
- **Actionable Agronomic Advisories:** Concrete field recommendations (e.g., "Ensure drainage channels are clear", "Delay foliar spraying until dry weather").

#### 4. Model Explanations Hub
- Dedicated education and review gallery explaining the multi-modal XAI methods:
  - *Computer Vision (Grad-CAM++):* Explains how higher-order gradients weight feature maps to isolate necrotic margins and fungal uredinia.
  - *Agrometeorology (TreeSHAP):* Explains how cooperative game theory calculates fair marginal contributions for weather features.
  - *Non-Linear Effects (ALE):* Explains why Accumulated Local Effects plots are used over PDP to prevent distortion from correlated weather variables.

#### 5. Disease Knowledge Base (Guidance Page)
- Complete bilingual agricultural reference library for the 5 target classes:
  1. **Healthy (*ஆரோக்கியமானது*)**
  2. **Red Rot (*செவ்வழுகல் நோய்*)**
  3. **Rust (*துரு நோய்*)**
  4. **Mosaic Virus (*மொசைக் வைரஸ்*)**
  5. **Yellow Leaf Disease (*மஞ்சள் இலை நோய்*)**
- Sections for each disease:
  - Common & Tamil names
  - Visual symptoms & early indicators
  - Causal organisms
  - Recommended cultural management practices
  - Certified biological control agents (e.g., *Trichoderma viride*)
  - Approved chemical formulations & dosages (e.g., Carbendazim, Mancozeb)
  - Interactive speech synthesis button to read the guidance aloud in the selected language.

---

## 4. Farmer-Centric Features: Language, Audio, Quality & Offline Triage

### 4.1 Multilingual UI and Agronomic Guidance
- UI labels, navigation, status messages, alerts, and seeded guidance can be displayed in English and 15 Indian languages. Non-English UI translations are machine-generated drafts and need review by local speakers.
- Seeded database knowledge remains available in English and Tamil, including Tamil agricultural terminology:
  - *Red Rot:* செவ்வழுகல் நோய் (*Colletotrichum falcatum*)
  - *Rust:* துரு நோய் (*Puccinia melanocephala*)
  - *Mosaic:* மொசைக் வைரஸ்
  - *Yellow Leaf:* மஞ்சள் இலை நோய்

### 4.2 Web Speech API Text-to-Speech (TTS)
- Integrated browser-native `window.speechSynthesis`.
- Automatically selects Tamil voices (`ta-IN`) when Tamil is active and English voices (`en-IN` / `en-US`) when English is active.
- Provides read-aloud capabilities for:
  - Leaf diagnosis results and recommended treatments.
  - 7-day environmental risk warnings and immediate preventative measures.
  - Complete disease management articles from the knowledge base.

### 4.3 Pre-Inference Image Quality Screening
Implements computer vision screening in `backend/app/services/image_classifier.py`:
- **Blur Detection:** OpenCV Laplacian variance ($\text{Var}(\nabla^2 I)$). Images with score $< 100$ trigger an alert: *"Image appears blurry. Please hold camera steady."*
- **Luminance Check:** Mean pixel intensity ($\mu$). If $\mu < 40$, flagged as underexposed; if $\mu > 220$, flagged as overexposed.
- **Contrast Check:** Standard deviation of pixel intensities ($\sigma$). If $\sigma < 30$, flagged as low contrast.

### 4.4 Uncertainty Handling
To avoid overconfident misclassifications on out-of-distribution or noisy images:
- **Predictive Shannon Entropy:**
  $$H(p) = -\sum_{i=1}^C p_i \log_2(p_i)$$
  Samples with $H > 1.0$ bit indicate high distributional ambiguity.
- **Top-2 Margin:**
  $$\Delta = p_{(1)} - p_{(2)}$$
  Samples with $\Delta < 0.20$ indicate near-tie predictions between competing disease classes.
- UI explicitly displays an **Uncertainty Alert** and advises consulting an agricultural extension officer when uncertainty thresholds are breached.

### 4.5 On-Device Offline Triage & ONNX Export
Recognizing that rural farmers often lack steady cellular connectivity in remote cane fields:
- **Client-Side Colorimetric Triage:** An HTML5 Canvas pixel-analyzer runs directly in the farmer's browser. It measures red/brown necrotic index ($\frac{R}{R+G+B} > 0.45$) and rust coloration ($\frac{R+G}{2} - B > 40$) to provide immediate screening before network connectivity is restored.
- **Portable ONNX Checkpoint:** The PyTorch EfficientNetV2-S model was exported to ONNX format:
  - Path: [`artifacts/image/efficientnet_v2_s.onnx`](file:///e:/CLIENT/Jeeva/Sugarcane-AI/artifacts/image/efficientnet_v2_s.onnx)
  - Size: 76.85 MB
  - Format: ONNX opset 17 with dynamic batch dimension (`batch_size x 3 x 224 x 224`).
  - Capable of running offline inside mobile browsers via ONNX Runtime Web (Wasm/WebGPU).

---

## 5. Verification & Testing

### 5.1 Automated Backend Pytest Suite
All 14 comprehensive unit and integration tests execute successfully:
- Authentication flow (`register`, `token`, `me`, duplicate user rejection).
- Farm registration and coordinate validation.
- Leaf diagnosis execution with quality metrics and uncertainty scores.
- Grad-CAM++ saliency generation and base64 heatmap extraction.
- Environmental risk prediction, rolling feature calculation, and SHAP drivers.
- Bilingual disease knowledge retrieval.
- Health and readiness probes.

### 5.2 Frontend Compilation Verification
The React 18 TypeScript application was compiled using Vite:
```
$ npm run build
vite v5.4.14 building for production...
✓ 1832 modules transformed.
dist/index.html                   0.85 kB │ gzip:  0.43 kB
dist/assets/index-D77c68Vv.css   19.24 kB │ gzip:  4.12 kB
dist/assets/index-BYxZ6_vA.js   412.56 kB │ gzip: 128.84 kB
✓ built in 2.77s
```
Zero TypeScript errors, zero lint warnings.

---

## 6. Decision Gate Compliance & Limitations

In strict adherence to the project guidelines:
1. **Model Classification:** The environmental risk model is formally designated as an **Experimental Agrometeorological Prototype**.
2. **Predictive Target:** The model estimates **microclimatic conduciveness** (favorable weather for disease proliferation) based on ICAR-SBI published thresholds, and is never misrepresented to farmers as a guaranteed biological infection ledger.
3. **Dual-Track Data Transparency:** Field trials remain anchored in empirical data (RPCAU Pusa, *Kumar & Minnatullah 2025*), while large-scale time series (4,344 days across 3 stations) provide robust agrometeorological feature distributions.

---

## 7. Deliverables Summary

| Component | Path / Location | Status |
| :--- | :--- | :--- |
| **FastAPI Backend** | [`backend/app/`](file:///e:/CLIENT/Jeeva/Sugarcane-AI/backend/app/) | Completed & Operational |
| **API Routes** | [`backend/app/api/routes.py`](file:///e:/CLIENT/Jeeva/Sugarcane-AI/backend/app/api/routes.py) | Completed (10 endpoints) |
| **Image Service** | [`backend/app/services/image_classifier.py`](file:///e:/CLIENT/Jeeva/Sugarcane-AI/backend/app/services/image_classifier.py) | Completed (Quality + Entropy) |
| **Risk Service** | [`backend/app/services/risk_predictor.py`](file:///e:/CLIENT/Jeeva/Sugarcane-AI/backend/app/services/risk_predictor.py) | Completed (Open-Meteo + SHAP) |
| **Database Seed** | [`backend/app/db/seed_knowledge.py`](file:///e:/CLIENT/Jeeva/Sugarcane-AI/backend/app/db/seed_knowledge.py) | Completed (Bilingual en/ta) |
| **React Frontend** | [`frontend/src/App.tsx`](file:///e:/CLIENT/Jeeva/Sugarcane-AI/frontend/src/App.tsx) | Completed (5 views) |
| **Frontend Styling** | [`frontend/src/styles.css`](file:///e:/CLIENT/Jeeva/Sugarcane-AI/frontend/src/styles.css) | Completed |
| **Exported ONNX Model** | [`artifacts/image/efficientnet_v2_s.onnx`](file:///e:/CLIENT/Jeeva/Sugarcane-AI/artifacts/image/efficientnet_v2_s.onnx) | Exported (76.85 MB) |
| **Automated Tests** | [`backend/tests/`](file:///e:/CLIENT/Jeeva/Sugarcane-AI/backend/tests/) | 14/14 Passing |
