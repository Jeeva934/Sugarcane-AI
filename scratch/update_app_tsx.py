path = "frontend/src/App.tsx"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add grassAge state
state_old = """function RiskAssessment({ farms, t, language }: { farms: Farm[]; t: typeof copy.en; language: Language }) {
  const [farmId, setFarmId] = useState("");
  const [targetDisease, setTargetDisease] = useState("RedRot");"""

state_new = """function RiskAssessment({ farms, t, language }: { farms: Farm[]; t: typeof copy.en; language: Language }) {
  const [farmId, setFarmId] = useState("");
  const [targetDisease, setTargetDisease] = useState("RedRot");
  const [grassAge, setGrassAge] = useState("90 days (3 Months - Tillering)");"""

content = content.replace(state_old, state_new, 1)

# 2. Add grass_age to submit (/risk/predict)
submit_old = """      const res = await api<RiskResult>("/risk/predict", {
        method: "POST",
        body: JSON.stringify({ farm_id: farmId, disease_class: targetDisease })
      });"""

submit_new = """      const res = await api<RiskResult>("/risk/predict", {
        method: "POST",
        body: JSON.stringify({ farm_id: farmId, disease_class: targetDisease, grass_age: grassAge })
      });"""

content = content.replace(submit_old, submit_new, 1)

# 3. Add grass_age to analyzeWeather (/weather/guidance)
analyze_old = """      const result = await api<WeatherGuidance>("/weather/guidance", {
        method: "POST",
        body: JSON.stringify({ farm_id: selectedFarm.id, disease_class: targetDisease, language_code: requestLanguage }),
      });"""

analyze_new = """      const result = await api<WeatherGuidance>("/weather/guidance", {
        method: "POST",
        body: JSON.stringify({ farm_id: selectedFarm.id, disease_class: targetDisease, language_code: requestLanguage, grass_age: grassAge }),
      });"""

content = content.replace(analyze_old, analyze_new, 1)

# 4. Add Grass age selector in the form right after targetDisease select
dropdown_old = """        <select
          id="risk-disease"
          className="text-input"
          value={targetDisease}
          onChange={(event) => { setTargetDisease(event.target.value); setRiskResult(null); clearAiGuidance(); setError(""); }}
        >
          <option value="Mosaic"><LocalText source="Mosaic" /></option>
          <option value="RedRot"><LocalText source="Red rot" /></option>
          <option value="Rust"><LocalText source="Rust" /></option>
          <option value="Yellow"><LocalText source="Yellow leaf" /></option>
          <option value="Wilt"><LocalText source="Wilt" /></option>
        </select>"""

dropdown_new = """        <select
          id="risk-disease"
          className="text-input"
          value={targetDisease}
          onChange={(event) => { setTargetDisease(event.target.value); setRiskResult(null); clearAiGuidance(); setError(""); }}
        >
          <option value="Mosaic"><LocalText source="Mosaic" /></option>
          <option value="RedRot"><LocalText source="Red rot" /></option>
          <option value="Rust"><LocalText source="Rust" /></option>
          <option value="Yellow"><LocalText source="Yellow leaf" /></option>
          <option value="Wilt"><LocalText source="Wilt" /></option>
        </select>

        <label className="field-label" htmlFor="risk-grass-age">
          <LocalText source="Grass age (Crop stage)" />
        </label>
        <select
          id="risk-grass-age"
          className="text-input"
          value={grassAge}
          onChange={(event) => { setGrassAge(event.target.value); setRiskResult(null); clearAiGuidance(); setError(""); }}
        >
          <option value="30 days (1 Month - Germination / Sprouting)">
            {localizedText(language, "30 days (1 Month - Germination / Sprouting)", "30 நாட்கள் (1 மாதம் - முளைப்பு நிலை)")}
          </option>
          <option value="60 days (2 Months - Early Tillering)">
            {localizedText(language, "60 days (2 Months - Early Tillering)", "60 நாட்கள் (2 மாதம் - ஆரம்ப தூர்க்கட்டும் நிலை)")}
          </option>
          <option value="90 days (3 Months - Tillering)">
            {localizedText(language, "90 days (3 Months - Tillering)", "90 நாட்கள் (3 மாதம் - தூர்க்கட்டும் நிலை)")}
          </option>
          <option value="120 days (4 Months - Late Tillering)">
            {localizedText(language, "120 days (4 Months - Late Tillering)", "120 நாட்கள் (4 மாதம் - தீவிர தூர்க்கட்டு)")}
          </option>
          <option value="180 days (6 Months - Grand Growth)">
            {localizedText(language, "180 days (6 Months - Grand Growth)", "180 நாட்கள் (6 மாதம் - தீவிர வளர்ச்சி நிலை)")}
          </option>
          <option value="240 days (8 Months - Stalk Elongation)">
            {localizedText(language, "240 days (8 Months - Stalk Elongation)", "240 நாட்கள் (8 மாதம் - தண்டு வளர்ச்சி நிலை)")}
          </option>
          <option value="300 days (10 Months - Early Maturity)">
            {localizedText(language, "300 days (10 Months - Early Maturity)", "300 நாட்கள் (10 மாதம் - ஆரம்ப முதிர்ச்சி நிலை)")}
          </option>
          <option value="360 days (12 Months - Harvest Maturity)">
            {localizedText(language, "360 days (12 Months - Harvest Maturity)", "360 நாட்கள் (12 மாதம் - அறுவடை நிலை)")}
          </option>
          <option value="Ratoon Crop (1st-2nd Ratoon)">
            {localizedText(language, "Ratoon Crop (1st-2nd Ratoon)", "மறுதாம்பு பயிர் (Ratoon)")}
          </option>
        </select>"""

content = content.replace(dropdown_old, dropdown_new, 1)

# 5. Display Grass Age AI guidance in Risk Result Card
shap_old = """          <div className="shap-list">
            <strong style={{ fontSize: "12px", color: "#475569", textTransform: "uppercase" }}>{t.primaryDrivers}</strong>"""

shap_new = """          {riskResult.age_ai_guidance && (
            <div className="model-notice" style={{ marginBottom: "14px", background: "#f0fdf4", borderColor: "#86efac", color: "#14532d" }}>
              <ShieldCheck />
              <div>
                <strong>{localizedText(language, "Grass Age & Physiological Advisory (Gemini AI)", "பயிர் வயது மற்றும் உடலியல் வழிகாட்டல் (Gemini AI)")}</strong>
                <p style={{ margin: "4px 0", fontSize: "13px", lineHeight: "1.5" }}>{riskResult.age_ai_guidance}</p>
                <small style={{ color: "#166534", fontWeight: "600" }}>
                  {localizedText(language, "Evaluated Cane Age: ", "மதிப்பிடப்பட்ட பயிர் வயது: ")}{riskResult.grass_age}
                </small>
              </div>
            </div>
          )}

          <div className="shap-list">
            <strong style={{ fontSize: "12px", color: "#475569", textTransform: "uppercase" }}>{t.primaryDrivers}</strong>"""

content = content.replace(shap_old, shap_new, 1)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Updated frontend/src/App.tsx successfully.")

