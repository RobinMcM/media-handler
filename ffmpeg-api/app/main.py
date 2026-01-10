from fastapi import FastAPI, Depends
from app.auth import verify_api_key
from app.schemas import (
    ConcatRequest, TrimRequest, ScaleRequest, CropRequest,
    RotateRequest, AudioRequest, OverlayRequest, WatermarkRequest,
    EncodeRequest, SuccessResponse, ErrorResponse
)
from app.ffmpeg import (
    build_concat_command, build_trim_command, build_scale_command,
    build_crop_command, build_rotate_command, build_audio_command,
    build_overlay_command, build_watermark_command, build_encode_command
)
from app.docker_exec import execute_ffmpeg_command, extract_input_files


app = FastAPI(title="FFmpeg API", version="1.0.0")


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
