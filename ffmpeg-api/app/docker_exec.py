import os
import uuid
import shutil
import subprocess
from pathlib import Path
from typing import List, Tuple


SOURCE_DIR = os.getenv("SOURCE_DIR", "/source")
TEMP_BASE = "/tmp"


def execute_ffmpeg_command(command: List[str], input_files: List[str]) -> Tuple[bool, str, str]:
    job_id = str(uuid.uuid4())
    job_dir = Path(TEMP_BASE) / f"job-{job_id}"
    
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
            "video-stitcher"
        ] + command
        
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
            return True, output_file, result.stdout
        else:
            return False, "", result.stderr or result.stdout
    
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out after 1 hour"
    except Exception as e:
        return False, "", str(e)
    finally:
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
