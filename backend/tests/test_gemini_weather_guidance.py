import json
from datetime import datetime, timezone

import httpx
import pytest

import app.services.gemini_weather_guidance as guidance_service


def test_generate_weather_guidance_sends_observation_and_validates_json(monkeypatch):
    request_data = {}

    class MockResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "candidates": [{
                    "content": {
                        "parts": [{
                            "text": json.dumps({
                                "risk_level": "moderate",
                                "risk_reason": "Warm humid weather may favor monitoring for red rot.",
                                "summary": "Check the crop after humid weather.",
                                "weather_effect": "Humidity is 84.5%.",
                                "actions": ["Walk the field and scout."],
                                "watch_for": ["Unusual leaf changes."],
                                "limitations": "Weather alone does not confirm disease.",
                            })
                        }]
                    }
                }]
            }

    class MockClient:
        def __init__(self, **kwargs):
            request_data["timeout"] = kwargs["timeout"]

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def post(self, url, *, headers, json):
            request_data.update({"url": url, "headers": headers, "body": json})
            return MockResponse()

    monkeypatch.setattr(guidance_service.httpx, "Client", MockClient)
    result = guidance_service.generate_weather_guidance(
        api_key="test-key",
        model="gemini-test",
        language_code="ta",
        disease_class="RedRot",
        observed_at=datetime(2026, 10, 31, 4, 0, tzinfo=timezone.utc),
        freshness="current",
        weather={
            "temperature_c": 29.5,
            "relative_humidity_pct": 84.5,
            "dew_point_c": 25.8,
            "rainfall_mm": 5.0,
            "wind_speed_kmh": 6.0,
        },
        location={"latitude": 10.5, "longitude": 78.2},
        recent_weather={
            "provider": "Open-Meteo",
            "available_days": 7,
            "days": [{"date": "2026-10-30", "mean_relative_humidity_pct": 84.0}],
        },
        crop_variety="Co 86032",
        growth_stage="Tillering",
        soil_ph=6.4,
        knowledge={
            "display_name": "Red Rot",
            "symptoms": "Reddish leaf lesions.",
            "monitoring_guidance": "Inspect the midrib during humid weather.",
            "preventive_guidance": "Use certified seed setts and treat them at 52°C for 30 minutes.",
            "management_guidance": "Apply fungicide.",
        },
    )

    assert request_data["url"].endswith("/models/gemini-test:generateContent")
    assert "?" not in request_data["url"]
    assert request_data["headers"] == {"x-goog-api-key": "test-key"}
    assert request_data["timeout"].read == 45.0
    assert request_data["timeout"].connect == 10.0
    assert request_data["body"]["generationConfig"]["responseMimeType"] == "application/json"
    assert request_data["body"]["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "LOW"}
    prompt = request_data["body"]["contents"][0]["parts"][0]["text"]
    assert "Tamil" in prompt
    assert "using its native writing system" in prompt
    assert "For Tamil, use Tamil script" in prompt
    assert "The selected disease is authoritative" in prompt
    assert "actions relevant to the risk_reason" in prompt
    assert "Prevention or management checklists are not weather analysis" in prompt
    assert '"display_name": "Red Rot"' in prompt
    assert '"monitoring_guidance": "Inspect the midrib during humid weather."' in prompt
    assert "52°C" not in prompt
    assert "certified seed setts" not in prompt
    assert "Apply fungicide" not in prompt
    assert '"relative_humidity_pct": 84.5' in prompt
    assert '"disease": "RedRot"' in prompt
    assert '"crop_variety": "Co 86032"' in prompt
    assert '"growth_stage": "Tillering"' in prompt
    assert '"latitude": 10.5' in prompt
    assert '"longitude": 78.2' in prompt
    assert '"available_days": 7' in prompt
    assert "Do not claim the disease is present" in prompt
    assert "Do not recommend pesticides" in prompt
    assert "farm_gps_coordinates" in prompt
    assert result["actions"] == ["Walk the field and scout."]


def test_prompt_only_includes_selected_disease_context_and_not_red_rot_prevention():
    prompt = guidance_service._prompt(
        language="Tamil",
        disease_class="Rust",
        observed_at=datetime(2026, 10, 31, 4, 0, tzinfo=timezone.utc),
        freshness="current",
        weather={"temperature_c": 24.0, "relative_humidity_pct": 80.0},
        location={"latitude": 10.5, "longitude": 78.2},
        recent_weather={
            "available_days": 7,
            "days": [{
                "date": "2026-10-30",
                "mean_temperature_c": 24.0,
                "mean_relative_humidity_pct": 80.0,
                "hours_relative_humidity_at_least_80_pct": 12,
                "total_precipitation_mm": 4.0,
            }],
        },
        crop_variety="Co 86032",
        growth_stage="Tillering",
        soil_ph=6.4,
        knowledge={
            "display_name": "Sugarcane Rust",
            "symptoms": "Orange-brown pustules on leaves.",
            "monitoring_guidance": "Inspect lower and middle canopy leaves.",
            "preventive_guidance": "For Red Rot, treat seed setts at 52°C.",
        },
    )

    assert '"disease": "Rust"' in prompt
    assert '"display_name": "Sugarcane Rust"' in prompt
    assert "Orange-brown pustules on leaves." in prompt
    assert "For Red Rot" not in prompt
    assert "52°C" not in prompt


def test_generate_weather_guidance_rejects_malformed_provider_content(monkeypatch):
    class MockResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "not json"}]}}]}

    class MockClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def post(self, *args, **kwargs):
            return MockResponse()

    monkeypatch.setattr(guidance_service.httpx, "Client", MockClient)

    try:
        guidance_service.generate_weather_guidance(
            api_key="test-key",
            model="gemini-test",
            language_code="en",
            disease_class="Rust",
            observed_at=datetime(2026, 10, 31, 4, 0, tzinfo=timezone.utc),
            freshness="cached",
            weather={"temperature_c": 25.0},
            location={"latitude": 10.5, "longitude": 78.2},
            recent_weather={"available_days": 0, "days": []},
            crop_variety=None,
            growth_stage=None,
            soil_ph=None,
            knowledge={},
        )
    except guidance_service.WeatherGuidanceError as exc:
        assert exc.code == "invalid_response"
    else:
        raise AssertionError("Malformed Gemini output should not be accepted.")


@pytest.mark.parametrize("status_code", [400, 401, 403, 404, 429, 500, 503])
def test_generate_weather_guidance_preserves_provider_http_status(monkeypatch, status_code):
    class MockResponse:
        def raise_for_status(self):
            request = httpx.Request("POST", "https://generativelanguage.googleapis.com/")
            response = httpx.Response(
                status_code,
                request=request,
                json={"error": {"message": "provider rejected test-key"}},
            )
            response.raise_for_status()

    class MockClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def post(self, *args, **kwargs):
            return MockResponse()

    monkeypatch.setattr(guidance_service.httpx, "Client", MockClient)

    with pytest.raises(guidance_service.WeatherGuidanceError) as error:
        guidance_service.generate_weather_guidance(
            api_key="test-key",
            model="gemini-test",
            language_code="en",
            disease_class="Rust",
            observed_at=datetime(2026, 10, 31, 4, 0, tzinfo=timezone.utc),
            freshness="current",
            weather={"temperature_c": 25.0},
            location={"latitude": 10.5, "longitude": 78.2},
            recent_weather={"available_days": 0, "days": []},
            crop_variety=None,
            growth_stage=None,
            soil_ph=None,
            knowledge={},
        )

    assert error.value.provider_status_code == status_code
    assert error.value.provider_message == "provider rejected [redacted]"
    assert "test-key" not in error.value.provider_message
