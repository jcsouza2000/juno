"""Smoke tests do endpoint de saúde e da raiz."""


def test_root_returns_ok(client):
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert "message" in body
    assert "JUNO" in body["message"]


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "online"
    assert body["features"]["auth"] is True
    assert body["features"]["rate_limit"] is True
