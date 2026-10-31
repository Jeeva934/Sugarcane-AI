path = "backend/app/api/routes.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update import
content = content.replace(
    "from app.services.gemini_weather_guidance import WeatherGuidanceError, generate_weather_guidance",
    "from app.services.gemini_weather_guidance import WeatherGuidanceError, generate_weather_guidance, generate_risk_age_guidance"
)

# 2. Update analyze_weather_guidance call
old_guidance_call = """            crop_variety=farm.crop_variety,
            growth_stage=farm.growth_stage,
            soil_ph=farm.soil_ph,
            knowledge=knowledge,
        )"""

new_guidance_call = """            crop_variety=farm.crop_variety,
            growth_stage=farm.growth_stage,
            soil_ph=farm.soil_ph,
            knowledge=knowledge,
            grass_age=payload.grass_age,
        )"""

content = content.replace(old_guidance_call, new_guidance_call, 1)

# 3. Update predict_risk to call generate_risk_age_guidance
old_risk_return = """    result["id"] = record.id
    result["saved_to_history"] = True
    return result"""

new_risk_return = """    if payload.grass_age:
        result["grass_age"] = payload.grass_age
        try:
            age_text = await run_in_threadpool(
                generate_risk_age_guidance,
                api_key=settings.gemini_api_key.strip(),
                model=settings.gemini_model,
                language_code=user.preferred_language or "en",
                disease_class=payload.disease_class,
                grass_age=payload.grass_age,
                risk_score=result["disease_presence_score"],
                primary_drivers=result.get("primary_drivers", []),
            )
            result["age_ai_guidance"] = age_text
        except Exception:
            result["age_ai_guidance"] = None

    result["id"] = record.id
    result["saved_to_history"] = True
    return result"""

content = content.replace(old_risk_return, new_risk_return, 1)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Updated backend/app/api/routes.py successfully.")

