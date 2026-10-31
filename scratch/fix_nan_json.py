path = "backend/app/services/verified_risk_predictor.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

target = """    return {
        "status": "experimental_observation_time_association",
        "disease_class": disease_class,
        "disease_presence_score": round(score, 5),
        "score_note": "Uncalibrated model score for disease presence at observation time; not a future forecast or diagnosis.",
        "primary_drivers": drivers[:5],
        "input_features": row,"""

replacement = """    output_features = {
        feature: None if (feature_values[feature] is None or np.isnan(feature_values[feature]))
        else round(float(feature_values[feature]), 3)
        for feature in FEATURES
    }

    return {
        "status": "experimental_observation_time_association",
        "disease_class": disease_class,
        "disease_presence_score": round(score, 5),
        "score_note": "Uncalibrated model score for disease presence at observation time; not a future forecast or diagnosis.",
        "primary_drivers": drivers[:5],
        "input_features": output_features,"""

content = content.replace(target, replacement, 1)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Updated verified_risk_predictor.py input_features serialization successfully.")

