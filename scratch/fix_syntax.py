path = "backend/app/services/gemini_weather_guidance.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Fix the return in _prompt
old_return = """    return (
        f"Write every user-facing field exclusively in {language}, using its native writing system. "
        f"Do not answer in English unless the requested language is English. For Tamil, use Tamil script. "
        f"Give a preliminary environmental risk screening for sugarcane and the exact selected disease "
        f"{disease_class}. The selected disease is authoritative; never substitute another disease. "
        "Do not give Red Rot symptoms or prevention advice unless the selected disease is RedRot. "
        + (f"CRITICALLY factor in the sugarcane Grass / Crop Age: '{grass_age}'. Disease vulnerability varies significantly across crop age: early tillering (0-90 days) is prone to Mosaic virus and fungal seedling rot; grand growth (120-240 days) is prone to Rust on dense green foliage; maturity/ripening (270-360+ days) is acutely susceptible to Red Rot (Colletotrichum falcatum) stalk pith destruction, sucrose inversion, and Wilt. Address how this specific grass age interacts with the ambient humidity and temperature in both your risk evaluation and field action checklist. " if grass_age else "")
        "The exact GPS coordinates are supplied only to identify the farm location. Do not infer \""""

new_return = """    age_clause = (
        f"CRITICALLY factor in the sugarcane Grass / Crop Age: '{grass_age}'. Disease vulnerability varies significantly across crop age: early tillering (0-90 days) is prone to Mosaic virus and fungal seedling rot; grand growth (120-240 days) is prone to Rust on dense green foliage; maturity/ripening (270-360+ days) is acutely susceptible to Red Rot (Colletotrichum falcatum) stalk pith destruction, sucrose inversion, and Wilt. Address how this specific grass age interacts with the ambient humidity and temperature in both your risk evaluation and field action checklist. "
        if grass_age else ""
    )
    return (
        f"Write every user-facing field exclusively in {language}, using its native writing system. "
        f"Do not answer in English unless the requested language is English. For Tamil, use Tamil script. "
        f"Give a preliminary environmental risk screening for sugarcane and the exact selected disease "
        f"{disease_class}. The selected disease is authoritative; never substitute another disease. "
        f"{age_clause}"
        "Do not give Red Rot symptoms or prevention advice unless the selected disease is RedRot. "
        "The exact GPS coordinates are supplied only to identify the farm location. Do not infer \""""

content = content.replace(old_return, new_return, 1)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Fixed syntax in gemini_weather_guidance.py.")

