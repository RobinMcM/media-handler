import shutil
from pathlib import Path

import httpx
from fastapi import FastAPI, Depends
from fastapi.responses import FileResponse, StreamingResponse

from app.auth import verify_api_key
from app.schemas import (
    ConcatRequest, TrimRequest, ScaleRequest, CropRequest,
    RotateRequest, AudioRequest, OverlayRequest, WatermarkRequest,
    EncodeRequest, SuccessResponse, ErrorResponse,
    InstructionsResponse, EndpointInfo, LogsResponse,
    ConcatSpacesRequest,
    MuxRequest,
    ExtractFrameRequest,
    ExtractFrameResponse,
)
from app.ffmpeg import (
    build_concat_command, build_trim_command, build_scale_command,
    build_crop_command, build_rotate_command, build_audio_command,
    build_overlay_command, build_watermark_command, build_encode_command,
    build_mux_command,
    build_extract_frame_command,
)
from app.docker_exec import execute_ffmpeg_command, extract_input_files
from app.logger import get_sanitized_logs, log_request, log_success, log_error, log_docker_command
from app.spaces import download_key_to_path, upload_path_to_key, get_public_url
from app.download import download_url_to_path


def upload_file_to_presigned_url(file_path: Path, presigned_put_url: str, content_type: str = "application/octet-stream") -> None:
    """Upload file to client-provided presigned PUT URL. Raises on failure."""
    with open(file_path, "rb") as f:
        content = f.read()
    resp = httpx.put(presigned_put_url, content=content, headers={"Content-Type": content_type}, timeout=60.0)
    resp.raise_for_status()


def _stream_path_then_cleanup(file_path: Path, job_dir: Path, chunk_size: int = 65536):
    """Yield file chunks then delete job_dir so cleanup happens after response is sent."""
    try:
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                yield chunk
    finally:
        if job_dir and job_dir.exists():
            shutil.rmtree(job_dir, ignore_errors=True)


app = FastAPI(title="FFmpeg API", version="1.0.0")


@app.get("/api/instructions", response_model=InstructionsResponse)
async def get_instructions(api_key: str = Depends(verify_api_key)):
    """
    Get API documentation for all endpoints.
    Output rule: job output is never written to server storage (SOURCE_DIR). For file-producing
    endpoints, either the file is streamed in the response (no output_destination), or the client
    provides output_destination.presigned_put_url and the result is uploaded there via PUT; then
    JSON success is returned. Client generates the pre-signed URL; no S3/Spaces credentials on server.
    """
    endpoints = [
        EndpointInfo(
            name="concat",
            method="POST",
            path="/api/ffmpeg/concat",
            description="Concatenate multiple video files (inputs from SOURCE_DIR). Output: streamed or output_destination.presigned_put_url.",
            request_body={
                "inputs": ["a.mp4", "b.mp4"],
                "output": "out.mp4",
                "output_destination": "optional: { \"presigned_put_url\": \"https://...\" }; if absent, file is streamed"
            },
            success_response={"stream": "file body", "presigned": {"status": "ok", "output": "uploaded"}},
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
            description="Concatenate 2+ videos from Spaces. Output: streamed in response or upload to output_destination.presigned_put_url. No server storage.",
            request_body={
                "inputs": [{"spaces_key": "path/to/input1.mp4"}, {"spaces_key": "path/to/input2.mp4"}],
                "output_destination": "optional: { \"presigned_put_url\": \"https://...\" }; if absent, file is streamed (Content-Disposition: attachment)"
            },
            success_response={
                "stream": "HTTP 200 with file body",
                "presigned": {"status": "ok", "output": "uploaded"}
            },
            error_response={"status": "error", "message": "Error description"}
        ),
        EndpointInfo(
            name="mux",
            method="POST",
            path="/api/ffmpeg/mux",
            description="Mux one video and one audio. Use (video, audio) or (video_url, audio_url). Output: streamed or output_destination.presigned_put_url. No server storage.",
            request_body={
                "local": {"video": "clip.mp4", "audio": "music.mp3", "output_destination": "optional"},
                "url": {"video_url": "https://...", "audio_url": "https://...", "output_destination": "optional"}
            },
            success_response={
                "stream": "HTTP 200 with file body",
                "presigned": {"status": "ok", "output": "uploaded"}
            },
            error_response={"status": "error", "message": "Error description"}
        ),
        EndpointInfo(
            name="extract-last-frame",
            method="POST",
            path="/api/ffmpeg/extract-last-frame",
            description="Extract a single frame from a source video URL or Spaces key. Compatible aliases: /api/ffmpeg/extract_frame and /api/ffmpeg/last-frame.",
            request_body={
                "video_url": "https://... OR spaces/key/to/video.mp4",
                "position": "optional: last|first|<seconds>; default last"
            },
            success_response={
                "status": "ok",
                "image_url": "https://public-image-url.jpg",
                "image_data_url": None
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


@app.post("/api/ffmpeg/concat_spaces")
async def concat_videos_from_spaces(
    request: ConcatSpacesRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    Concatenate two or more videos from DigitalOcean Spaces.
    Downloads inputs from Spaces, runs concat in /tmp, then streams result or uploads to
    client-provided output_destination.presigned_put_url. Output is never written to server storage.
    """
    import hashlib
    import json
    import logging
    import os
    import subprocess
    import uuid
    from app.ffmpeg import build_concat_command
    from app.schemas import ConcatRequest as LocalConcatRequest
    from app.valkey_guard import get_guard

    if len(request.inputs) < 2:
        return ErrorResponse(message="At least 2 inputs required for concat_spaces")

    for inp in request.inputs:
        if not inp.spaces_key or not inp.spaces_key.strip():
            return ErrorResponse(message="Input spaces_key cannot be empty")
        if ".." in inp.spaces_key or inp.spaces_key.startswith("/"):
            return ErrorResponse(message="Invalid spaces_key: cannot contain '..' or start with '/'")

    allowed_extensions = {".mp4", ".mov", ".m4v", ".webm"}
    for inp in request.inputs:
        ext = Path(inp.spaces_key).suffix.lower()
        if ext not in allowed_extensions:
            return ErrorResponse(message=f"Invalid input file extension: {ext}. Allowed: {', '.join(allowed_extensions)}")

    guard = get_guard()
    allowed, error_msg = guard.check_rate_limit(api_key)
    if not allowed:
        return ErrorResponse(message=error_msg)

    dedupe_payload = {"inputs": [inp.spaces_key for inp in request.inputs]}
    dedupe_key = hashlib.sha256(json.dumps(dedupe_payload, sort_keys=True).encode()).hexdigest()
    acquired_dedupe, error_msg = guard.acquire_dedupe(dedupe_key)
    if not acquired_dedupe:
        return ErrorResponse(message=error_msg)

    job_id = str(uuid.uuid4())
    job_dir = Path("/tmp") / f"job-{job_id}"
    log_request("concat_spaces", job_id)
    logger = logging.getLogger("ffmpeg-api")
    streaming_response = False  # set True when returning stream so finally does not delete before send

    try:
        job_dir.mkdir(parents=True, exist_ok=True)

        local_inputs = []
        for i, inp in enumerate(request.inputs):
            filename = f"input_{i}.mp4"
            local_path = job_dir / filename
            try:
                download_key_to_path(inp.spaces_key, str(local_path))
                local_inputs.append(filename)
            except Exception as e:
                log_error(job_id, f"Failed to download {inp.spaces_key}: {str(e)}")
                return ErrorResponse(message=f"Failed to download input from Spaces: {str(e)}")

        output_filename = "output.mp4"
        local_concat_req = LocalConcatRequest(inputs=local_inputs, output=output_filename)
        command = build_concat_command(local_concat_req)

        acquired_slot, error_msg = guard.acquire_slot(job_id)
        if not acquired_slot:
            return ErrorResponse(message=error_msg)
        try:
            docker_cmd = [
                "docker", "run", "--rm",
                "-v", f"{job_dir}:/videos",
                "media-handler"
            ] + command
            log_docker_command(job_id, docker_cmd)
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=3600
            )
        finally:
            guard.release_slot(job_id)

        output_path = job_dir / output_filename

        try:
            dir_contents = [f"{f} ({os.path.getsize(job_dir / f) if (job_dir / f).is_file() else 0} bytes)" for f in os.listdir(job_dir)]
            logger.info(f"job={job_id} job_dir_contents={', '.join(dir_contents)}")
        except Exception as e:
            logger.warning(f"job={job_id} failed_to_list_dir error={str(e)}")

        if result.returncode != 0:
            error_msg = result.stderr or result.stdout or "Unknown error"
            log_error(job_id, error_msg)
            return ErrorResponse(message=f"FFmpeg concat failed: {error_msg[:200]}")
        if not output_path.exists():
            log_error(job_id, "Output file does not exist after FFmpeg execution")
            return ErrorResponse(message="Output file was not created by FFmpeg")
        if output_path.stat().st_size == 0:
            log_error(job_id, "Output file is empty (0 bytes)")
            return ErrorResponse(message="Output file is empty - concat may have failed silently")

        try:
            probe_result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(output_path)],
                capture_output=True,
                text=True,
                timeout=30
            )
            duration_str = probe_result.stdout.strip()
            duration = float(duration_str) if duration_str else 0.0
            logger.info(f"job={job_id} output_duration={duration}s")
            if duration < 0.1:
                log_error(job_id, f"Output duration is invalid: {duration}s")
                return ErrorResponse(message=f"Output video has invalid duration ({duration}s) - concat failed")
        except Exception as e:
            logger.warning(f"job={job_id} ffprobe_validation_failed error={str(e)}")

        log_success(job_id, output_filename)

        if request.output_destination and request.output_destination.presigned_put_url:
            try:
                upload_file_to_presigned_url(
                    output_path,
                    request.output_destination.presigned_put_url,
                    content_type="video/mp4",
                )
                if job_dir.exists():
                    shutil.rmtree(job_dir, ignore_errors=True)
                return SuccessResponse(status="ok", output="uploaded")
            except Exception as e:
                log_error(job_id, f"Failed to upload to presigned URL: {str(e)}")
                if job_dir.exists():
                    shutil.rmtree(job_dir, ignore_errors=True)
                return ErrorResponse(message=f"Failed to upload output: {str(e)}")

        streaming_response = True
        return StreamingResponse(
            _stream_path_then_cleanup(output_path, job_dir),
            media_type="video/mp4",
            headers={"Content-Disposition": f'attachment; filename="{output_filename}"'},
        )
    except Exception as e:
        log_error(job_id, str(e))
        return ErrorResponse(message=f"Unexpected error: {str(e)}")
    finally:
        guard.release_dedupe(dedupe_key)
        if not streaming_response and job_dir.exists():
            shutil.rmtree(job_dir, ignore_errors=True)


@app.post("/api/ffmpeg/concat")
async def concat_videos(request: ConcatRequest, api_key: str = Depends(verify_api_key)):
    command = build_concat_command(request)
    input_files = request.inputs
    success, job_dir, output_filename, message = execute_ffmpeg_command(command, input_files, api_key)
    if not success:
        return ErrorResponse(message=message)
    output_path = job_dir / output_filename
    if request.output_destination and request.output_destination.presigned_put_url:
        upload_file_to_presigned_url(
            output_path,
            request.output_destination.presigned_put_url,
            content_type="video/mp4",
        )
        if job_dir and job_dir.exists():
            shutil.rmtree(job_dir, ignore_errors=True)
        return SuccessResponse(status="ok", output="uploaded")
    return StreamingResponse(
        _stream_path_then_cleanup(output_path, job_dir),
        media_type="video/mp4",
        headers={"Content-Disposition": f'attachment; filename="{output_filename}"'},
    )


@app.post("/api/ffmpeg/trim")
async def trim_video(request: TrimRequest, api_key: str = Depends(verify_api_key)):
    command = build_trim_command(request)
    input_files = [request.input]
    success, job_dir, output_filename, message = execute_ffmpeg_command(command, input_files, api_key)
    if not success:
        return ErrorResponse(message=message)
    output_path = job_dir / output_filename
    if request.output_destination and request.output_destination.presigned_put_url:
        upload_file_to_presigned_url(
            output_path,
            request.output_destination.presigned_put_url,
            content_type="video/mp4",
        )
        if job_dir and job_dir.exists():
            shutil.rmtree(job_dir, ignore_errors=True)
        return SuccessResponse(status="ok", output="uploaded")
    return StreamingResponse(
        _stream_path_then_cleanup(output_path, job_dir),
        media_type="video/mp4",
        headers={"Content-Disposition": f'attachment; filename="{output_filename}"'},
    )


@app.post("/api/ffmpeg/scale")
async def scale_video(request: ScaleRequest, api_key: str = Depends(verify_api_key)):
    command = build_scale_command(request)
    input_files = [request.input]
    success, job_dir, output_filename, message = execute_ffmpeg_command(command, input_files, api_key)
    if not success:
        return ErrorResponse(message=message)
    output_path = job_dir / output_filename
    if request.output_destination and request.output_destination.presigned_put_url:
        upload_file_to_presigned_url(
            output_path,
            request.output_destination.presigned_put_url,
            content_type="video/mp4",
        )
        if job_dir and job_dir.exists():
            shutil.rmtree(job_dir, ignore_errors=True)
        return SuccessResponse(status="ok", output="uploaded")
    return StreamingResponse(
        _stream_path_then_cleanup(output_path, job_dir),
        media_type="video/mp4",
        headers={"Content-Disposition": f'attachment; filename="{output_filename}"'},
    )


@app.post("/api/ffmpeg/crop")
async def crop_video(request: CropRequest, api_key: str = Depends(verify_api_key)):
    command = build_crop_command(request)
    input_files = [request.input]
    success, job_dir, output_filename, message = execute_ffmpeg_command(command, input_files, api_key)
    if not success:
        return ErrorResponse(message=message)
    output_path = job_dir / output_filename
    if request.output_destination and request.output_destination.presigned_put_url:
        upload_file_to_presigned_url(
            output_path,
            request.output_destination.presigned_put_url,
            content_type="video/mp4",
        )
        if job_dir and job_dir.exists():
            shutil.rmtree(job_dir, ignore_errors=True)
        return SuccessResponse(status="ok", output="uploaded")
    return StreamingResponse(
        _stream_path_then_cleanup(output_path, job_dir),
        media_type="video/mp4",
        headers={"Content-Disposition": f'attachment; filename="{output_filename}"'},
    )


@app.post("/api/ffmpeg/rotate")
async def rotate_video(request: RotateRequest, api_key: str = Depends(verify_api_key)):
    command = build_rotate_command(request)
    input_files = [request.input]
    success, job_dir, output_filename, message = execute_ffmpeg_command(command, input_files, api_key)
    if not success:
        return ErrorResponse(message=message)
    output_path = job_dir / output_filename
    if request.output_destination and request.output_destination.presigned_put_url:
        upload_file_to_presigned_url(
            output_path,
            request.output_destination.presigned_put_url,
            content_type="video/mp4",
        )
        if job_dir and job_dir.exists():
            shutil.rmtree(job_dir, ignore_errors=True)
        return SuccessResponse(status="ok", output="uploaded")
    return StreamingResponse(
        _stream_path_then_cleanup(output_path, job_dir),
        media_type="video/mp4",
        headers={"Content-Disposition": f'attachment; filename="{output_filename}"'},
    )


@app.post("/api/ffmpeg/audio")
async def process_audio(request: AudioRequest, api_key: str = Depends(verify_api_key)):
    command = build_audio_command(request)
    input_files = [request.input]
    success, job_dir, output_filename, message = execute_ffmpeg_command(command, input_files, api_key)
    if not success:
        return ErrorResponse(message=message)
    output_path = job_dir / output_filename
    if request.output_destination and request.output_destination.presigned_put_url:
        upload_file_to_presigned_url(
            output_path,
            request.output_destination.presigned_put_url,
            content_type="video/mp4",
        )
        if job_dir and job_dir.exists():
            shutil.rmtree(job_dir, ignore_errors=True)
        return SuccessResponse(status="ok", output="uploaded")
    return StreamingResponse(
        _stream_path_then_cleanup(output_path, job_dir),
        media_type="video/mp4",
        headers={"Content-Disposition": f'attachment; filename="{output_filename}"'},
    )


@app.post("/api/ffmpeg/overlay")
async def overlay_videos(request: OverlayRequest, api_key: str = Depends(verify_api_key)):
    command = build_overlay_command(request)
    input_files = [request.base, request.overlay]
    success, job_dir, output_filename, message = execute_ffmpeg_command(command, input_files, api_key)
    if not success:
        return ErrorResponse(message=message)
    output_path = job_dir / output_filename
    if request.output_destination and request.output_destination.presigned_put_url:
        upload_file_to_presigned_url(
            output_path,
            request.output_destination.presigned_put_url,
            content_type="video/mp4",
        )
        if job_dir and job_dir.exists():
            shutil.rmtree(job_dir, ignore_errors=True)
        return SuccessResponse(status="ok", output="uploaded")
    return StreamingResponse(
        _stream_path_then_cleanup(output_path, job_dir),
        media_type="video/mp4",
        headers={"Content-Disposition": f'attachment; filename="{output_filename}"'},
    )


@app.post("/api/ffmpeg/watermark")
async def add_watermark(request: WatermarkRequest, api_key: str = Depends(verify_api_key)):
    command = build_watermark_command(request)
    input_files = [request.video, request.image]
    success, job_dir, output_filename, message = execute_ffmpeg_command(command, input_files, api_key)
    if not success:
        return ErrorResponse(message=message)
    output_path = job_dir / output_filename
    if request.output_destination and request.output_destination.presigned_put_url:
        upload_file_to_presigned_url(
            output_path,
            request.output_destination.presigned_put_url,
            content_type="video/mp4",
        )
        if job_dir and job_dir.exists():
            shutil.rmtree(job_dir, ignore_errors=True)
        return SuccessResponse(status="ok", output="uploaded")
    return StreamingResponse(
        _stream_path_then_cleanup(output_path, job_dir),
        media_type="video/mp4",
        headers={"Content-Disposition": f'attachment; filename="{output_filename}"'},
    )


@app.post("/api/ffmpeg/encode")
async def encode_video(request: EncodeRequest, api_key: str = Depends(verify_api_key)):
    command = build_encode_command(request)
    input_files = [request.input]
    success, job_dir, output_filename, message = execute_ffmpeg_command(command, input_files, api_key)
    if not success:
        return ErrorResponse(message=message)
    output_path = job_dir / output_filename
    if request.output_destination and request.output_destination.presigned_put_url:
        upload_file_to_presigned_url(
            output_path,
            request.output_destination.presigned_put_url,
            content_type="application/octet-stream",
        )
        if job_dir and job_dir.exists():
            shutil.rmtree(job_dir, ignore_errors=True)
        return SuccessResponse(status="ok", output="uploaded")
    return StreamingResponse(
        _stream_path_then_cleanup(output_path, job_dir),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{output_filename}"'},
    )


# Allowed extensions for mux endpoint
_MUX_VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm"}
_MUX_AUDIO_EXTENSIONS = {".mp3", ".m4a", ".wav", ".aac"}


@app.post("/api/ffmpeg/mux")
async def mux_video_audio(request: MuxRequest, api_key: str = Depends(verify_api_key)):
    """
    Mux one video and one audio into a single video (replaces video's audio with the supplied audio).
    Use either local filenames (video, audio) or URLs (video_url, audio_url).
    Output: stream in response, or upload to client-provided output_destination.presigned_put_url.
    Output length = shorter of the two inputs (-shortest).
    """
    import json
    import hashlib
    import subprocess
    import uuid
    from app.valkey_guard import get_guard

    output_filename = "output.mp4"

    if request.video is not None and request.audio is not None:
        # --- Local mode: inputs from SOURCE_DIR ---
        for name, val in [("video", request.video), ("audio", request.audio)]:
            if ".." in val or val.startswith("/"):
                return ErrorResponse(message=f"Invalid {name}: cannot contain '..' or start with '/'")
        video_ext = Path(request.video).suffix.lower()
        audio_ext = Path(request.audio).suffix.lower()
        if video_ext not in _MUX_VIDEO_EXTENSIONS:
            return ErrorResponse(
                message=f"Invalid video extension: {video_ext}. Allowed: {', '.join(sorted(_MUX_VIDEO_EXTENSIONS))}"
            )
        if audio_ext not in _MUX_AUDIO_EXTENSIONS:
            return ErrorResponse(
                message=f"Invalid audio extension: {audio_ext}. Allowed: {', '.join(sorted(_MUX_AUDIO_EXTENSIONS))}"
            )
        command = build_mux_command(request.video, request.audio, output_filename)
        success, job_dir, out_name, message = execute_ffmpeg_command(command, [request.video, request.audio], api_key)
        if not success:
            return ErrorResponse(message=message)
        output_path = job_dir / out_name
        if request.output_destination and request.output_destination.presigned_put_url:
            upload_file_to_presigned_url(
                output_path,
                request.output_destination.presigned_put_url,
                content_type="video/mp4",
            )
            if job_dir and job_dir.exists():
                shutil.rmtree(job_dir, ignore_errors=True)
            return SuccessResponse(status="ok", output="uploaded")
        return StreamingResponse(
            _stream_path_then_cleanup(output_path, job_dir),
            media_type="video/mp4",
            headers={"Content-Disposition": f'attachment; filename="{output_filename}"'},
        )

    # --- URL mode ---
    video_url = request.video_url
    audio_url = request.audio_url
    url_lower_v = video_url.strip().lower()
    url_lower_a = audio_url.strip().lower()
    if not (url_lower_v.startswith("http://") or url_lower_v.startswith("https://")):
        return ErrorResponse(message="video_url must use http:// or https://")
    if not (url_lower_a.startswith("http://") or url_lower_a.startswith("https://")):
        return ErrorResponse(message="audio_url must use http:// or https://")

    guard = get_guard()
    allowed, error_msg = guard.check_rate_limit(api_key)
    if not allowed:
        return ErrorResponse(message=error_msg)

    dedupe_payload = {"video_url": video_url, "audio_url": audio_url}
    dedupe_key = hashlib.sha256(json.dumps(dedupe_payload, sort_keys=True).encode()).hexdigest()
    acquired_dedupe, error_msg = guard.acquire_dedupe(dedupe_key)
    if not acquired_dedupe:
        return ErrorResponse(message=error_msg)

    job_id = str(uuid.uuid4())
    job_dir = Path("/tmp") / f"job-{job_id}"
    log_request("mux", job_id)
    streaming_response = False

    try:
        job_dir.mkdir(parents=True, exist_ok=True)
        video_path = job_dir / "video.mp4"
        audio_path = job_dir / "audio.mp3"
        try:
            download_url_to_path(video_url, str(video_path), default_extension=".mp4")
            download_url_to_path(audio_url, str(audio_path), default_extension=".mp3")
        except ValueError as e:
            log_error(job_id, str(e))
            return ErrorResponse(message=str(e))
        except Exception as e:
            log_error(job_id, f"Download failed: {str(e)}")
            return ErrorResponse(message=f"Download failed: {str(e)}")

        command = build_mux_command("video.mp4", "audio.mp3", output_filename)
        docker_cmd = [
            "docker", "run", "--rm",
            "-v", f"{job_dir}:/videos",
            "media-handler"
        ] + command

        log_docker_command(job_id, docker_cmd)
        acquired_slot, error_msg = guard.acquire_slot(job_id)
        if not acquired_slot:
            return ErrorResponse(message=error_msg)
        try:
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=3600
            )
        finally:
            guard.release_slot(job_id)

        output_path = job_dir / output_filename
        if result.returncode != 0:
            error_msg = result.stderr or result.stdout or "Unknown error"
            log_error(job_id, error_msg)
            return ErrorResponse(message=f"FFmpeg mux failed: {error_msg[:200]}")
        if not output_path.exists():
            log_error(job_id, "Output file does not exist after FFmpeg execution")
            return ErrorResponse(message="Output file was not created by FFmpeg")
        if output_path.stat().st_size == 0:
            log_error(job_id, "Output file is empty")
            return ErrorResponse(message="Output file is empty")

        log_success(job_id, "output.mp4")
        if request.output_destination and request.output_destination.presigned_put_url:
            upload_file_to_presigned_url(
                output_path,
                request.output_destination.presigned_put_url,
                content_type="video/mp4",
            )
            if job_dir.exists():
                shutil.rmtree(job_dir, ignore_errors=True)
            return SuccessResponse(status="ok", output="uploaded")
        streaming_response = True
        return StreamingResponse(
            _stream_path_then_cleanup(output_path, job_dir),
            media_type="video/mp4",
            headers={"Content-Disposition": f'attachment; filename="{output_filename}"'},
        )
    except Exception as e:
        log_error(job_id, str(e))
        return ErrorResponse(message=f"Unexpected error: {str(e)}")
    finally:
        guard.release_dedupe(dedupe_key)
        if not streaming_response and job_dir.exists():
            shutil.rmtree(job_dir, ignore_errors=True)


async def _extract_last_frame_impl(request: ExtractFrameRequest, api_key: str) -> ExtractFrameResponse | ErrorResponse:
    import hashlib
    import json
    import subprocess
    import uuid
    from app.valkey_guard import get_guard

    source_ref = (request.video_url or "").strip()
    if not source_ref:
        return ErrorResponse(message="video_url is required")

    position = (request.position or "last").strip() or "last"
    guard = get_guard()
    allowed, error_msg = guard.check_rate_limit(api_key)
    if not allowed:
        return ErrorResponse(message=error_msg)

    dedupe_payload = {"video_url": source_ref, "position": position}
    dedupe_key = hashlib.sha256(json.dumps(dedupe_payload, sort_keys=True).encode()).hexdigest()
    acquired_dedupe, error_msg = guard.acquire_dedupe(dedupe_key)
    if not acquired_dedupe:
        return ErrorResponse(message=error_msg)

    job_id = str(uuid.uuid4())
    job_dir = Path("/tmp") / f"job-{job_id}"
    input_name = "input.mp4"
    output_name = "frame.jpg"
    streaming_response = False
    log_request("extract_last_frame", job_id)

    try:
        job_dir.mkdir(parents=True, exist_ok=True)
        input_path = job_dir / input_name
        output_path = job_dir / output_name

        source_lower = source_ref.lower()
        if source_lower.startswith("http://") or source_lower.startswith("https://"):
            try:
                download_url_to_path(source_ref, str(input_path), default_extension=".mp4")
            except ValueError as e:
                log_error(job_id, str(e))
                return ErrorResponse(message=str(e))
            except Exception as e:
                log_error(job_id, f"Download failed: {str(e)}")
                return ErrorResponse(message=f"Download failed: {str(e)}")
        else:
            if ".." in source_ref or source_ref.startswith("/"):
                return ErrorResponse(message="Invalid video_url: cannot contain '..' or start with '/'")
            ext = Path(source_ref).suffix.lower()
            if ext and ext not in _MUX_VIDEO_EXTENSIONS:
                return ErrorResponse(
                    message=f"Invalid input file extension: {ext}. Allowed: {', '.join(sorted(_MUX_VIDEO_EXTENSIONS))}"
                )
            try:
                download_key_to_path(source_ref, str(input_path))
            except Exception as e:
                log_error(job_id, f"Failed to download {source_ref}: {str(e)}")
                return ErrorResponse(message=f"Failed to download input from Spaces: {str(e)}")

        command = build_extract_frame_command(request, input_name=input_name, output_name=output_name)
        docker_cmd = [
            "docker", "run", "--rm",
            "-v", f"{job_dir}:/videos",
            "media-handler"
        ] + command
        log_docker_command(job_id, docker_cmd)

        acquired_slot, error_msg = guard.acquire_slot(job_id)
        if not acquired_slot:
            return ErrorResponse(message=error_msg)
        try:
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=3600,
            )
        finally:
            guard.release_slot(job_id)

        if result.returncode != 0:
            error_msg = result.stderr or result.stdout or "Unknown error"
            log_error(job_id, error_msg)
            return ErrorResponse(message=f"FFmpeg frame extraction failed: {error_msg[:200]}")
        if not output_path.exists():
            log_error(job_id, "Output image does not exist after FFmpeg execution")
            return ErrorResponse(message="Output image was not created by FFmpeg")
        if output_path.stat().st_size == 0:
            log_error(job_id, "Output image is empty")
            return ErrorResponse(message="Output image is empty")

        image_url = None
        if request.output_destination and request.output_destination.presigned_put_url:
            try:
                upload_file_to_presigned_url(
                    output_path,
                    request.output_destination.presigned_put_url,
                    content_type="image/jpeg",
                )
            except Exception as e:
                log_error(job_id, f"Failed to upload to presigned URL: {str(e)}")
                return ErrorResponse(message=f"Failed to upload output: {str(e)}")

        spaces_key = f"frames/{job_id}/last-frame.jpg"
        try:
            upload_path_to_key(str(output_path), spaces_key, content_type="image/jpeg")
            image_url = get_public_url(spaces_key)
        except Exception as e:
            log_error(job_id, f"Failed to upload frame to Spaces: {str(e)}")
            return ErrorResponse(message=f"Failed to upload frame to Spaces: {str(e)}")

        if not image_url:
            return ErrorResponse(message="SPACES_PUBLIC_BASE_URL is not configured; cannot return image_url")

        log_success(job_id, output_name)
        return ExtractFrameResponse(status="ok", image_url=image_url, image_data_url=None)
    except Exception as e:
        log_error(job_id, str(e))
        return ErrorResponse(message=f"Unexpected error: {str(e)}")
    finally:
        guard.release_dedupe(dedupe_key)
        if not streaming_response and job_dir.exists():
            shutil.rmtree(job_dir, ignore_errors=True)


@app.post("/api/ffmpeg/extract-last-frame")
async def extract_last_frame(request: ExtractFrameRequest, api_key: str = Depends(verify_api_key)):
    return await _extract_last_frame_impl(request, api_key)


@app.post("/api/ffmpeg/extract_frame")
async def extract_frame_legacy(request: ExtractFrameRequest, api_key: str = Depends(verify_api_key)):
    return await _extract_last_frame_impl(request, api_key)


@app.post("/api/ffmpeg/last-frame")
async def last_frame_legacy(request: ExtractFrameRequest, api_key: str = Depends(verify_api_key)):
    return await _extract_last_frame_impl(request, api_key)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
