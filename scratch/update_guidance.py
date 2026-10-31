import os
import re

path = r"backend/app/services/gemini_weather_guidance.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update _prompt signature
old_sig = """    growth_stage: str | None,
    soil_ph: float | None,
    knowledge: dict[str, str | None],
) -> str:"""

new_sig = """    growth_stage: str | None,
    soil_ph: float | None,
    knowledge: dict[str, str | None],
    grass_age: str | None = None,
) -> str:"""

content = content.replace(old_sig, new_sig, 1)

# 2. Update prompt_data inside _prompt
old_pdata = """    prompt_data = {
        "disease": disease_class,"""

new_pdata = """    prompt_data = {
        "disease": disease_class,
        "grass_age": grass_age,"""

content = content.replace(old_pdata, new_pdata, 1)

# 3. Add grass_age clause to prompt instructions
old_clause = '"Do not give Red Rot symptoms or prevention advice unless the selected disease is RedRot. "'
new_clause = '''"Do not give Red Rot symptoms or prevention advice unless the selected disease is RedRot. "
        + (f"CRITICALLY factor in the sugarcane Grass / Crop Age: '{grass_age}'. Disease vulnerability varies significantly across crop age: early tillering (0-90 days) is prone to Mosaic virus and fungal seedling rot; grand growth (120-240 days) is prone to Rust on dense green foliage; maturity/ripening (270-360+ days) is acutely susceptible to Red Rot (Colletotrichum falcatum) stalk pith destruction, sucrose inversion, and Wilt. Address how this specific grass age interacts with the ambient humidity and temperature in both your risk evaluation and field action checklist. " if grass_age else "")'''

content = content.replace(old_clause, new_clause, 1)

# 4. Update generate_weather_guidance signature
old_gen_sig = """    growth_stage: str | None,
    soil_ph: float | None,
    knowledge: dict[str, str | None],
) -> dict[str, Any]:"""

new_gen_sig = """    growth_stage: str | None,
    soil_ph: float | None,
    knowledge: dict[str, str | None],
    grass_age: str | None = None,
) -> dict[str, Any]:"""

content = content.replace(old_gen_sig, new_gen_sig, 1)

# 5. Update _prompt call inside generate_weather_guidance
old_call = """        crop_variety=crop_variety,
        growth_stage=growth_stage,
        soil_ph=soil_ph,
        knowledge=knowledge,
    )"""

new_call = """        crop_variety=crop_variety,
        growth_stage=growth_stage,
        soil_ph=soil_ph,
        knowledge=knowledge,
        grass_age=grass_age,
    )"""

content = content.replace(old_call, new_call, 1)

# 6. Add generate_risk_age_guidance
age_func = '''

def generate_risk_age_guidance(
    *,
    api_key: str,
    model: str,
    language_code: str,
    disease_class: str,
    grass_age: str,
    risk_score: float,
    primary_drivers: list[dict],
) -> str:
    """Generates a focused 2-3 sentence Gemini AI physiological advisory for Grass Age in Option 2."""
    if not api_key.strip():
        return ""
    lang_name = LANGUAGE_NAMES.get(language_code, "English")
    drivers_str = ", ".join(f"{d.get('feature')}: {d.get('value')} ({d.get('effect')})" for d in primary_drivers[:4])
    prompt = (
        f"Act as a Senior Sugarcane Agronomist and Pathologist. "
        f"Write strictly in {lang_name} (use native script). "
        f"A machine learning risk model computed a {round(risk_score * 100, 1)}% environmental disease-presence risk "
        f"for sugarcane {disease_class}. The sugarcane Grass/Crop Age is '{grass_age}'. "
        f"Key weather drivers: {drivers_str}. "
        f"In 2-3 concise, farmer-friendly sentences, explain how this specific Grass Age affects plant vulnerability "
        f"to {disease_class} under these weather conditions, and what immediate age-specific monitoring the farmer must take. "
        f"Do not recommend dangerous chemicals. Return only the plain text advice."
    )
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.2, "maxOutputTokens": 250}}
    try:
        with httpx.Client(timeout=httpx.Timeout(15.0, connect=5.0)) as client:
            resp = client.post(url, headers={"x-goog-api-key": api_key.strip(), "Content-Type": "application/json"}, json=body)
            if resp.status_code == 200:
                data = resp.json()
                parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                return "".join(p.get("text", "") for p in parts).strip()
    except Exception:
        pass
    return ""
'''
if "def generate_risk_age_guidance" not in content:
    content += age_func

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Updated gemini_weather_guidance.py successfully.")

