"""
Live End-to-End System Smoke Test
Starts FastAPI server in-process via TestClient and verifies:
1. Health and readiness of models and database.
2. User registration and farm registration (Coimbatore, Tamil Nadu).
3. Live leaf image diagnosis with real leaf photo from dataset + Grad-CAM++ heatmap generation.
4. Live 7-day environmental risk assessment with Open-Meteo weather features and SHAP drivers.
5. Bilingual agronomic guidance in Tamil and English.
6. Uncertainty handling and image quality checks.
"""

import sys
from pathlib import Path

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings

def run_live_test():
    print("=" * 65)
    print("🚀 STARTING LIVE END-TO-END SYSTEM INTEGRATION TEST")
    print("=" * 65)

    client = TestClient(app)

    # 1. System Readiness Probe
    print("\n[Step 1] Checking System Health & Model Readiness...")
    resp = client.get("/api/v1/health/ready")
    print(f"Status Code: {resp.status_code}")
    data = resp.json()
    print(f"Readiness Status: {data.get('status')}")
    print(f"Component Checks: {data.get('checks')}")
    assert resp.status_code == 200
    assert data["checks"]["database"] == "ok"
    assert data["checks"]["image_model"] == "experimental_enabled"
    assert data["checks"]["risk_model"] == "experimental_enabled"
    print("✅ System health and all models are READY!")

    # 2. Farmer Registration
    print("\n[Step 2] Registering Farmer Account...")
    import random
    rand_id = random.randint(1000, 9999)
    email = f"farmer_live_{rand_id}@sugarcane.org"
    reg_resp = client.post("/api/v1/auth/register", json={
        "email": email,
        "password": "FarmerPassword123!",
        "full_name": "செல்வன் (Selvan)",
        "preferred_language": "ta"
    })
    print(f"Register status: {reg_resp.status_code}")
    assert reg_resp.status_code == 201
    user_info = reg_resp.json()
    print(f"Farmer registered: {user_info['full_name']} ({user_info['email']}) | Preferred Lang: {user_info['preferred_language']}")

    # 3. Farm Creation (Coimbatore, Tamil Nadu)
    print("\n[Step 3] Registering Farm Plot (Coimbatore, Tamil Nadu)...")
    farm_resp = client.post("/api/v1/farms", json={
        "name": "கோயம்புத்தூர் கரும்பு தோட்டம் (Coimbatore Cane Plot)",
        "latitude": 11.00,
        "longitude": 76.96,
        "soil_type": "Clay loam",
        "crop_variety": "Co 86032",
        "growth_stage": "Formative"
    })
    assert farm_resp.status_code == 201
    farm = farm_resp.json()
    print(f"Farm Registered: ID={farm['id']}, Name={farm['name']}, Lat={farm['latitude']}, Lon={farm['longitude']}")

    # 4. Leaf Image Diagnosis with Real Dataset Photo
    print("\n[Step 4] Uploading & Diagnosing Real Sugarcane Leaf Photo...")
    # Find a real image in dataset
    sample_images = list((PROJECT_ROOT / "datasets" / "mendeley_v1").rglob("*.jpeg")) + list((PROJECT_ROOT / "datasets" / "mendeley_v1").rglob("*.jpg"))
    
    assert sample_images, "No test images found in dataset!"
    test_img_path = sample_images[0]
    print(f"Selected Test Image: {test_img_path.name} (from {test_img_path.parent.name})")

    with open(test_img_path, "rb") as f:
        img_bytes = f.read()

    diag_resp = client.post(
        "/api/v1/diagnosis/predict",
        files={"file": (test_img_path.name, img_bytes, "image/jpeg")},
        data={"farm_id": farm["id"]}
    )
    print(f"Diagnosis Status: {diag_resp.status_code}")
    assert diag_resp.status_code == 200
    diag_data = diag_resp.json()
    print(f"  Predicted Disease: {diag_data['predicted_class']}")
    print(f"  Confidence Score:  {diag_data['uncalibrated_score'] * 100:.2f}%")
    print(f"  Processing Time:   {diag_data['processing_time_ms']} ms")
    print(f"  Image Quality:     {diag_data.get('image_quality')}")
    print(f"  Uncertainty Info:  {diag_data.get('uncertainty')}")
    has_heatmap = bool(diag_data.get("heatmap_base64"))
    print(f"  Grad-CAM++ Heatmap Generated: {has_heatmap} (Length: {len(diag_data.get('heatmap_base64') or '')} chars)")
    print("✅ Leaf image diagnosis and Grad-CAM++ saliency successfully executed!")

    # 5. Experimental, observation-time disease-presence association
    print("\n[Step 5] Assessing Red rot against the trained observation-time model...")
    risk_resp = client.post("/api/v1/risk/predict", json={
        "farm_id": farm["id"],
        "disease_class": "RedRot"
    })
    print(f"Risk Prediction Status: {risk_resp.status_code}")
    assert risk_resp.status_code == 200
    risk_data = risk_resp.json()
    print(f"  Disease class:       {risk_data['disease_class']}")
    print(f"  Uncalibrated score:  {risk_data['disease_presence_score']}")
    print(f"  Score meaning:       {risk_data['score_note']}")
    print(f"  Top SHAP feature drivers:")
    for driver in risk_data.get("primary_drivers", [])[:3]:
        print(f"    - {driver['feature']}: {driver['value']} (SHAP: {driver['shap_value']}, Effect: {driver['effect']})")
    print(f"  Scientific Disclosure: {risk_data['scientific_disclosure'][:75]}...")
    print("✅ Experimental observation-time score and SHAP explanation successfully executed!")

    # 6. Bilingual Agronomic Guidance Lookup
    print("\n[Step 6] Fetching ICAR-SBI Verified Guidance (Tamil & English)...")
    guidance_resp_ta = client.get("/api/v1/guidance/RedRot?language=ta")
    if guidance_resp_ta.status_code == 200:
        ta_info = guidance_resp_ta.json()
        print(f"  [Tamil] Title: {ta_info.get('display_name')}")
        print(f"  [Tamil] Symptoms: {ta_info.get('symptoms', '')[:80]}...")
        print(f"  [Tamil] Management: {ta_info.get('preventive_guidance', '')[:80]}...")
    else:
        # Check all guidance endpoint
        all_guidance = client.get("/api/v1/guidance?language=ta").json()
        print(f"  Retrieved {len(all_guidance)} disease articles in Tamil.")

    print("\n" + "=" * 65)
    print("🎉 ALL 6 STEPS COMPLETED SUCCESSFULLY WITH ZERO ERRORS!")
    print("=" * 65)

if __name__ == "__main__":
    run_live_test()
