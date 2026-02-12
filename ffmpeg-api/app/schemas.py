from pydantic import BaseModel, Field, model_validator
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


class MuxRequest(BaseModel):
    """Mux one video and one audio. Use either local filenames or URLs, not both."""
    video: Optional[str] = None
    audio: Optional[str] = None
    output: Optional[str] = None
    video_url: Optional[str] = None
    audio_url: Optional[str] = None
    output_spaces: Optional[SpacesObjectRef] = None

    @model_validator(mode="after")
    def exactly_one_mode(self):
        local = all(
            self.video is not None,
            self.audio is not None,
            self.output is not None,
        )
        url = all(
            self.video_url is not None,
            self.audio_url is not None,
            self.output_spaces is not None,
        )
        if local and not url:
            return self
        if url and not local:
            return self
        raise ValueError(
            "Use either (video, audio, output) for local files or "
            "(video_url, audio_url, output_spaces) for URLs; do not mix."
        )


class MuxSpacesResponse(BaseModel):
    """Response for mux when using URL mode (output uploaded to Spaces)."""
    status: str = "ok"
    output_key: str
    output_url: Optional[str]
