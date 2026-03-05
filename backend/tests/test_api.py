"""
Tests cho FastAPI backend — target coverage > 80%

Chạy:
    pytest tests/ -v --cov=app --cov-report=term-missing
"""
import pytest
import httpx
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock, MagicMock

from app.main import app
from app.core import auth
from app.core.config import settings
from app.services import kserve as kserve_module

# ── Setup: override valid keys cho toàn bộ test session ─────────────────────

VALID_KEY   = "sk-test-valid-key"
INVALID_KEY = "sk-invalid-key"

MOCK_PROFILES = [
    {
        "Patient_ID": "N/A",
        "Name": "Nguyễn Văn A",
        "Age": "35",
        "Gender": "N/A",
        "Location": "Cầu Giấy, Hà Nội",
        "Symptoms_Diseases": "N/A",
    }
]

@pytest.fixture(autouse=True)
def override_settings():
    """Patch settings cho mỗi test — không phụ thuộc vào .env"""
    original_keys = settings.VALID_API_KEYS
    settings.VALID_API_KEYS = VALID_KEY
    yield
    settings.VALID_API_KEYS = original_keys


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


# ════════════════════════════════════════════════════════════════════════════
# Health
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_health_ok(client):
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "version": "1.0.0"}


# ════════════════════════════════════════════════════════════════════════════
# Auth middleware — auth.py
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_missing_api_key_returns_401(client):
    resp = await client.post("/predict", json={"text": "test"})
    assert resp.status_code == 401
    assert "Missing" in resp.json()["detail"]["error"]


@pytest.mark.anyio
async def test_invalid_api_key_returns_403(client):
    resp = await client.post(
        "/predict",
        json={"text": "test"},
        headers={"X-API-Key": INVALID_KEY},
    )
    assert resp.status_code == 403
    assert "Invalid" in resp.json()["detail"]["error"]


@pytest.mark.anyio
async def test_valid_api_key_passes_auth(client):
    with patch("app.api.predict.call_kserve", new=AsyncMock(return_value=MOCK_PROFILES)):
        resp = await client.post(
            "/predict",
            json={"text": "Bệnh nhân test"},
            headers={"X-API-Key": VALID_KEY},
        )
    assert resp.status_code == 200


# ════════════════════════════════════════════════════════════════════════════
# Predict endpoint — predict.py
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_predict_returns_profiles(client):
    with patch("app.api.predict.call_kserve", new=AsyncMock(return_value=MOCK_PROFILES)):
        resp = await client.post(
            "/predict",
            json={"text": "Bệnh nhân Nguyễn Văn A, 35 tuổi, Cầu Giấy, Hà Nội."},
            headers={"X-API-Key": VALID_KEY},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "profiles" in data
    assert data["profiles"][0]["Name"] == "Nguyễn Văn A"
    assert data["profiles"][0]["Age"] == "35"


@pytest.mark.anyio
async def test_predict_empty_text_returns_422(client):
    resp = await client.post(
        "/predict",
        json={"text": ""},
        headers={"X-API-Key": VALID_KEY},
    )
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_predict_missing_text_returns_422(client):
    resp = await client.post(
        "/predict",
        json={},
        headers={"X-API-Key": VALID_KEY},
    )
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_predict_text_too_long_returns_422(client):
    resp = await client.post(
        "/predict",
        json={"text": "a" * 10_001},
        headers={"X-API-Key": VALID_KEY},
    )
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_predict_kserve_timeout_returns_504(client):
    from fastapi import HTTPException
    with patch(
        "app.api.predict.call_kserve",
        new=AsyncMock(side_effect=HTTPException(status_code=504, detail={"error": "timeout"})),
    ):
        resp = await client.post(
            "/predict",
            json={"text": "test text"},
            headers={"X-API-Key": VALID_KEY},
        )
    assert resp.status_code == 504


@pytest.mark.anyio
async def test_predict_kserve_502_returns_502(client):
    from fastapi import HTTPException
    with patch(
        "app.api.predict.call_kserve",
        new=AsyncMock(side_effect=HTTPException(status_code=502, detail={"error": "bad gateway"})),
    ):
        resp = await client.post(
            "/predict",
            json={"text": "test text"},
            headers={"X-API-Key": VALID_KEY},
        )
    assert resp.status_code == 502


# ════════════════════════════════════════════════════════════════════════════
# KServe service — kserve.py
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_call_kserve_success_profiles():
    """KServe trả về {"profiles": [...]}"""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"profiles": MOCK_PROFILES}

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)):
        result = await kserve_module.call_kserve("test text", "sk-test-key")
    assert result == MOCK_PROFILES


@pytest.mark.anyio
async def test_call_kserve_success_predictions():
    """KServe trả về {"predictions": [...]} — fallback key"""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"predictions": MOCK_PROFILES}

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)):
        result = await kserve_module.call_kserve("test text", "sk-test-key")
    assert result == MOCK_PROFILES


@pytest.mark.anyio
async def test_call_kserve_empty_response():
    """KServe trả về response không có profiles/predictions"""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {}

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)):
        result = await kserve_module.call_kserve("test text", "sk-test-key")
    assert result == []


@pytest.mark.anyio
async def test_call_kserve_timeout_raises_504():
    with patch(
        "httpx.AsyncClient.post",
        new=AsyncMock(side_effect=httpx.TimeoutException("timeout")),
    ):
        with pytest.raises(Exception) as exc_info:
            await kserve_module.call_kserve("test text", "sk-test-key")
    assert exc_info.value.status_code == 504


@pytest.mark.anyio
async def test_call_kserve_request_error_raises_502():
    with patch(
        "httpx.AsyncClient.post",
        new=AsyncMock(side_effect=httpx.RequestError("connection refused")),
    ):
        with pytest.raises(Exception) as exc_info:
            await kserve_module.call_kserve("test text", "sk-test-key")
    assert exc_info.value.status_code == 502


@pytest.mark.anyio
async def test_call_kserve_non_200_raises_502():
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.text = "<html>403 Forbidden</html>"

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)):
        with pytest.raises(Exception) as exc_info:
            await kserve_module.call_kserve("test text", "sk-test-key")
    assert exc_info.value.status_code == 502
    assert "403" in exc_info.value.detail["error"]


# ════════════════════════════════════════════════════════════════════════════
# Config — valid_keys_set property
# ════════════════════════════════════════════════════════════════════════════

def test_valid_keys_set_comma_separated():
    settings.VALID_API_KEYS = "key1,key2,key3"
    assert settings.valid_keys_set == {"key1", "key2", "key3"}


def test_valid_keys_set_newline_separated():
    settings.VALID_API_KEYS = "key1\nkey2\nkey3"
    assert settings.valid_keys_set == {"key1", "key2", "key3"}


def test_valid_keys_set_strips_whitespace():
    settings.VALID_API_KEYS = "  key1  ,  key2  "
    assert settings.valid_keys_set == {"key1", "key2"}


def test_valid_keys_set_empty():
    settings.VALID_API_KEYS = ""
    assert settings.valid_keys_set == set()