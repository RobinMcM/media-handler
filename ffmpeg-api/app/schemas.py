from pydantic import BaseModel, Field, model_validator
from typing import List, Optional, Dict, Any


class ConcatRequest(BaseModel):
    inputs: List[str]
    output: str  # filename for temp output (e.g. out.mp4)
    output_destination: Optional["OutputDestination"] = None


class TrimRequest(BaseModel):
    input: str
    output: str
    output_destination: Optional["OutputDestination"] = None
    start: Optional[float] = None
    end: Optional[float] = None
    duration: Optional[float] = None


class ScaleRequest(BaseModel):
    input: str
    output: str
    output_destination: Optional["OutputDestination"] = None
    size: str
    aspect_ratio: bool = False


class CropRequest(BaseModel):
    input: str
    output: str
    output_destination: Optional["OutputDestination"] = None
    x: int
    y: int
    width: int
    height: int


class RotateRequest(BaseModel):
    input: str
    output: str
    output_destination: Optional["OutputDestination"] = None
    angle: int


class AudioRequest(BaseModel):
    input: str
    output: str
    output_destination: Optional["OutputDestination"] = None
    action: str
    normalize: bool = False


class OverlayRequest(BaseModel):
    base: str
    overlay: str
    output: str
    output_destination: Optional["OutputDestination"] = None
    x: int = 0
    y: int = 0


class WatermarkRequest(BaseModel):
    video: str
    image: str
    output: str
    output_destination: Optional["OutputDestination"] = None
    x: Optional[int] = None
    y: Optional[int] = None
    opacity: float = 1.0
    position: Optional[str] = None


class EncodeRequest(BaseModel):
    input: str
    output: str
    output_destination: Optional["OutputDestination"] = None
    format: Optional[str] = None
    vcodec: Optional[str] = None
    acodec: Optional[str] = None


class ExtractFrameRequest(BaseModel):
    """Extract a single frame from a source video URL or Spaces key."""
    video_url: str
    position: str = "last"  # "last", "first", or seconds as string/number
    output_destination: Optional["OutputDestination"] = None


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


class OutputDestination(BaseModel):
    """Client-provided destination for job output. If absent, output is streamed in the response."""
    presigned_put_url: str


class ConcatSpacesRequest(BaseModel):
    inputs: List[SpacesObjectRef]
    output: Optional[SpacesObjectRef] = None  # deprecated: use output_destination
    output_destination: Optional[OutputDestination] = None


class ConcatSpacesResponse(BaseModel):
    status: str = "ok"
    output_key: str
    output_url: Optional[str]


class MuxRequest(BaseModel):
    """Mux one video and one audio. Use either local filenames or URLs, not both. Output: stream or output_destination."""
    video: Optional[str] = None
    audio: Optional[str] = None
    video_url: Optional[str] = None
    audio_url: Optional[str] = None
    output_destination: Optional[OutputDestination] = None

    @model_validator(mode="after")
    def exactly_one_mode(self):
        local = self.video is not None and self.audio is not None
        url = self.video_url is not None and self.audio_url is not None
        if local and not url:
            return self
        if url and not local:
            return self
        raise ValueError(
            "Use either (video, audio) for local files or (video_url, audio_url) for URLs; do not mix."
        )


class MuxSpacesResponse(BaseModel):
    """Response for mux when using URL mode (output uploaded to Spaces)."""
    status: str = "ok"
    output_key: str
    output_url: Optional[str]


class ExtractFrameResponse(BaseModel):
    status: str = "ok"
    image_url: Optional[str] = None
    image_data_url: Optional[str] = None


# Pydantic v2: resolve forward refs where OutputDestination is referenced
# before its class definition in this module.
ConcatRequest.model_rebuild()
TrimRequest.model_rebuild()
ScaleRequest.model_rebuild()
CropRequest.model_rebuild()
RotateRequest.model_rebuild()
AudioRequest.model_rebuild()
OverlayRequest.model_rebuild()
WatermarkRequest.model_rebuild()
EncodeRequest.model_rebuild()
ExtractFrameRequest.model_rebuild()
