"""
Gọi KServe qua NGINX gateway với API Key.
"""
import httpx
from fastapi import HTTPException, status

from app.core.config import settings


async def call_kserve(text: str, api_key: str) -> list[dict]:
    """
    Gửi text đến KServe model, trả về danh sách medical profiles.
    """
    payload = {"instances": [text]}
    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json",
    }

    # Chỉ set Host header khi gọi qua IP/internal DNS (không phải domain thật)
    # Tránh conflict khi GATEWAY_URL đã là domain có TLS
    if not settings.GATEWAY_URL.startswith("https://api."):
        headers["Host"] = settings.GATEWAY_HOST

    url = f"{settings.GATEWAY_URL}{settings.KSERVE_PATH}"

    # verify=False: bỏ qua SSL check cho self-signed cert trong cluster
    # An toàn vì traffic nội bộ cluster (không ra internet)
    async with httpx.AsyncClient(
        timeout=settings.KSERVE_TIMEOUT,
        verify=False,
    ) as client:
        try:
            resp = await client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail={"error": "KServe model timeout"},
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"error": f"Cannot reach KServe: {str(e)}"},
            )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": f"KServe returned {resp.status_code}", "body": resp.text},
        )

    data = resp.json()
    return data.get("profiles") or data.get("predictions") or []