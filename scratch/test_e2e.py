import httpx

client = httpx.Client(base_url="http://127.0.0.1:8000/api/v1", timeout=35.0)

# 1. Login
login = client.post("/auth/login", json={"email": "test1@example.com", "password": "Test12345678!"})
assert login.status_code == 200, f"Login failed: {login.text}"
print("1. Logged in successfully as test1")

# 2. Get farms
farms = client.get("/farms").json()
assert len(farms) > 0, "No farms found"
farm = farms[0]
print(f"2. Farm loaded: {farm['name']} ({farm['latitude']}, {farm['longitude']})")

# 3. Test Option 1: Weather Guidance (Gemini AI)
guidance_res = client.post("/weather/guidance", json={
    "farm_id": farm["id"],
    "disease_class": "RedRot",
    "language_code": "en",
    "grass_age": "90 days (3 Months - Tillering)"
})
print("3. Gemini Guidance Status:", guidance_res.status_code)
if guidance_res.status_code == 200:
    g = guidance_res.json()
    print("   Risk Level:", g["risk_level"])
    print("   Summary:", g["summary"])
    print("   Actions count:", len(g["actions"]))
else:
    print("   Guidance Error:", guidance_res.text)

# 4. Test Option 2: Environmental Risk Model (XGBoost + SHAP + Gemini Age Advisory)
risk_res = client.post("/risk/predict", json={
    "farm_id": farm["id"],
    "disease_class": "RedRot",
    "grass_age": "90 days (3 Months - Tillering)"
})
print("4. Risk Prediction Status:", risk_res.status_code)
if risk_res.status_code == 200:
    r = risk_res.json()
    print("   Risk Score:", r["disease_presence_score"])
    print("   Top SHAP Driver:", r["primary_drivers"][0]["feature"], "effect:", r["primary_drivers"][0]["effect"])
    print("   Gemini Age Guidance:", r.get("age_ai_guidance"))
else:
    print("   Risk Error:", risk_res.text)

