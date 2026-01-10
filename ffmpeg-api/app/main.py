from fastapi import FastAPI, Depends
from app.auth import verify_api_key
from app.schemas import (
    ConcatRequest, TrimRequest, ScaleRequest, CropRequest,
    RotateRequest, AudioRequest, OverlayRequest, WatermarkRequest,
    EncodeRequest, SuccessResponse, ErrorResponse,
    InstructionsResponse, EndpointInfo, LogsResponse,
    ConcatSpacesRequest, ConcatSpacesResponse
)
from app.ffmpeg import (
    build_concat_command, build_trim_command, build_scale_command,
    build_crop_command, build_rotate_command, build_audio_command,
    build_overlay_command, build_watermark_command, build_encode_command
)
from app.docker_exec import execute_ffmpeg_command, extract_input_files
from app.logger import get_sanitized_logs, log_request, log_success, log_error
from app.spaces import download_key_to_path, upload_path_to_key, get_public_url


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
        ),
        EndpointInfo(
            name="concat_spaces",
            method="POST",
            path="/api/ffmpeg/concat_spaces",
            description="Concatenate 2 or more videos from DigitalOcean Spaces",
            request_body={
                "inputs": [
                    {"spaces_key": "path/to/input1.mp4"},
                    {"spaces_key": "path/to/input2.mp4"},
                    {"spaces_key": "path/to/input3.mp4"}
                ],
                "output": {"spaces_key": "path/to/output.mp4"}
            },
            success_response={
                "status": "ok",
                "output_key": "path/to/output.mp4",
                "output_url": "https://bucket.region.digitaloceanspaces.com/path/to/output.mp4"
            },
            error_response={"status": "error", "message": "Error description"}
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


@app.post("/api/ffmpeg/concat_spaces", response_model=ConcatSpacesResponse | ErrorResponse)
async def concat_videos_from_spaces(
    request: ConcatSpacesRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    Concatenate two videos from DigitalOcean Spaces.
    Downloads inputs from Spaces, runs local concat, uploads result back to Spaces.
    """
    import uuid
    import shutil
    from pathlib import Path
    
    # Validation: at least 2 inputs required (no maximum limit)
    if len(request.inputs) < 2:
        return ErrorResponse(message="At least 2 inputs required for concat_spaces")
    
    # Validation: spaces_key cannot be empty, contain .., or start with /
    for inp in request.inputs:
        if not inp.spaces_key or not inp.spaces_key.strip():
            return ErrorResponse(message="Input spaces_key cannot be empty")
        if ".." in inp.spaces_key or inp.spaces_key.startswith("/"):
            return ErrorResponse(message="Invalid spaces_key: cannot contain '..' or start with '/'")
    
    if not request.output.spaces_key or not request.output.spaces_key.strip():
        return ErrorResponse(message="Output spaces_key cannot be empty")
    if ".." in request.output.spaces_key or request.output.spaces_key.startswith("/"):
        return ErrorResponse(message="Invalid output spaces_key: cannot contain '..' or start with '/'")
    
    # Validation: check video file extensions
    allowed_extensions = {".mp4", ".mov", ".m4v", ".webm"}
    for inp in request.inputs:
        ext = Path(inp.spaces_key).suffix.lower()
        if ext not in allowed_extensions:
            return ErrorResponse(message=f"Invalid input file extension: {ext}. Allowed: {', '.join(allowed_extensions)}")
    
    output_ext = Path(request.output.spaces_key).suffix.lower()
    if output_ext not in allowed_extensions:
        return ErrorResponse(message=f"Invalid output file extension: {output_ext}. Allowed: {', '.join(allowed_extensions)}")
    
    # Generate job ID and create temp directory
    job_id = str(uuid.uuid4())
    job_dir = Path("/tmp") / f"job-{job_id}"
    
    log_request("concat_spaces", job_id)
    
    try:
        job_dir.mkdir(parents=True, exist_ok=True)
        
        # Download inputs from Spaces
        local_inputs = []
        for i, inp in enumerate(request.inputs):
            # Use sequential filenames: input_0.mp4, input_1.mp4, etc. (supports any number)
            filename = f"input_{i}.mp4"
            local_path = job_dir / filename
            
            try:
                download_key_to_path(inp.spaces_key, str(local_path))
                local_inputs.append(filename)
            except Exception as e:
                log_error(job_id, f"Failed to download {inp.spaces_key}: {str(e)}")
                return ErrorResponse(message=f"Failed to download input from Spaces: {str(e)}")
        
        # Prepare output filename
        output_filename = "output.mp4"
        
        # Build concat command using existing builder
        from app.ffmpeg import build_concat_command
        from app.schemas import ConcatRequest as LocalConcatRequest
        
        local_concat_req = LocalConcatRequest(
            inputs=local_inputs,
            output=output_filename
        )
        command = build_concat_command(local_concat_req)
        
        # Execute FFmpeg via Docker (same as local concat endpoint)
        # We need to manually execute here to use the job_dir we created
        docker_cmd = [
            "docker", "run", "--rm",
            "-v", f"{job_dir}:/videos",
            "media-handler"
        ] + command
        
        import subprocess
        from app.logger import log_docker_command
        
        log_docker_command(job_id, docker_cmd)
        
        result = subprocess.run(
            docker_cmd,
            capture_output=True,
            text=True,
            timeout=3600
        )
        
        output_path = job_dir / output_filename
        
        # DEBUG: Log all files in job directory before validation
        import os
        import logging
        logger = logging.getLogger("ffmpeg-api")
        try:
            dir_contents = []
            for f in os.listdir(job_dir):
                fpath = job_dir / f
                fsize = os.path.getsize(fpath) if os.path.isfile(fpath) else 0
                dir_contents.append(f"{f} ({fsize} bytes)")
            logger.info(f"job={job_id} job_dir_contents={', '.join(dir_contents)}")
        except Exception as e:
            logger.warning(f"job={job_id} failed_to_list_dir error={str(e)}")
        
        # Validate FFmpeg execution
        if result.returncode != 0:
            error_msg = result.stderr or result.stdout or "Unknown error"
            log_error(job_id, error_msg)
            return ErrorResponse(message=f"FFmpeg concat failed: {error_msg[:200]}")
        
        if not output_path.exists():
            log_error(job_id, "Output file does not exist after FFmpeg execution")
            return ErrorResponse(message="Output file was not created by FFmpeg")
        
        # Validate output file size
        output_size = os.path.getsize(output_path)
        logger.info(f"job={job_id} output_path={str(output_path)} output_size={output_size}")
        
        if output_size == 0:
            log_error(job_id, f"Output file is empty (0 bytes). FFmpeg stderr: {result.stderr[:1000]}")
            return ErrorResponse(message="Output file is empty - concat may have failed silently")
        
        # Validate output has valid duration using ffprobe
        try:
            probe_result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration", 
                 "-of", "csv=p=0", str(output_path)],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            duration_str = probe_result.stdout.strip()
            duration = float(duration_str) if duration_str else 0.0
            logger.info(f"job={job_id} output_duration={duration}s")
            
            if duration < 0.1:
                log_error(job_id, f"Output duration is invalid: {duration}s. FFmpeg stderr: {result.stderr[:1000]}")
                return ErrorResponse(message=f"Output video has invalid duration ({duration}s) - concat failed")
        except Exception as e:
            logger.warning(f"job={job_id} ffprobe_validation_failed error={str(e)}")
            # Continue anyway - ffprobe might not be available or file might be valid
        
        # Upload result to Spaces
        try:
            upload_path_to_key(
                str(output_path),
                request.output.spaces_key,
                content_type="video/mp4"
            )
        except Exception as e:
            log_error(job_id, f"Failed to upload to Spaces: {str(e)}")
            return ErrorResponse(message=f"Failed to upload output to Spaces: {str(e)}")
        
        # Generate public URL if configured
        output_url = get_public_url(request.output.spaces_key)
        
        log_success(job_id, request.output.spaces_key)
        
        return ConcatSpacesResponse(
            output_key=request.output.spaces_key,
            output_url=output_url
        )
    
    except Exception as e:
        log_error(job_id, str(e))
        return ErrorResponse(message=f"Unexpected error: {str(e)}")
    
    finally:
        # Always cleanup job directory
        if job_dir.exists():
            shutil.rmtree(job_dir, ignore_errors=True)


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
