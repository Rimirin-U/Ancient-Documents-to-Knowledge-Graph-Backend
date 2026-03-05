import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.normalizer import normalize_date, normalize_currency
from app.core.corrector import detect_ocr_conflicts

client = TestClient(app)

def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert "Welcome" in response.json()["message"]

def test_normalize_date():
    response = client.post("/api/v1/normalize/date", json={"date_str": "光绪三年八月"})
    assert response.status_code == 200
    data = response.json()
    assert data["normalized"] == "1877-08-01"

def test_normalize_currency():
    response = client.post("/api/v1/normalize/currency", json={"amount_str": "纹银五十两"})
    assert response.status_code == 200
    data = response.json()
    assert "RMB" in data["normalized"]

def test_correction():
    response = client.post("/api/v1/correct", json={"text": "绝买"})
    # Currently detect_ocr_conflicts is heuristic and might return empty if context is weak
    # But let's check response structure
    assert response.status_code == 200
    data = response.json()
    assert "ocr_corrections" in data

def test_parse_mock():
    # Test with a mock input
    response = client.post("/api/v1/parse", json={"text": "Test input text"})
    assert response.status_code == 200
    data = response.json()
    assert "parsed_data" in data
    assert data["parsed_data"]["extracted_entities"]["date"]["text"] == "光绪三年八月" # From Mock Service

def test_unit_normalizer():
    _, norm, _ = normalize_date("嘉庆五年三月十二日")
    assert norm == "1800-03-12"

def test_unit_currency():
    _, norm, _ = normalize_currency("纹银一两")
    assert "750.00" in norm
