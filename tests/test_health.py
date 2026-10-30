def test_health_check(sync_client):
    response = sync_client.get("/api/v1/health")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["code"] == "SUCCESS"
    assert json_data["data"]["status"] == "UP"


def test_readiness_check(sync_client):
    response = sync_client.get("/api/v1/health/ready")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["code"] == "SUCCESS"
    assert json_data["data"]["database"] == "HEALTHY"


def test_response_codes_registry(sync_client):
    response = sync_client.get("/api/v1/health/response-codes")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["code"] == "SUCCESS"
    assert isinstance(json_data["data"], list)
    codes = {item["code"] for item in json_data["data"]}
    assert "SUCCESS" in codes
    assert "UNAUTHORIZED" in codes
