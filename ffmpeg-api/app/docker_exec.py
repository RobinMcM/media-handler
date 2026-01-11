import os
import uuid
import shutil
import subprocess
from pathlib import Path
from typing import List, Tuple, Optional
from app.logger import log_request, log_docker_command, log_success, log_error
from app.valkey_guard import get_guard


SOURCE_DIR = os.getenv("SOURCE_DIR", "/source")
TEMP_BASE = "/tmp"


def execute_ffmpeg_command(
    command: List[str],
    input_files: List[str],
    api_key: Optional[str] = None
) -> Tuple[bool, str, str]:
    job_id = str(uuid.uuid4())
    job_dir = Path(TEMP_BASE) / f"job-{job_id}"
    
    # Log request received
    log_request("ffmpeg", job_id)
    
    # Admission control: rate limiting
    guard = get_guard()
    if api_key:
        allowed, error_msg = guard.check_rate_limit(api_key)
        if not allowed:
            log_error(job_id, f"Rate limit exceeded for API key")
            return False, "", error_msg
    
    # Admission control: global concurrency semaphore
    acquired, error_msg = guard.acquire_slot(job_id)
    if not acquired:
        log_error(job_id, error_msg)
        return False, "", error_msg
    
    try:
        job_dir.mkdir(parents=True, exist_ok=True)
        
        for input_file in input_files:
            source_path = Path(SOURCE_DIR) / input_file
            if not source_path.exists():
                return False, "", f"Input file not found: {input_file}"
            
            dest_path = job_dir / input_file
            shutil.copy2(source_path, dest_path)
        
        docker_cmd = [
            "docker", "run", "--rm",
            "-v", f"{job_dir}:/videos",
            "media-handler"
        ] + command
        
        # Log docker command (sanitized)
        log_docker_command(job_id, docker_cmd)
        
        print(f"Executing: {' '.join(docker_cmd)}")
        
        result = subprocess.run(
            docker_cmd,
            capture_output=True,
            text=True,
            timeout=3600
        )
        
        output_file = command[-1]
        output_path = job_dir / output_file
        
        if result.returncode == 0 and output_path.exists():
            final_output = Path(SOURCE_DIR) / output_file
            shutil.copy2(output_path, final_output)
            log_success(job_id, output_file)
            return True, output_file, result.stdout
        else:
            error_msg = result.stderr or result.stdout
            log_error(job_id, error_msg)
            return False, "", error_msg
    
    except subprocess.TimeoutExpired:
        log_error(job_id, "Command timed out after 1 hour")
        return False, "", "Command timed out after 1 hour"
    except Exception as e:
        log_error(job_id, str(e))
        return False, "", str(e)
    finally:
        # Release semaphore slot
        guard.release_slot(job_id)
        
        # Clean up job directory
        if job_dir.exists():
            shutil.rmtree(job_dir, ignore_errors=True)


def extract_input_files(command: List[str]) -> List[str]:
    inputs = []
    
    operation = command[0] if command else ""
    
    if operation == "concat":
        for arg in command[1:]:
            if not arg.startswith("--") and arg != command[-1]:
                inputs.append(arg)
    
    elif operation == "trim":
        i = 1
        while i < len(command):
            if command[i].startswith("--"):
                i += 2
            else:
                if i < len(command) - 1:
                    inputs.append(command[i])
                break
    
    elif operation in ["scale", "crop", "rotate", "mute", "format"]:
        for i, arg in enumerate(command):
            if not arg.startswith("--") and i > 0:
                if i < len(command) - 1:
                    inputs.append(arg)
                break
    
    elif operation in ["overlay", "watermark"]:
        i = 1
        while i < len(command):
            if command[i].startswith("--"):
                i += 2
            else:
                if i < len(command) - 1:
                    inputs.append(command[i])
                if operation == "overlay" and i < len(command) - 2:
                    inputs.append(command[i + 1])
                elif operation == "watermark" and i < len(command) - 2:
                    inputs.append(command[i + 1])
                break
    
    return inputs
