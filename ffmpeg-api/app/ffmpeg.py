from typing import List
from app.schemas import (
    ConcatRequest, TrimRequest, ScaleRequest, CropRequest,
    RotateRequest, AudioRequest, OverlayRequest, WatermarkRequest,
    EncodeRequest
)


def build_concat_command(req: ConcatRequest) -> List[str]:
    cmd = ["concat"] + req.inputs + [req.output]
    return cmd


def build_trim_command(req: TrimRequest) -> List[str]:
    cmd = ["trim"]
    if req.start is not None:
        cmd.extend(["--start", str(req.start)])
    if req.end is not None:
        cmd.extend(["--end", str(req.end)])
    elif req.duration is not None:
        cmd.extend(["--duration", str(req.duration)])
    cmd.extend([req.input, req.output])
    return cmd


def build_scale_command(req: ScaleRequest) -> List[str]:
    cmd = ["scale", "--size", req.size]
    if req.aspect_ratio:
        cmd.append("--aspect-ratio")
    cmd.extend([req.input, req.output])
    return cmd


def build_crop_command(req: CropRequest) -> List[str]:
    cmd = ["crop", str(req.x), str(req.y), str(req.width), str(req.height), req.input, req.output]
    return cmd


def build_rotate_command(req: RotateRequest) -> List[str]:
    cmd = ["rotate", str(req.angle), req.input, req.output]
    return cmd


def build_audio_command(req: AudioRequest) -> List[str]:
    cmd = ["mute"]
    if req.normalize:
        cmd.append("--normalize")
    cmd.extend([req.input, req.output])
    return cmd


def build_overlay_command(req: OverlayRequest) -> List[str]:
    cmd = ["overlay", "--x", str(req.x), "--y", str(req.y), req.base, req.overlay, req.output]
    return cmd


def build_watermark_command(req: WatermarkRequest) -> List[str]:
    cmd = ["watermark"]
    
    if req.position:
        cmd.extend(["--position", req.position])
    elif req.x is not None and req.y is not None:
        cmd.extend(["--x", str(req.x), "--y", str(req.y)])
    
    if req.opacity != 1.0:
        cmd.extend(["--opacity", str(req.opacity)])
    
    cmd.extend([req.video, req.image, req.output])
    return cmd


def build_encode_command(req: EncodeRequest) -> List[str]:
    cmd = ["format"]
    if req.format:
        cmd.extend(["--format", req.format])
    if req.vcodec:
        cmd.extend(["--vcodec", req.vcodec])
    if req.acodec:
        cmd.extend(["--acodec", req.acodec])
    cmd.extend([req.input, req.output])
    return cmd
