path = "backend/app/services/gemini_weather_guidance.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Pass grass_age in generate_weather_guidance
old_prompt_call = """            soil_ph=soil_ph,
            knowledge=knowledge,
        )}]}],"""

new_prompt_call = """            soil_ph=soil_ph,
            knowledge=knowledge,
            grass_age=grass_age,
        )}]}],"""

content = content.replace(old_prompt_call, new_prompt_call, 1)

# 2. Add fallback model logic
old_request_logic = """    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    request_body = {
        "contents": [{"parts": [{"text": _prompt(
            language=language,
            disease_class=disease_class,
            observed_at=observed_at,
            freshness=freshness,
            weather=weather,
            location=location,
            recent_weather=recent_weather,
            crop_variety=crop_variety,
            growth_stage=growth_stage,
            soil_ph=soil_ph,
            knowledge=knowledge,
            grass_age=grass_age,
        )}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": RESPONSE_SCHEMA,
            "temperature": 0.2,
            "maxOutputTokens": 800,
            "thinkingConfig": {"thinkingLevel": "LOW"},
        },
    }
    try:
        with httpx.Client(timeout=httpx.Timeout(45.0, connect=10.0)) as client:
            response = client.post(url, headers={"x-goog-api-key": api_key}, json=request_body)
            response.raise_for_status()
            payload = response.json()
    except httpx.TimeoutException:
        raise WeatherGuidanceError("provider_timeout") from None
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        error_code = "provider_rate_limited" if status_code == 429 else "provider_unavailable"
        try:
            error_payload = exc.response.json()
        except ValueError:
            error_payload = {}
        provider_message = (
            error_payload.get("error", {}).get("message")
            if isinstance(error_payload, dict) and isinstance(error_payload.get("error"), dict)
            else None
        )
        if isinstance(provider_message, str):
            provider_message = provider_message.replace(api_key, "[redacted]")[:300]
        else:
            provider_message = None
        raise WeatherGuidanceError(
            error_code,
            provider_status_code=status_code,
            provider_message=provider_message,
        ) from None
    except Exception:
        raise WeatherGuidanceError("provider_unavailable") from None"""

new_request_logic = """    models_to_try = [model]
    for fallback in ["gemini-3.5-flash-lite", "gemini-3.5-flash"]:
        if fallback not in models_to_try:
            models_to_try.append(fallback)

    payload = None
    last_exc = None
    for attempt_model in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{attempt_model}:generateContent"
        request_body = {
            "contents": [{"parts": [{"text": _prompt(
                language=language,
                disease_class=disease_class,
                observed_at=observed_at,
                freshness=freshness,
                weather=weather,
                location=location,
                recent_weather=recent_weather,
                crop_variety=crop_variety,
                growth_stage=growth_stage,
                soil_ph=soil_ph,
                knowledge=knowledge,
                grass_age=grass_age,
            )}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": RESPONSE_SCHEMA,
                "temperature": 0.2,
                "maxOutputTokens": 800,
                "thinkingConfig": {"thinkingLevel": "LOW"},
            },
        }
        try:
            with httpx.Client(timeout=httpx.Timeout(25.0, connect=8.0)) as client:
                response = client.post(url, headers={"x-goog-api-key": api_key}, json=request_body)
                response.raise_for_status()
                payload = response.json()
                model = attempt_model
                break
        except (httpx.TimeoutException, httpx.HTTPStatusError, Exception) as exc:
            last_exc = exc
            continue

    if payload is None:
        if isinstance(last_exc, httpx.TimeoutException):
            raise WeatherGuidanceError("provider_timeout") from None
        if isinstance(last_exc, httpx.HTTPStatusError):
            status_code = last_exc.response.status_code
            error_code = "provider_rate_limited" if status_code == 429 else "provider_unavailable"
            raise WeatherGuidanceError(error_code, provider_status_code=status_code, provider_message="High demand spike, retrying...") from None
        raise WeatherGuidanceError("provider_unavailable") from None"""

content = content.replace(old_request_logic, new_request_logic, 1)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Updated fallback and prompt call in gemini_weather_guidance.py")

