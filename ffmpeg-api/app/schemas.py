from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


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


class EndpointInfo(BaseModel):
    name: str
    method: str
    path: str
    description: str
    request_body: Optional[Dict[str, Any]]
    success_response: Dict[str, Any]
    error_response: Optional[Dict[str, Any]]


class InstructionsResponse(BaseModel):
    status: str = "ok"
    service: str = "ffmpeg-api"
    auth: Dict[str, str] = Field(default_factory=lambda: {"header": "X-Internal-API-Key"})
    endpoints: List[EndpointInfo]


class LogsResponse(BaseModel):
    status: str = "ok"
    lines: int
    logs: List[str]


class SpacesObjectRef(BaseModel):
    spaces_key: str


class ConcatSpacesRequest(BaseModel):
    inputs: List[SpacesObjectRef]
    output: SpacesObjectRef


class ConcatSpacesResponse(BaseModel):
    status: str = "ok"
    output_key: str
    output_url: Optional[str]
