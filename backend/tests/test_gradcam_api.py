def test_gradcam_heatmap_generation_and_retrieval(client):
    from backend.tests.test_api import register
    register(client, "gradcam_tester@example.com")
    
    with open("datasets/mendeley_v1/Sugarcane Leaf Disease Dataset/Healthy/healthy (1).jpeg", "rb") as f:
        img_bytes = f.read()
        
    response = client.post(
        "/api/v1/diagnosis/predict",
        files={"file": ("healthy_leaf.jpg", img_bytes, "image/jpeg")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["predicted_class"] == "Healthy"
    assert "heatmap_base64" in data
    assert len(data["heatmap_base64"]) > 1000
    assert "explanation" in data
    
    # Check diagnosis history
    history = client.get("/api/v1/diagnosis/history").json()
    assert len(history) > 0
    diagnosis_id = history[0]["id"]
    
    # Query GET /diagnosis/{diagnosis_id}/heatmap
    heatmap_resp = client.get(f"/api/v1/diagnosis/{diagnosis_id}/heatmap")
    assert heatmap_resp.status_code == 200
    assert heatmap_resp.headers["content-type"] == "image/jpeg"
    assert len(heatmap_resp.content) > 1000

