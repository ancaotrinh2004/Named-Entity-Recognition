from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.auth import require_api_key
from app.services.kserve import call_kserve

router = APIRouter()


class PredictRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=1,
        max_length=10_000,
        examples=["Bệnh nhân Nguyễn Văn A, 35 tuổi, trú tại Cầu Giấy, Hà Nội."],
    )


class PredictResponse(BaseModel):
    profiles: list[dict]


@router.post(
    "",
    response_model=PredictResponse,
    summary="Trích xuất thông tin y tế từ văn bản",
)
async def predict(
    body: PredictRequest,
    api_key: str = Depends(require_api_key),
):
    """
    Nhận văn bản tiếng Việt, trả về danh sách medical profiles (NER).

    **Headers yêu cầu:** `X-API-Key: <your-key>`
    """
    profiles = await call_kserve(body.text, api_key)
    return PredictResponse(profiles=profiles)