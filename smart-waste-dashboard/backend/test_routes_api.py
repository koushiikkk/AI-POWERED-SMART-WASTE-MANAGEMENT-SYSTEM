import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from app.main import app

client = TestClient(app)

@patch("app.routers.routes.httpx.AsyncClient")
@patch("app.routers.routes.get_db_connection")
def test_optimize_route_success(mock_get_db, mock_async_client, monkeypatch):
    monkeypatch.setenv("ORS_API_KEY", "fake_key")
    
    # Mock DB
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    
    # Return 2 reports
    mock_cursor.fetchall.return_value = [
        (1, 48.47, 9.70, "HIGH", 0.9, "completed"),
        (2, 49.15, 9.20, "CRITICAL", 0.95, "completed")
    ]
    mock_cursor.description = [
        ("id",), ("latitude",), ("longitude",), ("severity",), ("confidence",), ("analysis_status",)
    ]
    
    # Mock HTTP responses
    mock_client_instance = MagicMock()
    mock_async_client.return_value.__aenter__.return_value = mock_client_instance
    
    # Mock POST response for Matrix
    class MockMatrixResponse:
        status_code = 200
        def json(self):
            return {
                "durations": [
                    [0, 600, 1200],
                    [600, 0, 800],
                    [1200, 800, 0]
                ]
            }
    
    # Mock POST response for Directions
    class MockDirectionsResponse:
        status_code = 200
        def json(self):
            return {
                "features": [{
                    "properties": {
                        "summary": {
                            "distance": 15000,
                            "duration": 900
                        }
                    },
                    "geometry": {
                        "coordinates": [[9.7, 48.4], [9.2, 49.1]]
                    }
                }]
            }

    # Set side effect to return Matrix then Directions
    async def mock_post(url, *args, **kwargs):
        if "matrix" in url:
            return MockMatrixResponse()
        if "directions" in url:
            return MockDirectionsResponse()
    
    mock_client_instance.post.side_effect = mock_post
    
    response = client.post("/api/routes/optimize", json={
        "start_lat": 48.0,
        "start_lng": 9.0,
        "report_ids": [1, 2]
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["total_distance_km"] == 15.0
    assert data["total_duration_minutes"] == 15.0
    assert len(data["stops"]) == 2
    assert "geometry" in data

def test_optimize_route_no_api_key(monkeypatch):
    monkeypatch.delenv("ORS_API_KEY", raising=False)
    
    response = client.post("/api/routes/optimize", json={
        "start_lat": 48.0,
        "start_lng": 9.0,
        "report_ids": [1]
    })
    
    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]
