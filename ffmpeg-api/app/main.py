from fastapi import FastAPI, Depends
from app.auth import verify_api_key
from app.schemas import (
    ConcatRequest, TrimRequest, ScaleRequest, CropRequest,
    RotateRequest, AudioRequest, OverlayRequest, WatermarkRequest,
    EncodeRequest, SuccessResponse, ErrorResponse,
    InstructionsResponse, EndpointInfo, LogsResponse
)
from app.ffmpeg import (
    build_concat_command, build_trim_command, build_scale_command,
    build_crop_command, build_rotate_command, build_audio_command,
    build_overlay_command, build_watermark_command, build_encode_command
)
from app.docker_exec import execute_ffmpeg_command, extract_input_files
from app.logger import get_sanitized_logs


app = FastAPI(title="FFmpeg API", version="1.0.0")


@app.get("/api/instructions", response_model=InstructionsResponse)
async def get_instructions(api_key: str = Depends(verify_api_key)):
    """
    Get API documentation for all endpoints.
    Returns instructions for using the FFmpeg API including all available endpoints.
    """
    endpoints = [
        EndpointInfo(
            name="concat",
            method="POST",
            path="/api/ffmpeg/concat",
            description="Concatenate multiple video files into one",
            request_body={
                "inputs": ["a.mp4", "b.mp4"],
                "output": "out.mp4"
            },
            success_response={"status": "ok", "output": "out.mp4"},
            error_response={"status": "error", "message": "Error description"}
        ),
        EndpointInfo(
            name="trim",
            method="POST",
            path="/api/ffmpeg/trim",
            description="Trim video by start/end time or duration",
            request_body={
                "input": "video.mp4",
                "output": "trimmed.mp4",
                "start": 10.5,
                "end": 30.0
            },
            success_response={"status": "ok", "output": "trimmed.mp4"},
            error_response={"status": "error", "message": "Error description"}
        ),
        EndpointInfo(
            name="scale",
            method="POST",
            path="/api/ffmpeg/scale",
            description="Scale video to specified size",
            request_body={
                "input": "video.mp4",
                "output": "scaled.mp4",
                "size": "1280x720",
                "aspect_ratio": False
            },
            success_response={"status": "ok", "output": "scaled.mp4"},
            error_response={"status": "error", "message": "Error description"}
        ),
        EndpointInfo(
            name="crop",
            method="POST",
            path="/api/ffmpeg/crop",
            description="Crop video to specified rectangle",
            request_body={
                "input": "video.mp4",
                "output": "cropped.mp4",
                "x": 0,
                "y": 0,
                "width": 640,
                "height": 480
            },
            success_response={"status": "ok", "output": "cropped.mp4"},
            error_response={"status": "error", "message": "Error description"}
        ),
        EndpointInfo(
            name="rotate",
            method="POST",
            path="/api/ffmpeg/rotate",
            description="Rotate video by specified angle (90, 180, 270)",
            request_body={
                "input": "video.mp4",
                "output": "rotated.mp4",
                "angle": 90
            },
            success_response={"status": "ok", "output": "rotated.mp4"},
            error_response={"status": "error", "message": "Error description"}
        ),
        EndpointInfo(
            name="audio",
            method="POST",
            path="/api/ffmpeg/audio",
            description="Process audio (mute or normalize)",
            request_body={
                "input": "video.mp4",
                "output": "muted.mp4",
                "action": "mute",
                "normalize": False
            },
            success_response={"status": "ok", "output": "muted.mp4"},
            error_response={"status": "error", "message": "Error description"}
        ),
        EndpointInfo(
            name="overlay",
            method="POST",
            path="/api/ffmpeg/overlay",
            description="Overlay one video on top of another",
            request_body={
                "base": "background.mp4",
                "overlay": "foreground.mp4",
                "output": "result.mp4",
                "x": 0,
                "y": 0
            },
            success_response={"status": "ok", "output": "result.mp4"},
            error_response={"status": "error", "message": "Error description"}
        ),
        EndpointInfo(
            name="watermark",
            method="POST",
            path="/api/ffmpeg/watermark",
            description="Add image watermark to video",
            request_body={
                "video": "input.mp4",
                "image": "logo.png",
                "output": "watermarked.mp4",
                "position": "top-right",
                "opacity": 0.8
            },
            success_response={"status": "ok", "output": "watermarked.mp4"},
            error_response={"status": "error", "message": "Error description"}
        ),
        EndpointInfo(
            name="encode",
            method="POST",
            path="/api/ffmpeg/encode",
            description="Encode/transcode video to different format or codec",
            request_body={
                "input": "video.mp4",
                "output": "encoded.webm",
                "format": "webm",
                "vcodec": "libvpx",
                "acodec": "libvorbis"
            },
            success_response={"status": "ok", "output": "encoded.webm"},
            error_response={"status": "error", "message": "Error description"}
        ),
        EndpointInfo(
            name="health",
            method="GET",
            path="/health",
            description="Unauthenticated health check for monitoring",
            request_body=None,
            success_response={"status": "healthy"},
            error_response=None
        )
    ]
    
    return InstructionsResponse(endpoints=endpoints)


@app.get("/api/logs", response_model=LogsResponse)
async def get_logs(
    lines: int = 200,
    api_key: str = Depends(verify_api_key)
):
    """
    Get recent operational logs for debugging.
    Returns the last N lines from the log file (default 200, max 1000).
    All sensitive data is redacted before returning.
    """
    # Validate and cap lines parameter
    if lines > 1000:
        lines = 1000
    if lines < 1:
        lines = 1
    
    # Get sanitized logs
    logs = get_sanitized_logs(lines)
    
    return LogsResponse(lines=len(logs), logs=logs)


@app.post("/api/ffmpeg/concat", response_model=SuccessResponse | ErrorResponse)
async def concat_videos(request: ConcatRequest, api_key: str = Depends(verify_api_key)):
    command = build_concat_command(request)
    input_files = request.inputs
    
    success, output, message = execute_ffmpeg_command(command, input_files)
    
    if success:
        return SuccessResponse(output=output)
    else:
        return ErrorResponse(message=message)


@app.post("/api/ffmpeg/trim", response_model=SuccessResponse | ErrorResponse)
async def trim_video(request: TrimRequest, api_key: str = Depends(verify_api_key)):
    command = build_trim_command(request)
    input_files = [request.input]
    
    success, output, message = execute_ffmpeg_command(command, input_files)
    
    if success:
        return SuccessResponse(output=output)
    else:
        return ErrorResponse(message=message)


@app.post("/api/ffmpeg/scale", response_model=SuccessResponse | ErrorResponse)
async def scale_video(request: ScaleRequest, api_key: str = Depends(verify_api_key)):
    command = build_scale_command(request)
    input_files = [request.input]
    
    success, output, message = execute_ffmpeg_command(command, input_files)
    
    if success:
        return SuccessResponse(output=output)
    else:
        return ErrorResponse(message=message)


@app.post("/api/ffmpeg/crop", response_model=SuccessResponse | ErrorResponse)
async def crop_video(request: CropRequest, api_key: str = Depends(verify_api_key)):
    command = build_crop_command(request)
    input_files = [request.input]
    
    success, output, message = execute_ffmpeg_command(command, input_files)
    
    if success:
        return SuccessResponse(output=output)
    else:
        return ErrorResponse(message=message)


@app.post("/api/ffmpeg/rotate", response_model=SuccessResponse | ErrorResponse)
async def rotate_video(request: RotateRequest, api_key: str = Depends(verify_api_key)):
    command = build_rotate_command(request)
    input_files = [request.input]
    
    success, output, message = execute_ffmpeg_command(command, input_files)
    
    if success:
        return SuccessResponse(output=output)
    else:
        return ErrorResponse(message=message)


@app.post("/api/ffmpeg/audio", response_model=SuccessResponse | ErrorResponse)
async def process_audio(request: AudioRequest, api_key: str = Depends(verify_api_key)):
    command = build_audio_command(request)
    input_files = [request.input]
    
    success, output, message = execute_ffmpeg_command(command, input_files)
    
    if success:
        return SuccessResponse(output=output)
    else:
        return ErrorResponse(message=message)


@app.post("/api/ffmpeg/overlay", response_model=SuccessResponse | ErrorResponse)
async def overlay_videos(request: OverlayRequest, api_key: str = Depends(verify_api_key)):
    command = build_overlay_command(request)
    input_files = [request.base, request.overlay]
    
    success, output, message = execute_ffmpeg_command(command, input_files)
    
    if success:
        return SuccessResponse(output=output)
    else:
        return ErrorResponse(message=message)


@app.post("/api/ffmpeg/watermark", response_model=SuccessResponse | ErrorResponse)
async def add_watermark(request: WatermarkRequest, api_key: str = Depends(verify_api_key)):
    command = build_watermark_command(request)
    input_files = [request.video, request.image]
    
    success, output, message = execute_ffmpeg_command(command, input_files)
    
    if success:
        return SuccessResponse(output=output)
    else:
        return ErrorResponse(message=message)


@app.post("/api/ffmpeg/encode", response_model=SuccessResponse | ErrorResponse)
async def encode_video(request: EncodeRequest, api_key: str = Depends(verify_api_key)):
    command = build_encode_command(request)
    input_files = [request.input]
    
    success, output, message = execute_ffmpeg_command(command, input_files)
    
    if success:
        return SuccessResponse(output=output)
    else:
        return ErrorResponse(message=message)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
