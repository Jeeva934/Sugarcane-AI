# Interactive System Demonstration & Verification Guide

**Project:** Explainable AI Multi-Modal Decision Support System for Sugarcane Disease Risk Assessment and Diagnosis  
**Document:** Live Demonstration & Verification Protocol  
**Date:** October 30, 2026  

---

## 1. Prerequisites & Environment Setup

Ensure the virtual environment has all necessary dependencies installed:
- Python 3.10+ with `torch`, `torchvision`, `xgboost`, `shap`, `fastapi`, `uvicorn`, `sqlalchemy`, `alembic`, `onnxruntime`, `opencv-python`.
- Node.js v18+ and `npm`.

Verify database migration and seeding status:
```powershell
python -m alembic -c backend/alembic.ini upgrade head
python backend/app/db/seed_knowledge.py
```

---

## 2. Launching the Services

### 2.1 Start the FastAPI Backend Server
Open Terminal 1:
```powershell
cd e:\CLIENT\Jeeva\Sugarcane-AI
$env:PYTHONPATH = "e:\CLIENT\Jeeva\Sugarcane-AI\backend"
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```
- Verify API Readiness: [http://127.0.0.1:8000/api/v1/health/ready](http://127.0.0.1:8000/api/v1/health/ready)
- Interactive OpenAPI Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### 2.2 Start the React + Vite Frontend
Open Terminal 2:
```powershell
cd e:\CLIENT\Jeeva\Sugarcane-AI\frontend
npm run dev
```
- Open the Web Application in your browser: [http://localhost:5173](http://localhost:5173)

---

## 3. Step-by-Step Live Demonstration Script

### Demo Scenario 1: Farmer Onboarding & Biometeorological Early Warning (7 Days Ahead)
1. **Navigate to the Application:** Open [http://localhost:5173](http://localhost:5173).
2. **Switch Language:** In the header navigation bar, click the language dropdown and select **தமிழ் (Tamil)** or **English**. Notice how all navigation tabs, alerts, metric cards, and advisories instantly update.
3. **Navigate to the Environmental Risk Tab:** Click on **Environmental Risk** (or **சுற்றுச்சூழல் இடர்**).
4. **Select Farm Profile:** Choose the default farm: **Coimbatore Cane Plot (11.00° N, 76.96° E)**.
5. **Observe 7-Day Forecast & Conduciveness Scores:**
   - The system retrieves live 7-day meteorological forecasts from Open-Meteo.
   - Inspect the **Composite Risk Badge**: Displays `HIGH`, `MODERATE`, or `LOW` risk.
   - Inspect the **Sub-Disease Conduciveness Breakdown**:
     - *Red Rot Conduciveness Index*
     - *Rust Conduciveness Index*
     - *Wilt Conduciveness Index*
6. **Inspect TreeSHAP Local Drivers:**
   - Review the horizontal driver bars showing feature contributions (e.g. `rh_mean_7d`, `temp_min_7d`, `precip_sum_7d`).
   - Observe how high relative humidity ($>80\%$) pushes the probability bar upward.
7. **Read & Listen to Agronomic Recommendations:**
   - Review actionable preventative field recommendations (e.g., clearing waterlogging channels).
   - Click the **Listen / கேள்** button: hear the browser synthesize the audio advisory in the selected language.

---

### Demo Scenario 2: Leaf Image Upload, Quality Gate & Explainable Diagnosis
1. **Navigate to the Leaf Diagnosis Tab:** Click on **Leaf Diagnosis** (or **இலை நோய் கண்டறிதல்**).
2. **Test Image Quality Screening:**
   - **Upload a Clear Leaf Image:** Upload a sample from `datasets/mendeley_v1/red_rot/` or `datasets/mendeley_v1/rust/`.
   - **Observe Quality Inspection Card:**
     - *Sharpness:* Green checkmark showing high Laplacian variance.
     - *Lighting:* "Optimal" illumination.
     - *Contrast:* "High Contrast".
   - **Upload a Degraded / Blurry Image:** Upload an intentionally blurry or dark photo.
   - Observe how the quality panel displays yellow/red warning alerts: *"Image appears blurry. Hold camera steady"* or *"Lighting is dim / underexposed"*.
3. **Inspect the Diagnostic Output:**
   - Displays predicted class (e.g., **Red Rot (*Colletotrichum falcatum*)**).
   - Displays uncalibrated probability score (e.g., $89.4\%$).
   - Displays uncertainty analysis: predictive entropy ($H = 0.41$ bits) and confidence level ("High Confidence").
4. **Inspect the Grad-CAM++ Saliency Overlay:**
   - View the generated thermal heatmap overlay.
   - Point out how the red/yellow high-activation zones align directly over the central vascular midrib lesions and dark necrotic margins.
5. **Listen to Spoken Diagnosis:** Click **Listen** to hear the disease diagnosis and immediate treatment steps spoken in Tamil or English.

---

### Demo Scenario 3: Offline Mode & Edge-Case Resilience
1. **Offline HTML5 Canvas Triage:**
   - Disconnect the network or simulate offline field conditions.
   - In the diagnosis tab, click **Screen On-Device (Offline)**.
   - The browser analyzes raw canvas pixels locally, detecting red/brown necrotic index ($\frac{R}{R+G+B} > 0.45$) and rust coloration without contacting any server.
2. **Offline ONNX Runtime Inference:**
   - Run the dedicated evaluation benchmark:
     ```powershell
     python ml/test_edge_cases.py
     ```
   - Observe the ONNX runtime benchmark: CPU inference executes in **18.88 ms** with $5.36 \times 10^{-7}$ numerical discrepancy compared to PyTorch, proving sub-50ms offline deployment readiness for mobile browsers.
3. **Weather Outage Fallback:**
   - When Open-Meteo is unreachable, the backend automatically engages its climatological fallback, sets `cached=True`, marks status as `stale`, and preserves uninterrupted operation.

---

### Demo Scenario 4: Certified Agronomic Knowledge Base
1. **Navigate to Disease Guidance Tab:** Click on **Disease Guidance** (or **நோய் வழிகாட்டி**).
2. **Explore All 5 Classes:**
   - `Healthy` (*ஆரோக்கியமானது*)
   - `Red Rot` (*செவ்வழுகல் நோய்*)
   - `Rust` (*துரு நோய்*)
   - `Mosaic` (*மொசைக் வைரஸ்*)
   - `Yellow Leaf Disease` (*மஞ்சள் இலை நோய்*)
3. **Verify Certified Agronomic Protocols:**
   - Check symptom descriptions, causal organisms (*Colletotrichum falcatum*, *Puccinia melanocephala*, SCMV, SCYLD).
   - Check certified ICAR-SBI cultural practices (hot water sett treatment at $52^\circ\text{C}$ for 30 minutes, certified disease-free seed canes).
   - Check bio-controls (*Trichoderma viride* @ 2.5 kg/ha in enriched FYM).
   - Check chemical treatments (Carbendazim 0.1% sett dip, Mancozeb 0.2% foliar spray).
4. **Click the Audio Button:** Verify fluent Tamil speech synthesis of the complete technical advisory.

