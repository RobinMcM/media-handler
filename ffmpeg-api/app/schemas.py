from pydantic import BaseModel
from typing import List, Optional


class ConcatRequest(BaseModel):
    inputs: List[str]
    output: str


class TrimRequest(BaseModel):
    input: str
    output: str
    start: Optional[float] = None
    end: Optional[float] = None
    duration: Optional[float] = None


class ScaleRequest(BaseModel):
    input: str
    output: str
    size: str
    aspect_ratio: bool = False


class CropRequest(BaseModel):
    input: str
    output: str
    x: int
    y: int
    width: int
    height: int


class RotateRequest(BaseModel):
    input: str
    output: str
    angle: int


class AudioRequest(BaseModel):
    input: str
    output: str
    action: str
    normalize: bool = False


class OverlayRequest(BaseModel):
    base: str
    overlay: str
    output: str
    x: int = 0
    y: int = 0


class WatermarkRequest(BaseModel):
    video: str
    image: str
    output: str
    x: Optional[int] = None
    y: Optional[int] = None
    opacity: float = 1.0
    position: Optional[str] = None


class EncodeRequest(BaseModel):
    input: str
    output: str
    format: Optional[str] = None
    vcodec: Optional[str] = None
    acodec: Optional[str] = None


class SuccessResponse(BaseModel):
    status: str = "ok"
    output: str


class ErrorResponse(BaseModel):
    status: str = "error"
    message: str
