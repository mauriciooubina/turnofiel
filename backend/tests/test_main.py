def test_read_root(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "active"
    assert "Backend running successfully." in data["message"]

def test_health_check_is_public(anon_client):
    response = anon_client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"message": "Backend running successfully.", "status": "active"}
    assert anon_client.get("/api/auth/me").status_code == 401

def test_health_matches_root(client):
    health_res = client.get("/api/health")
    root_res = client.get("/")
    assert health_res.status_code == root_res.status_code
    assert health_res.json() == root_res.json()

def test_openapi_schema(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "Sistema de Predicción de Ausentismo"
    assert "/api/health" in schema["paths"]
    assert "/api/calendar" in schema["paths"]
    assert "/api/queues" in schema["paths"]
